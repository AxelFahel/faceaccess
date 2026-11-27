"""Privacy and LGPD compliance management API routes."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import AuthenticatedPrincipal, require_permission
from app.db.session import get_db
from app.models.privacy import AuditLog, DataSubjectRequest, LegalBasisRecord, PrivacyNotice
from app.services.audit import AuditService

router = APIRouter(prefix="/privacy", tags=["Privacidade & LGPD"])


@router.get("/legal-basis")
def list_legal_bases(
    principal: AuthenticatedPrincipal = Depends(require_permission("privacy:read")),
    db: Session = Depends(get_db),
):
    return db.execute(select(LegalBasisRecord).where(LegalBasisRecord.is_active == True)).scalars().all()


@router.get("/notices")
def list_privacy_notices(
    principal: AuthenticatedPrincipal = Depends(require_permission("privacy:read")),
    db: Session = Depends(get_db),
):
    return db.execute(select(PrivacyNotice).where(PrivacyNotice.is_active == True)).scalars().all()


@router.get("/audit-logs")
def list_audit_logs(
    limit: int = 50,
    principal: AuthenticatedPrincipal = Depends(require_permission("audit:read")),
    db: Session = Depends(get_db),
):
    return db.execute(
        select(AuditLog).order_by(AuditLog.seq.desc()).limit(limit)
    ).scalars().all()
