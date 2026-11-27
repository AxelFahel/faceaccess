"""Privacy / LGPD support entities, audit log and system settings."""
from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, Timestamps, UUIDPk


class PrivacyNotice(UUIDPk, Timestamps, Base):
    __tablename__ = "privacy_notices"
    __table_args__ = (UniqueConstraint("organization_id", "version"),)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="RESTRICT"))
    version: Mapped[str] = mapped_column(String(20))
    title: Mapped[str] = mapped_column(String(200))
    content: Mapped[str] = mapped_column(Text)
    effective_from: Mapped[date] = mapped_column(Date)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))


class LegalBasisRecord(UUIDPk, Timestamps, Base):
    """Registro de operação de tratamento + base legal (LGPD art. 7º / art. 11).

    The system does NOT presume consent; the controller must choose and justify
    the hypothesis with legal counsel.
    """

    __tablename__ = "legal_basis_records"
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="RESTRICT"))
    processing_activity: Mapped[str] = mapped_column(String(250))
    data_categories: Mapped[str] = mapped_column(Text)
    legal_basis: Mapped[str] = mapped_column(String(60))
    legal_basis_description: Mapped[str] = mapped_column(Text)
    purpose: Mapped[str] = mapped_column(Text)
    retention_summary: Mapped[str | None] = mapped_column(Text)
    dpia_reference: Mapped[str | None] = mapped_column(String(250))
    approved_by: Mapped[str | None] = mapped_column(String(200))
    approved_at: Mapped[date | None] = mapped_column(Date)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class DataSubjectRequest(UUIDPk, Timestamps, Base):
    __tablename__ = "data_subject_requests"
    employee_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("employees.id", ondelete="SET NULL"), index=True)
    request_type: Mapped[str] = mapped_column(String(30))  # access|correction|deletion|revocation|portability|information|objection
    description: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="open", index=True)  # open|in_progress|completed|rejected
    opened_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    assigned_to_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    response: Mapped[str | None] = mapped_column(Text)
    due_date: Mapped[date | None] = mapped_column(Date)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RetentionPolicy(UUIDPk, Timestamps, Base):
    __tablename__ = "retention_policies"
    data_category: Mapped[str] = mapped_column(String(60), unique=True)
    description: Mapped[str] = mapped_column(Text)
    retention_days: Mapped[int] = mapped_column(Integer)
    action: Mapped[str] = mapped_column(String(20))  # delete|anonymize|purge_template
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_run_affected: Mapped[int | None] = mapped_column(Integer)


class SecurityIncident(UUIDPk, Timestamps, Base):
    __tablename__ = "security_incidents"
    title: Mapped[str] = mapped_column(String(250))
    description: Mapped[str] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(String(20))  # low|medium|high|critical
    status: Mapped[str] = mapped_column(String(20), default="open")  # open|investigating|contained|closed
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    affected_data: Mapped[str | None] = mapped_column(Text)
    actions_taken: Mapped[str | None] = mapped_column(Text)
    authority_notified: Mapped[bool] = mapped_column(Boolean, default=False, comment="Comunicação à ANPD")
    subjects_notified: Mapped[bool] = mapped_column(Boolean, default=False)
    reported_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AuditLog(UUIDPk, Base):
    """Tamper-evident audit trail (hash chain + HMAC).

    The application DB role has INSERT/SELECT only on this table (no UPDATE/DELETE).
    Never stores passwords, tokens, images or biometric templates.
    """

    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_created", "created_at"),
        Index("ix_audit_logs_resource", "resource_type", "resource_id"),
        Index("ix_audit_logs_action", "action"),
    )
    seq: Mapped[int | None] = mapped_column(BigInteger, Identity(always=True), primary_key=False, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    actor_type: Mapped[str] = mapped_column(String(20))  # user|terminal|system|anonymous
    actor_id: Mapped[str | None] = mapped_column(String(64))
    actor_label: Mapped[str | None] = mapped_column(String(254))
    action: Mapped[str] = mapped_column(String(80))
    resource_type: Mapped[str | None] = mapped_column(String(60))
    resource_id: Mapped[str | None] = mapped_column(String(64))
    result: Mapped[str] = mapped_column(String(20))  # success|failure|denied
    ip_address: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(300))
    request_id: Mapped[str | None] = mapped_column(String(64))
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    prev_hash: Mapped[str] = mapped_column(String(64))
    hash: Mapped[str] = mapped_column(String(64))


class SystemSetting(UUIDPk, Base):
    __tablename__ = "system_settings"
    key: Mapped[str] = mapped_column(String(100), unique=True)
    value: Mapped[dict | list | str | int | float | bool | None] = mapped_column(JSON)
    description: Mapped[str | None] = mapped_column(Text)
    updated_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


__all__ = [
    "PrivacyNotice",
    "LegalBasisRecord",
    "DataSubjectRequest",
    "RetentionPolicy",
    "SecurityIncident",
    "AuditLog",
    "SystemSetting",
]
