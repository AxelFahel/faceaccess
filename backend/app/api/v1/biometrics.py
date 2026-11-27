"""Biometrics enrollment, revocation, status checking and template lifecycle."""
from __future__ import annotations

import base64
import uuid
from datetime import UTC, datetime

import cv2
import numpy as np
from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import AuthenticatedPrincipal, require_permission
from app.biometrics.engine import get_biometric_engine
from app.core.config import get_settings
from app.core.crypto import (
    biometric_key_ring,
    serialize_template,
    template_aad,
)
from app.core.errors import NotFound, ValidationFailed
from app.db.session import get_db
from app.models.biometric import BiometricEnrollment, EnrollmentStatus
from app.models.employee import BiometricStatus, Employee
from app.schemas.dto import (
    BiometricEnrollmentRequest,
    BiometricEnrollmentResponse,
    MessageResponse,
)
from app.services.audit import AuditService

router = APIRouter(prefix="/biometrics", tags=["Biometria Facial"])


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


@router.post("/enroll", response_model=BiometricEnrollmentResponse)
def enroll_face(
    req: BiometricEnrollmentRequest,
    request: Request,
    principal: AuthenticatedPrincipal = Depends(require_permission("biometrics:enroll")),
    db: Session = Depends(get_db),
):
    s = get_settings()
    emp = db.get(Employee, req.employee_id)
    if not emp:
        raise NotFound("Funcionário não encontrado.")

    engine = get_biometric_engine()

    embeddings: list[np.ndarray] = []
    qualities: list[float] = []
    liveness_scores: list[float] = []

    for idx, b64_img in enumerate(req.images_base64):
        img_bgr = _decode_image(b64_img)
        feature = engine.process_face(img_bgr, check_liveness=s.liveness_enabled)
        if not feature:
            raise ValidationFailed(f"Nenhum rosto detectado na captura #{idx + 1}.")

        if not feature.quality.passed:
            err_msg = "; ".join(feature.quality.errors)
            raise ValidationFailed(f"Qualidade insuficiente na captura #{idx + 1}: {err_msg}")

        if feature.liveness and not feature.liveness.is_real:
            raise ValidationFailed(
                f"Falha na prova de vivacidade na captura #{idx + 1} "
                f"(confiança: {feature.liveness.confidence:.2f})."
            )

        embeddings.append(feature.embedding)
        qualities.append(feature.quality.score)
        if feature.liveness:
            liveness_scores.append(feature.liveness.confidence)

    # Multi-capture consistency check
    if len(embeddings) > 1:
        for i in range(len(embeddings)):
            for j in range(i + 1, len(embeddings)):
                sim = engine.compute_similarity(embeddings[i], embeddings[j])
                if sim < s.enrollment_min_consistency:
                    raise ValidationFailed(
                        f"Inconsistência entre as capturas ({sim:.2f} < {s.enrollment_min_consistency:.2f}). "
                        "Certifique-se de que todas as fotos pertencem à mesma pessoa."
                    )

    # Average and L2-normalize master embedding
    master_emb = np.mean(embeddings, axis=0)
    norm = np.linalg.norm(master_emb)
    if norm > 0:
        master_emb /= norm

    # Inactivate/supersede any prior active enrollments
    prior_enrollments = db.execute(
        select(BiometricEnrollment).where(
            BiometricEnrollment.employee_id == emp.id,
            BiometricEnrollment.status == EnrollmentStatus.ACTIVE,
        )
    ).scalars().all()
    for prior in prior_enrollments:
        prior.status = EnrollmentStatus.SUPERSEDED

    enrollment_id = uuid.uuid4()
    keyring = biometric_key_ring()
    aad = template_aad(str(enrollment_id), str(emp.id), engine.version)
    plaintext_template = serialize_template(master_emb)
    encrypted_blob = keyring.encrypt(plaintext_template, aad)

    now = datetime.now(UTC)
    enrollment = BiometricEnrollment(
        id=enrollment_id,
        employee_id=emp.id,
        status=EnrollmentStatus.ACTIVE,
        template_ciphertext=encrypted_blob.ciphertext,
        template_nonce=encrypted_blob.nonce,
        key_id=encrypted_blob.key_id,
        template_dim=len(master_emb),
        engine_name=engine.name,
        engine_version=engine.version,
        model_info={"version": engine.version},
        quality_score=float(np.mean(qualities)),
        liveness_score=float(np.mean(liveness_scores)) if liveness_scores else None,
        capture_count=len(embeddings),
        purpose="Controle de acesso e verificação presencial voluntária 1:1",
        legal_basis_record_id=req.legal_basis_record_id,
        privacy_notice_id=req.privacy_notice_id,
        notice_acknowledged_at=now,
        enrolled_by_user_id=principal.id,
        enrolled_at=now,
    )
    db.add(enrollment)

    emp.biometric_status = BiometricStatus.ENROLLED
    db.commit()

    AuditService.record(
        db,
        actor_type="user",
        actor_id=str(principal.id),
        actor_label=principal.label,
        action="biometrics:enrolled",
        resource_type="employee",
        resource_id=str(emp.id),
        details={"enrollment_id": str(enrollment_id), "captures": len(embeddings)},
    )

    return BiometricEnrollmentResponse(
        enrollment_id=enrollment.id,
        employee_id=emp.id,
        status=enrollment.status,
        quality_score=enrollment.quality_score or 0.0,
        liveness_score=enrollment.liveness_score,
        capture_count=enrollment.capture_count,
        created_at=enrollment.enrolled_at,
    )


@router.post("/revoke/{employee_id}", response_model=MessageResponse)
def revoke_biometrics(
    employee_id: uuid.UUID,
    reason: str = "Solicitação de revogação de cadastro biométrico",
    principal: AuthenticatedPrincipal = Depends(require_permission("biometrics:revoke")),
    db: Session = Depends(get_db),
):
    emp = db.get(Employee, employee_id)
    if not emp:
        raise NotFound("Funcionário não encontrado.")

    active_enrollments = db.execute(
        select(BiometricEnrollment).where(
            BiometricEnrollment.employee_id == emp.id,
            BiometricEnrollment.status == EnrollmentStatus.ACTIVE,
        )
    ).scalars().all()

    now = datetime.now(UTC)
    for enr in active_enrollments:
        enr.status = EnrollmentStatus.REVOKED
        enr.revoked_at = now
        enr.revoked_by_user_id = principal.id
        enr.revocation_reason = reason
        # Zero/Purge template ciphertext immediately
        enr.template_ciphertext = None
        enr.template_nonce = None
        enr.purged_at = now

    emp.biometric_status = BiometricStatus.REVOKED
    db.commit()

    AuditService.record(
        db,
        actor_type="user",
        actor_id=str(principal.id),
        actor_label=principal.label,
        action="biometrics:revoked",
        resource_type="employee",
        resource_id=str(emp.id),
        details={"reason": reason},
    )

    return MessageResponse(message="Cadastro biométrico revogado com sucesso. Representação biométrica eliminada.")
