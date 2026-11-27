"""Biometric data — logically separated in the ``biometric`` PostgreSQL schema.

Templates are stored ONLY as AES-256-GCM ciphertext. No image is ever stored.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import BIOMETRIC_SCHEMA, Base, UUIDPk


class EnrollmentStatus:
    ACTIVE = "active"
    REVOKED = "revoked"
    SUPERSEDED = "superseded"


class BiometricEnrollment(UUIDPk, Base):
    __tablename__ = "biometric_enrollments"
    __table_args__ = (
        Index(
            "uq_biometric_enrollments_one_active",
            "employee_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
    )
    employee_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(20), default=EnrollmentStatus.ACTIVE)
    # Encrypted template (nullable after purge)
    template_ciphertext: Mapped[bytes | None] = mapped_column(LargeBinary)
    template_nonce: Mapped[bytes | None] = mapped_column(LargeBinary)
    key_id: Mapped[str | None] = mapped_column(String(40))
    template_dim: Mapped[int] = mapped_column(Integer)
    # Provenance
    engine_name: Mapped[str] = mapped_column(String(40))
    engine_version: Mapped[str] = mapped_column(String(120))
    model_info: Mapped[dict] = mapped_column(JSON, default=dict)
    quality_score: Mapped[float | None] = mapped_column(Float)
    liveness_score: Mapped[float | None] = mapped_column(Float)
    capture_count: Mapped[int] = mapped_column(Integer)
    # Legal
    purpose: Mapped[str] = mapped_column(Text)
    legal_basis_record_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("legal_basis_records.id", ondelete="RESTRICT"))
    privacy_notice_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("privacy_notices.id", ondelete="RESTRICT"))
    notice_acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Lifecycle
    enrolled_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    enrolled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    revocation_reason: Mapped[str | None] = mapped_column(Text)
    purged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


__all__ = ["BiometricEnrollment", "EnrollmentStatus"]
