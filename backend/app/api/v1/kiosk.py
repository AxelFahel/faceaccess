"""Kiosk / Terminal Mode: 1:1 facial verification & attendance registration."""
from __future__ import annotations

import base64
import uuid
from datetime import UTC, datetime, time, timedelta

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
from app.core.timeutil import local_today, to_local, utcnow
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
from app.models.guest import BlockedPerson, Event, EventGuest
from app.models.organization import ScheduleException, WorkSchedule
from app.schemas.dto import KioskCaptureRequest, KioskVerifyRequest, KioskVerifyResponse
from app.services.camera_guidance import camera_guidance
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
    """Compare once-extracted features with active enrollments (employees and event guests) in this terminal's unit."""
    keyring = biometric_key_ring()
    candidates = {}

    # 1. Employees in this unit
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
            continue
        if np.isfinite(score) and (emp.id not in candidates or score > candidates[emp.id][0]):
            candidates[emp.id] = (score, "employee", emp, enrollment)

    # 2. Event Guests for active events in this unit
    guest_rows = db.execute(
        select(EventGuest, Event)
        .join(Event, Event.id == EventGuest.event_id)
        .where(
            Event.unit_id == terminal.unit_id,
            Event.is_active == True,
            EventGuest.biometric_status == "enrolled",
            EventGuest.status.in_(["active", "attended"]),
        )
    ).all()
    for guest, event in guest_rows:
        if (guest.engine_version != engine.version or not guest.key_id
                or not guest.template_nonce or not guest.template_ciphertext):
            continue
        try:
            vector = deserialize_template(keyring.decrypt(
                EncryptedBlob(guest.key_id, guest.template_nonce, guest.template_ciphertext),
                template_aad(str(guest.id), str(guest.event_id), guest.engine_version),
            ))
            if vector.shape != feature.embedding.shape:
                continue
            score = float(engine.compute_similarity(vector, feature.embedding))
        except Exception:
            continue
        if np.isfinite(score) and (guest.id not in candidates or score > candidates[guest.id][0]):
            candidates[guest.id] = (score, "guest", guest, event)

    ranked = sorted(candidates.values(), key=lambda item: item[0], reverse=True)
    if not ranked or ranked[0][0] < settings.match_threshold:
        return None, KioskVerifyResponse(
            status="rejected", message="Rosto não reconhecido nesta unidade. Procure a portaria.", retryable=True,
        )
    if len(ranked) > 1 and ranked[0][0] - ranked[1][0] < settings.identification_min_margin:
        return None, KioskVerifyResponse(
            status="inconclusive", message="Não foi possível distinguir a identidade com segurança. Tente novamente.",
        )
    return ranked[0], None


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


@router.post("/capture-check")
def kiosk_capture_check(
    req: KioskCaptureRequest,
    terminal_auth: AuthenticatedPrincipal = Depends(get_current_terminal),
    db: Session = Depends(get_db),
):
    terminal = db.get(Terminal, terminal_auth.id)
    if not terminal or req.operation_type not in terminal.allowed_operations:
        raise Forbidden("Operação não permitida para este terminal.")
    image = _decode_image(req.image_base64)
    feature = get_biometric_engine().process_face(image, check_liveness=True, include_embedding=False)
    return camera_guidance(feature, image.shape[1], image.shape[0])


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
    similarity: float | None = None
    quality_score: float | None = None
    liveness_passed: bool | None = None
    verification_outcome = "inconclusive"
    reasons: list[str] = []

    if req.method == "face" and not ident:
        if not terminal or not req.image_base64:
            raise ValidationFailed("Captura facial e terminal ativo são obrigatórios.")
        engine = get_biometric_engine()
        feature = engine.process_face(_decode_image(req.image_base64), check_liveness=True)
        problem = _capture_problem(feature)
        if problem:
            return problem
        candidate, problem = _identify_in_unit(db, terminal, feature, engine, s)
        if problem:
            return problem

        sim_score, kind, person, extra = candidate

        # Blacklist check
        clean_ident = person.registration_number if kind == "employee" else person.identifier
        badge = person.badge_code if kind == "employee" else None
        blocked_q = select(BlockedPerson).where(
            BlockedPerson.is_active == True,
            (BlockedPerson.identifier == clean_ident) |
            (BlockedPerson.full_name.ilike(person.full_name))
        )
        if badge:
            blocked_q = select(BlockedPerson).where(
                BlockedPerson.is_active == True,
                (BlockedPerson.identifier == clean_ident) |
                (BlockedPerson.identifier == badge) |
                (BlockedPerson.full_name.ilike(person.full_name))
            )
        blocked = db.execute(blocked_q.order_by(BlockedPerson.blocked_at.desc())).scalars().first()
        if blocked:
            return KioskVerifyResponse(
                status="rejected",
                access_decision="denied",
                message=f"ACESSO BLOQUEADO: {blocked.reason}",
                employee_name=person.full_name,
                similarity=sim_score,
                quality_score=feature.quality.score if feature else None,
                liveness_passed=feature.liveness.is_real if (feature and feature.liveness) else None,
                reasons=[f"Bloqueio administrativo: {blocked.reason}"],
                retryable=False,
            )

        # If Guest: validate event window
        if kind == "guest":
            event = extra
            starts_at = event.starts_at if event.starts_at.tzinfo else event.starts_at.replace(tzinfo=UTC)
            ends_at = event.ends_at if event.ends_at.tzinfo else event.ends_at.replace(tzinfo=UTC)
            early_window = starts_at - timedelta(minutes=event.early_entry_minutes)
            late_window = ends_at + timedelta(minutes=event.late_entry_minutes)

            if now < early_window:
                start_str = starts_at.strftime("%H:%M")
                early_str = early_window.strftime("%H:%M")
                return KioskVerifyResponse(
                    status="rejected",
                    access_decision="denied",
                    message=f"Acesso não liberado. O evento '{event.name}' inicia às {start_str} (entrada permitida a partir das {early_str}).",
                    employee_name=f"{person.full_name} (Convidado)",
                    similarity=sim_score,
                    reasons=["Horário de entrada do evento ainda não iniciado"],
                    retryable=False,
                )
            elif now > late_window:
                end_str = ends_at.strftime("%H:%M")
                return KioskVerifyResponse(
                    status="rejected",
                    access_decision="denied",
                    message=f"Acesso não liberado. O evento '{event.name}' encerrou às {end_str}.",
                    employee_name=f"{person.full_name} (Convidado)",
                    similarity=sim_score,
                    reasons=["Horário do evento já expirado"],
                    retryable=False,
                )
            else:
                if not person.first_access_at:
                    person.first_access_at = now
                person.last_access_at = now
                person.access_count += 1
                person.status = "attended"

                v_event = VerificationEvent(
                    employee_id=None,
                    terminal_id=terminal.id if terminal else None,
                    identifier_type="face",
                    method="face",
                    outcome="verified",
                    similarity=sim_score,
                    quality_score=feature.quality.score if feature else None,
                    liveness_score=feature.liveness.confidence if (feature and feature.liveness) else None,
                    liveness_passed=feature.liveness.is_real if (feature and feature.liveness) else None,
                    reasons=[f"Convidado do evento '{event.name}'"],
                    engine_version=engine.version,
                )
                db.add(v_event)
                db.flush()

                a_event = AccessEvent(
                    employee_id=None,
                    terminal_id=terminal.id if terminal else None,
                    unit_id=terminal.unit_id if terminal else None,
                    verification_event_id=v_event.id,
                    decision="granted",
                    reasons=[f"Convidado autorizado para o evento '{event.name}'"],
                    device_command="UNLOCK_RELAY",
                )
                db.add(a_event)
                db.commit()

                return KioskVerifyResponse(
                    status="verified",
                    access_decision="granted",
                    message=f"CONVIDADO AUTORIZADO — Evento: {event.name}",
                    employee_name=f"{person.full_name} (Convidado)",
                    similarity=sim_score,
                    quality_score=feature.quality.score if feature else None,
                    liveness_passed=feature.liveness.is_real if (feature and feature.liveness) else None,
                    reasons=[f"Acesso liberado para o evento '{event.name}'"],
                )

        emp = person
        selected_enrollment = extra
        similarity = sim_score
        quality_score = feature.quality.score if feature else None
        liveness_passed = feature.liveness.is_real if (feature and feature.liveness) else None
        verification_outcome = "verified"

    else:
        if not ident:
            raise ValidationFailed("Informe a identificação para verificação.")

        # Check Blacklist by identifier
        blocked = db.execute(
            select(BlockedPerson).where(
                BlockedPerson.is_active == True,
                BlockedPerson.identifier == ident.upper(),
            ).order_by(BlockedPerson.blocked_at.desc())
        ).scalars().first()
        if blocked:
            return KioskVerifyResponse(
                status="rejected",
                access_decision="denied",
                message=f"ACESSO BLOQUEADO: {blocked.reason}",
                reasons=[f"Bloqueio administrativo: {blocked.reason}"],
                retryable=False,
            )

        emp = db.execute(
            select(Employee).where(
                (Employee.registration_number == ident) | (Employee.badge_code == ident)
            )
        ).scalar_one_or_none()

        if not emp:
            guest = db.execute(
                select(EventGuest).where(
                    EventGuest.identifier == ident.upper(),
                    EventGuest.status.in_(["active", "attended"]),
                ).order_by(EventGuest.created_at.desc())
            ).scalars().first()
            if guest:
                # 1. BIOMETRICS IS MANDATORY FOR GUESTS
                if guest.biometric_status != "enrolled" or not guest.template_ciphertext or not guest.key_id:
                    return KioskVerifyResponse(
                        status="rejected",
                        access_decision="denied",
                        message=f"Acesso negado: biometria facial obrigatória não cadastrada para o convidado {guest.full_name}. Realize o cadastro na recepção/portaria.",
                        employee_name=f"{guest.full_name} (Convidado)",
                        reasons=["Biometria facial obrigatória não cadastrada"],
                        retryable=False,
                    )

                # Guests must be verified by facial recognition, not PIN-only
                if req.method == "pin":
                    return KioskVerifyResponse(
                        status="rejected",
                        access_decision="denied",
                        message="O acesso de convidados exige validação biométrica facial no totem.",
                        employee_name=f"{guest.full_name} (Convidado)",
                        reasons=["Reconhecimento facial biométrico obrigatório para convidados"],
                        retryable=False,
                    )

                # Face verification against guest's enrolled template
                if not req.image_base64:
                    raise ValidationFailed("Captura facial obrigatória para verificação do convidado.")

                engine = get_biometric_engine()
                if feature is None:
                    feature = engine.process_face(_decode_image(req.image_base64), check_liveness=s.liveness_enabled)
                if not feature:
                    return KioskVerifyResponse(
                        status="rejected",
                        message="Nenhum rosto detectado na câmera.",
                        employee_name=f"{guest.full_name} (Convidado)",
                        retryable=True,
                    )

                problem = _capture_problem(feature, require_liveness=s.liveness_enabled)
                if problem:
                    problem.access_decision = "denied"
                    return problem
                if guest.engine_version != engine.version:
                    return KioskVerifyResponse(status="rejected", access_decision="denied",
                                               message="Cadastro facial desatualizado. Procure a recepção.")
                keyring = biometric_key_ring()
                aad = template_aad(str(guest.id), str(guest.event_id), guest.engine_version)
                try:
                    pt = keyring.decrypt(
                        EncryptedBlob(guest.key_id, guest.template_nonce, guest.template_ciphertext),
                        aad,
                    )
                    guest_vec = deserialize_template(pt)
                except Exception:
                    return KioskVerifyResponse(
                        status="rejected",
                        message="Falha de integridade no cadastro biométrico do convidado.",
                        employee_name=f"{guest.full_name} (Convidado)",
                    )

                similarity = float(engine.compute_similarity(guest_vec, feature.embedding))
                if similarity < s.match_threshold:
                    return KioskVerifyResponse(
                        status="rejected",
                        access_decision="denied",
                        message=f"Rosto não confere com o cadastro biométrico de {guest.full_name}.",
                        employee_name=f"{guest.full_name} (Convidado)",
                        similarity=similarity,
                        reasons=[f"Similaridade facial insuficiente ({similarity:.2f} < {s.match_threshold:.2f})"],
                        retryable=False,
                    )

                event = db.get(Event, guest.event_id)
                if not event or not event.is_active or (terminal and event.unit_id != terminal.unit_id):
                    return KioskVerifyResponse(
                        status="rejected",
                        access_decision="denied",
                        message="Evento inativo ou não autorizado nesta unidade.",
                        employee_name=f"{guest.full_name} (Convidado)",
                    )
                starts_at = event.starts_at if event.starts_at.tzinfo else event.starts_at.replace(tzinfo=UTC)
                ends_at = event.ends_at if event.ends_at.tzinfo else event.ends_at.replace(tzinfo=UTC)
                early_window = starts_at - timedelta(minutes=event.early_entry_minutes)
                late_window = ends_at + timedelta(minutes=event.late_entry_minutes)
                if now < early_window:
                    return KioskVerifyResponse(
                        status="rejected",
                        access_decision="denied",
                        message=f"Acesso não liberado. O evento '{event.name}' inicia às {starts_at.strftime('%H:%M')}.",
                        employee_name=f"{guest.full_name} (Convidado)",
                        similarity=similarity,
                    )
                elif now > late_window:
                    return KioskVerifyResponse(
                        status="rejected",
                        access_decision="denied",
                        message=f"Acesso não liberado. O evento '{event.name}' encerrou às {ends_at.strftime('%H:%M')}.",
                        employee_name=f"{guest.full_name} (Convidado)",
                        similarity=similarity,
                    )
                else:
                    if not guest.first_access_at:
                        guest.first_access_at = now
                    guest.last_access_at = now
                    guest.access_count += 1
                    guest.status = "attended"
                    db.commit()
                    return KioskVerifyResponse(
                        status="verified",
                        access_decision="granted",
                        message=f"CONVIDADO AUTORIZADO — Evento: {event.name}",
                        employee_name=f"{guest.full_name} (Convidado)",
                        similarity=similarity,
                    )

            return KioskVerifyResponse(
                status="rejected",
                message="Identificação não encontrada.",
                reasons=["Funcionário ou convidado não cadastrado"],
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
        if not ident:
            # Already matched, similarity and liveness checked in Step 2 automatic identification
            pass
        else:
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
    final_message = "Identidade verificada com sucesso."

    # Check terminal / unit match
    if terminal and emp.unit_id != terminal.unit_id:
        access_decision = "denied"
        access_reasons.append("Funcionário alocado em outra unidade")
        final_message = "Acesso negado: funcionário alocado em outra unidade."

    # Check Work Schedule & Working Hours (Período de Trabalho e Exceções Registradas)
    if access_decision == "granted" and emp.work_schedule_id:
        work_sched = db.get(WorkSchedule, emp.work_schedule_id)
        if work_sched and work_sched.is_active:
            local_now = to_local(now)
            weekday = local_now.weekday()  # Mon=0 .. Sun=6
            day_cfg = None
            for d in (work_sched.days or []):
                if d.get("weekday") == weekday:
                    day_cfg = d
                    break

            within_schedule = False
            schedule_detail = ""
            if not day_cfg:
                schedule_detail = "Hoje é dia de folga (sem expediente previsto)"
            else:
                try:
                    start_str = day_cfg.get("start", "08:00")
                    end_str = day_cfg.get("end", "17:00")
                    sh, sm = [int(p) for p in start_str.split(":")]
                    eh, em = [int(p) for p in end_str.split(":")]
                    tol = work_sched.tolerance_minutes or 15

                    sched_start_dt = datetime.combine(local_now.date(), time(sh, sm)) - timedelta(minutes=tol)
                    sched_end_dt = datetime.combine(local_now.date(), time(eh, em)) + timedelta(minutes=tol * 2)

                    current_dt = datetime.combine(local_now.date(), local_now.time())
                    if sched_start_dt <= current_dt <= sched_end_dt:
                        within_schedule = True
                    else:
                        schedule_detail = f"Fora do horário de trabalho ({start_str} às {end_str})"
                except Exception:
                    within_schedule = True

            if not within_schedule:
                # Check for active ScheduleException
                exc = db.execute(
                    select(ScheduleException).where(
                        ScheduleException.employee_id == emp.id,
                        ScheduleException.is_active == True,
                        ScheduleException.starts_at <= now,
                        ScheduleException.ends_at >= now,
                    ).order_by(ScheduleException.starts_at.desc())
                ).scalars().first()

                if exc:
                    if not exc.used_at:
                        exc.used_at = now
                    exc.access_count += 1
                    access_reasons.append(f"Acesso liberado por exceção: {exc.reason} (Autorizado por: {exc.authorized_by_name or 'Gestão'})")
                    final_message = f"ACESSO LIBERADO POR EXCEÇÃO REGISTRADA — {exc.reason}"
                    AuditService.record(
                        db,
                        actor_type="terminal",
                        actor_id=str(terminal.id) if terminal else None,
                        actor_label=terminal.name if terminal else "Totem",
                        action="security:access_by_schedule_exception",
                        resource_type="schedule_exception",
                        resource_id=str(exc.id),
                        details={"employee_name": emp.full_name, "reason": exc.reason},
                    )
                else:
                    access_decision = "denied"
                    rejection_msg = f"Acesso não permitido fora do horário de trabalho. {schedule_detail}. Nenhuma exceção registrada."
                    access_reasons.append(rejection_msg)
                    final_message = rejection_msg

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
        status="verified" if access_decision == "granted" else "rejected",
        message=final_message,
        employee_name=emp.full_name,
        employee_id=emp.id,
        attendance_record_id=att_record_id,
        access_decision=access_decision,
        similarity=similarity,
        quality_score=quality_score,
        liveness_passed=liveness_passed,
        reasons=access_reasons,
    )
