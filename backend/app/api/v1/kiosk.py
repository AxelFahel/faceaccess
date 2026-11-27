"""Kiosk / Terminal Mode: 1:1 facial verification & attendance registration."""
from __future__ import annotations

import base64
import uuid
from datetime import UTC, datetime, timedelta

import cv2
import numpy as np
from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import AuthenticatedPrincipal, get_current_terminal
from app.biometrics.engine import get_biometric_engine
from app.core.config import get_settings
from app.core.crypto import (
    EncryptedBlob,
    biometric_key_ring,
    deserialize_template,
    template_aad,
)
from app.core.errors import Forbidden, ValidationFailed
from app.core.security import verify_secret
from app.core.timeutil import local_today, utcnow
from app.db.session import get_db
from app.models.access import (
    AccessEvent,
    AccessLocation,
    AccessRule,
    Terminal,
    VerificationEvent,
)
from app.models.attendance import AttendanceRecord, RecordType
from app.models.biometric import BiometricEnrollment, EnrollmentStatus
from app.models.employee import BiometricStatus, Employee, EmploymentStatus
from app.schemas.dto import KioskVerifyRequest, KioskVerifyResponse
from app.services.audit import AuditService

router = APIRouter(prefix="/kiosk", tags=["Terminal & Kiosk"])


@router.get("/terminal")
def terminal_info(
    principal: AuthenticatedPrincipal = Depends(get_current_terminal),
    db: Session = Depends(get_db),
):
    terminal = db.get(Terminal, principal.id)
    terminal.last_seen_at = utcnow()
    db.commit()
    return {"code": terminal.code, "name": terminal.name, "allowed_operations": terminal.allowed_operations}


def _capture_problem(feature, require_liveness=True):
    if feature is None:
        return KioskVerifyResponse(status="inconclusive", message="Posicione seu rosto na marcação.", retryable=True)
    if not feature.quality.passed:
        return KioskVerifyResponse(
            status="inconclusive", message=" ".join(feature.quality.errors) or "Ajuste a posição e a iluminação.",
            quality_score=feature.quality.score, retryable=True,
        )
    if require_liveness and (not feature.liveness or not feature.liveness.is_real):
        return KioskVerifyResponse(status="rejected", message="Vivacidade não confirmada. Olhe diretamente para a câmera.", liveness_passed=False, retryable=True)
    return None


def _identify_in_unit(db, terminal, feature, engine, settings):
    """Compare once-extracted features only with active enrollments in this terminal's unit."""
    rows = db.execute(
        select(Employee, BiometricEnrollment)
        .join(BiometricEnrollment, BiometricEnrollment.employee_id == Employee.id)
        .where(
            Employee.unit_id == terminal.unit_id,
            Employee.employment_status == EmploymentStatus.ACTIVE,
            Employee.biometric_status == BiometricStatus.ENROLLED,
            BiometricEnrollment.status == EnrollmentStatus.ACTIVE,
        )
    ).all()
    keyring = biometric_key_ring()
    # Rank people, not enrollments, to avoid treating duplicate templates as two identities.
    candidates = {}
    for emp, enrollment in rows:
        if (enrollment.engine_version != engine.version or not enrollment.key_id
                or not enrollment.template_nonce or not enrollment.template_ciphertext):
            continue
        try:
            vector = deserialize_template(keyring.decrypt(
                EncryptedBlob(enrollment.key_id, enrollment.template_nonce, enrollment.template_ciphertext),
                template_aad(str(enrollment.id), str(emp.id), enrollment.engine_version),
            ))
            if vector.shape != feature.embedding.shape:
                continue
            score = float(engine.compute_similarity(vector, feature.embedding))
        except Exception:
            continue  # An unreadable template must never authorize a person.
        if np.isfinite(score) and (emp.id not in candidates or score > candidates[emp.id][0]):
            candidates[emp.id] = (score, emp, enrollment)
    ranked = sorted(candidates.values(), key=lambda item: item[0], reverse=True)
    if not ranked or ranked[0][0] < settings.match_threshold:
        return None, None, KioskVerifyResponse(
            status="rejected", message="Rosto não reconhecido nesta unidade. Procure o responsável ou utilize matrícula e PIN.", retryable=True,
        )
    if len(ranked) > 1 and ranked[0][0] - ranked[1][0] < settings.identification_min_margin:
        return None, None, KioskVerifyResponse(
            status="inconclusive", message="Não foi possível distinguir a identidade com segurança. Utilize matrícula e PIN.",
        )
    return ranked[0][1], ranked[0][2], None


def _decode_image(b64_str: str) -> np.ndarray:
    try:
        if "," in b64_str:
            b64_str = b64_str.split(",", 1)[1]
        data = base64.b64decode(b64_str)
        arr = np.frombuffer(data, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError("Falha ao decodificar imagem.")
        return img
    except Exception as exc:
        raise ValidationFailed(f"Imagem base64 inválida: {exc}")


@router.post("/verify", response_model=KioskVerifyResponse)
def kiosk_verify(
    req: KioskVerifyRequest,
    request: Request,
    terminal_auth: AuthenticatedPrincipal = Depends(get_current_terminal),
    db: Session = Depends(get_db),
):
    s = get_settings()
    now = utcnow()

    # 1. Update terminal last seen
    terminal = db.get(Terminal, terminal_auth.id)
    if terminal:
        if req.operation_type not in terminal.allowed_operations:
            raise Forbidden("Operação não permitida para este terminal.")
        if req.method == "pin" and "pin_fallback" not in terminal.allowed_operations:
            raise Forbidden("Verificação por PIN não permitida neste terminal.")
        terminal.last_seen_at = now
        terminal.last_ip = request.state.client_ip

    # 2. Automatic identification, or declared identity for PIN / legacy 1:1 clients.
    ident = req.identifier.strip()
    feature = None
    selected_enrollment = None
    if req.method == "face" and not ident:
        if not terminal or not req.image_base64:
            raise ValidationFailed("Captura facial e terminal ativo são obrigatórios.")
        engine = get_biometric_engine()
        feature = engine.process_face(_decode_image(req.image_base64), check_liveness=True)
        problem = _capture_problem(feature)
        if problem:
            return problem
        emp, selected_enrollment, problem = _identify_in_unit(db, terminal, feature, engine, s)
        if problem:
            return problem
    else:
        if not ident:
            raise ValidationFailed("Informe a matrícula ou crachá para utilizar PIN.")
        emp = db.execute(
            select(Employee).where(
                (Employee.registration_number == ident) | (Employee.badge_code == ident)
            )
        ).scalar_one_or_none()

    if not emp:
        return KioskVerifyResponse(
            status="rejected",
            message="Identificação funcional não encontrada.",
            reasons=["Funcionário não cadastrado"],
        )

    if emp.employment_status != EmploymentStatus.ACTIVE:
        return KioskVerifyResponse(
            status="rejected",
            message=f"Cadastro funcional {emp.employment_status}. Acesso não permitido.",
            employee_name=emp.full_name,
            reasons=[f"Status funcional: {emp.employment_status}"],
        )

    # 3. Check verification method
    method = req.method.lower()
    similarity: float | None = None
    quality_score: float | None = None
    liveness_passed: bool | None = None
    verification_outcome = "inconclusive"
    reasons: list[str] = []

    if method == "pin":
        # Non-biometric alternative
        if not emp.pin_hash:
            return KioskVerifyResponse(
                status="rejected",
                message="PIN não cadastrado para este funcionário.",
                employee_name=emp.full_name,
                reasons=["PIN não configurado"],
            )
        if emp.pin_locked_until and emp.pin_locked_until > now:
            return KioskVerifyResponse(
                status="rejected",
                message="PIN bloqueado temporariamente por excesso de tentativas.",
                employee_name=emp.full_name,
                reasons=["PIN bloqueado"],
            )

        if not req.pin or not verify_secret(emp.pin_hash, req.pin):
            emp.pin_failed_count += 1
            if emp.pin_failed_count >= 5:
                emp.pin_locked_until = now + timedelta(minutes=15)
            db.commit()
            return KioskVerifyResponse(
                status="rejected",
                message="PIN incorreto.",
                employee_name=emp.full_name,
                reasons=["PIN inválido"],
            )

        emp.pin_failed_count = 0
        emp.pin_locked_until = None
        verification_outcome = "verified"

    elif method == "face":
        if emp.biometric_status != BiometricStatus.ENROLLED:
            return KioskVerifyResponse(
                status="no_biometrics",
                message="Biometria não cadastrada. Utilize o PIN ou procure o RH.",
                employee_name=emp.full_name,
                reasons=["Biometria facial não cadastrada"],
            )

        if not req.image_base64:
            raise ValidationFailed("Captura facial ausente para verificação biométrica.")

        enrollment = selected_enrollment or db.execute(
            select(BiometricEnrollment).where(
                BiometricEnrollment.employee_id == emp.id,
                BiometricEnrollment.status == EnrollmentStatus.ACTIVE,
            )
        ).scalar_one_or_none()

        if not enrollment or not enrollment.template_ciphertext or not enrollment.template_nonce or not enrollment.key_id:
            return KioskVerifyResponse(
                status="no_biometrics",
                message="Representação biométrica indisponível ou revogada.",
                employee_name=emp.full_name,
                reasons=["Cadastro biométrico indisponível"],
            )

        # Process input capture
        engine = get_biometric_engine()
        if feature is None:
            img_bgr = _decode_image(req.image_base64)
            feature = engine.process_face(img_bgr, check_liveness=s.liveness_enabled)

        if not feature:
            return KioskVerifyResponse(
                status="rejected",
                message="Nenhum rosto detectado na câmera. Posicione-se em frente ao visor.",
                employee_name=emp.full_name,
                reasons=["Rosto não detectado"],
                retryable=True,
            )

        quality_score = feature.quality.score
        if not feature.quality.passed:
            err_details = "; ".join(feature.quality.errors)
            return KioskVerifyResponse(
                status="inconclusive",
                message=f"Qualidade de captura insuficiente. {err_details}",
                employee_name=emp.full_name,
                quality_score=quality_score,
                reasons=feature.quality.errors,
                retryable=True,
            )

        if s.liveness_enabled and not feature.liveness:
            return KioskVerifyResponse(status="rejected", message="Não foi possível confirmar a vivacidade.", retryable=True)
        if feature.liveness:
            liveness_passed = feature.liveness.is_real
            if not liveness_passed:
                return KioskVerifyResponse(
                    status="rejected",
                    message="Verificação de vivacidade não concluída. Olhe diretamente para a câmera.",
                    employee_name=emp.full_name,
                    liveness_passed=False,
                    reasons=["Falha na prova de vivacidade"],
                    retryable=True,
                )

        # Decrypt registered template
        keyring = biometric_key_ring()
        aad = template_aad(str(enrollment.id), str(emp.id), enrollment.engine_version)
        try:
            pt = keyring.decrypt(
                EncryptedBlob(enrollment.key_id, enrollment.template_nonce, enrollment.template_ciphertext),
                aad,
            )
            master_vec = deserialize_template(pt)
        except Exception:
            return KioskVerifyResponse(
                status="rejected",
                message="Falha de integridade no cadastro biométrico.",
                employee_name=emp.full_name,
                reasons=["Erro de autenticação da representação biométrica"],
            )

        # Compute cosine similarity
        similarity = engine.compute_similarity(master_vec, feature.embedding)

        if similarity >= s.match_threshold:
            verification_outcome = "verified"
        elif similarity < s.inconclusive_threshold:
            verification_outcome = "rejected"
            reasons.append(f"Similaridade facial insuficiente ({similarity:.2f} < {s.match_threshold:.2f})")
        else:
            verification_outcome = "inconclusive"
            reasons.append(f"Resultado inconclusivo ({similarity:.2f}). Repita a captura.")

    # 4. Record VerificationEvent
    v_event = VerificationEvent(
        employee_id=emp.id,
        terminal_id=terminal.id if terminal else None,
        identifier_type="face" if not ident else "registration",
        method=method,
        outcome=verification_outcome,
        similarity=similarity,
        quality_score=quality_score,
        liveness_score=feature.liveness.confidence if (method == "face" and feature and feature.liveness) else None,
        liveness_passed=liveness_passed,
        reasons=reasons,
        engine_version=engine.version if method == "face" else "manual/pin",
    )
    db.add(v_event)
    db.flush()

    if verification_outcome != "verified":
        db.commit()
        return KioskVerifyResponse(
            status=verification_outcome,
            message="Identidade não confirmada." if verification_outcome == "rejected" else "Verificação inconclusiva.",
            employee_name=emp.full_name,
            similarity=similarity,
            quality_score=quality_score,
            liveness_passed=liveness_passed,
            reasons=reasons,
            retryable=verification_outcome == "inconclusive",
        )

    # 5. Authorization & Access Decision Check (Independent of biometric verification)
    access_decision = "granted"
    access_reasons = []

    # Check terminal / unit match
    if terminal and emp.unit_id != terminal.unit_id:
        access_decision = "denied"
        access_reasons.append(f"Funcionário alocado em outra unidade")

    # Record AccessEvent
    a_event = AccessEvent(
        employee_id=emp.id,
        terminal_id=terminal.id if terminal else None,
        unit_id=terminal.unit_id if terminal else emp.unit_id,
        verification_event_id=v_event.id,
        decision=access_decision,
        reasons=access_reasons,
        device_command="UNLOCK_RELAY" if access_decision == "granted" else None,
    )
    db.add(a_event)

    # 6. Record Attendance if granted and requested
    att_record_id: uuid.UUID | None = None
    if access_decision == "granted" and req.operation_type == "attendance":
        # Serialize attendance writes for this person on PostgreSQL.
        db.execute(select(Employee.id).where(Employee.id == emp.id).with_for_update()).scalar_one()
        rec_type = req.record_type or RecordType.ENTRY
        # Anti-duplicate check
        recent_window = now - timedelta(seconds=s.attendance_duplicate_window_seconds)
        dup = db.execute(
            select(AttendanceRecord).where(
                AttendanceRecord.employee_id == emp.id,
                AttendanceRecord.recorded_at >= recent_window,
                AttendanceRecord.status == "valid",
            ).limit(1)
        ).scalar_one_or_none()

        if dup:
            access_reasons.append("Registro já efetuado recentemente (prevenção de duplicidade).")
        else:
            att = AttendanceRecord(
                employee_id=emp.id,
                record_type=rec_type,
                recorded_at=now,
                local_date=local_today(),
                unit_id=terminal.unit_id if terminal else emp.unit_id,
                terminal_id=terminal.id if terminal else None,
                verification_method=method,
                verification_event_id=v_event.id,
                result="accepted",
                source="terminal",
                status="valid",
            )
            db.add(att)
            db.flush()
            att_record_id = att.id

    db.commit()

    return KioskVerifyResponse(
        status="verified",
        message="Identidade verificada com sucesso." if access_decision == "granted" else "Identidade verificada, mas acesso não autorizado para esta localidade.",
        employee_name=emp.full_name,
        employee_id=emp.id,
        attendance_record_id=att_record_id,
        access_decision=access_decision,
        similarity=similarity,
        quality_score=quality_score,
        liveness_passed=liveness_passed,
        reasons=access_reasons,
    )
