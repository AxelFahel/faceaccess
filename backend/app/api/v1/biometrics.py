"""Biometrics enrollment, revocation, status checking and template lifecycle."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

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
from app.core.errors import Forbidden, NotFound, ValidationFailed
from app.db.session import get_db
from app.models.biometric import BiometricEnrollment, EnrollmentStatus
from app.models.employee import BiometricStatus, Employee
from app.models.privacy import LegalBasisRecord
from app.schemas.dto import (
    BiometricCaptureRequest,
    BiometricEnrollmentRequest,
    BiometricEnrollmentResponse,
    MessageResponse,
)
from app.services.audit import AuditService
from app.services.enrollment import build_enrollment, capture_feedback, decode_image as _decode_image
from app.services.enrollment_policy import scoped_employee as _scoped_employee, eligible_employee

router = APIRouter(prefix="/biometrics", tags=["Biometria Facial"])


@router.get("/enrollment-options")
def enrollment_options(
    principal: AuthenticatedPrincipal = Depends(require_permission("biometrics:enroll")),
    db: Session = Depends(get_db),
):
    bases = db.execute(select(LegalBasisRecord).where(
        LegalBasisRecord.organization_id == principal.organization_id,
        LegalBasisRecord.is_active == True,
    ).order_by(LegalBasisRecord.created_at)).scalars().all()
    return {
        "required_captures": get_settings().enrollment_captures,
        "legal_bases": [{"id": str(b.id)} for b in bases],
    }


@router.post("/capture-check")
def check_capture(
    req: BiometricCaptureRequest,
    principal: AuthenticatedPrincipal = Depends(require_permission("biometrics:enroll")),
    db: Session = Depends(get_db),
):
    """Transient guidance only; enrollment independently repeats every check."""
    eligible_employee(_scoped_employee(db, req.employee_id, principal))
    s = get_settings()
    feature = get_biometric_engine().process_face(_decode_image(req.image_base64), check_liveness=True, include_embedding=False)
    return capture_feedback(feature, s.enrollment_captures)


@router.post("/enroll", response_model=BiometricEnrollmentResponse)
def enroll_face(
    req: BiometricEnrollmentRequest,
    request: Request,
    principal: AuthenticatedPrincipal = Depends(require_permission("biometrics:enroll")),
    db: Session = Depends(get_db),
):
    s = get_settings()
    emp = _scoped_employee(db, req.employee_id, principal)
    eligible_employee(emp)
    basis = db.get(LegalBasisRecord, req.legal_basis_record_id)
    if not basis or not basis.is_active or basis.organization_id != emp.organization_id:
        raise ValidationFailed("Base legal ativa não encontrada para esta organização.")

    engine = get_biometric_engine()

    result = build_enrollment(req.images_base64, engine, s)
    master_emb = result.template

    # Inactivate/supersede any prior active enrollments
    prior_enrollments = db.execute(
        select(BiometricEnrollment).where(
            BiometricEnrollment.employee_id == emp.id,
            BiometricEnrollment.status == EnrollmentStatus.ACTIVE,
        )
    ).scalars().all()
    for prior in prior_enrollments:
        prior.status = EnrollmentStatus.SUPERSEDED
        prior.template_ciphertext = None
        prior.template_nonce = None
        prior.purged_at = datetime.now(UTC)

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
        quality_score=result.quality,
        liveness_score=result.liveness,
        capture_count=result.capture_count,
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
        details={"enrollment_id": str(enrollment_id), "captures": result.capture_count},
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
    emp = _scoped_employee(db, employee_id, principal)

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
