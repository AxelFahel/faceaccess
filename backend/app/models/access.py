"""Access control: locations, groups, rules, terminals and events."""
from __future__ import annotations

import uuid
from datetime import date, datetime, time

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Time,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, Timestamps, UUIDPk
from app.models.employee import employee_access_groups


class AccessLocation(UUIDPk, Timestamps, Base):
    __tablename__ = "access_locations"
    unit_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("units.id", ondelete="RESTRICT"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    is_restricted: Mapped[bool] = mapped_column(Boolean, default=False, comment="Exige regra explícita")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class AccessGroup(UUIDPk, Timestamps, Base):
    __tablename__ = "access_groups"
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="RESTRICT"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    employees: Mapped[list["Employee"]] = relationship(  # noqa: F821
        secondary=employee_access_groups, back_populates="access_groups"
    )


class AccessRule(UUIDPk, Timestamps, Base):
    """Rule evaluated independently from biometric verification.

    Subject: an access group OR a single employee (temporary restriction/permission).
    Target: an access location OR a whole unit (null = any location of any unit
    the employee is authorised for).
    ``weekdays``: list of ints Mon=0..Sun=6 (empty = every day).
    Deny rules take precedence over allow rules.
    """

    __tablename__ = "access_rules"
    name: Mapped[str] = mapped_column(String(200))
    access_group_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("access_groups.id", ondelete="CASCADE"), index=True)
    employee_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), index=True)
    access_location_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("access_locations.id", ondelete="CASCADE"))
    unit_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("units.id", ondelete="CASCADE"))
    effect: Mapped[str] = mapped_column(String(10), default="allow")  # allow | deny
    weekdays: Mapped[list] = mapped_column(JSON, default=list)
    start_time: Mapped[time | None] = mapped_column(Time)
    end_time: Mapped[time | None] = mapped_column(Time)
    valid_from: Mapped[date | None] = mapped_column(Date)
    valid_until: Mapped[date | None] = mapped_column(Date)
    required_profile: Mapped[str | None] = mapped_column(String(40))
    reason: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class TerminalStatus:
    PENDING = "pending_activation"
    ACTIVE = "active"
    INACTIVE = "inactive"
    REVOKED = "revoked"


class Terminal(UUIDPk, Timestamps, Base):
    __tablename__ = "terminals"
    code: Mapped[str] = mapped_column(String(40), unique=True, comment="Identificador único legível")
    name: Mapped[str] = mapped_column(String(200))
    unit_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("units.id", ondelete="RESTRICT"), index=True)
    access_location_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("access_locations.id", ondelete="SET NULL"))
    location_description: Mapped[str | None] = mapped_column(String(300))
    terminal_type: Mapped[str] = mapped_column(String(20), default="attendance")  # attendance|access|hybrid
    status: Mapped[str] = mapped_column(String(30), default=TerminalStatus.PENDING, index=True)
    allowed_operations: Mapped[list] = mapped_column(JSON, default=lambda: ["attendance", "pin_fallback"])
    activation_code_hash: Mapped[str | None] = mapped_column(String(64))
    activation_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    credential_prefix: Mapped[str | None] = mapped_column(String(16), index=True)
    credential_hash: Mapped[str | None] = mapped_column(String(64))
    credential_issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    credential_revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_ip: Mapped[str | None] = mapped_column(String(64))
    app_version: Mapped[str | None] = mapped_column(String(40))


class VerificationEvent(UUIDPk, Base):
    """Outcome of a 1:1 verification attempt. Never contains images or templates."""

    __tablename__ = "verification_events"
    __table_args__ = (Index("ix_verification_events_created", "created_at"),)
    employee_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("employees.id", ondelete="SET NULL"), index=True)
    terminal_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("terminals.id", ondelete="SET NULL"), index=True)
    enrollment_id: Mapped[uuid.UUID | None] = mapped_column()
    identifier_type: Mapped[str] = mapped_column(String(20))  # registration|badge|qr
    method: Mapped[str] = mapped_column(String(20))  # face|pin|manual
    outcome: Mapped[str] = mapped_column(String(30), index=True)
    similarity: Mapped[float | None] = mapped_column(Float)
    quality_score: Mapped[float | None] = mapped_column(Float)
    liveness_score: Mapped[float | None] = mapped_column(Float)
    liveness_passed: Mapped[bool | None] = mapped_column(Boolean)
    reasons: Mapped[list] = mapped_column(JSON, default=list)
    engine_version: Mapped[str | None] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AccessEvent(UUIDPk, Base):
    __tablename__ = "access_events"
    __table_args__ = (Index("ix_access_events_created", "created_at"),)
    employee_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("employees.id", ondelete="SET NULL"), index=True)
    terminal_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("terminals.id", ondelete="SET NULL"), index=True)
    unit_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("units.id", ondelete="SET NULL"), index=True)
    access_location_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("access_locations.id", ondelete="SET NULL"))
    verification_event_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("verification_events.id", ondelete="SET NULL"))
    decision: Mapped[str] = mapped_column(String(20), index=True)  # granted|denied|review
    reasons: Mapped[list] = mapped_column(JSON, default=list)
    matched_rule_id: Mapped[uuid.UUID | None] = mapped_column()
    device_command: Mapped[str | None] = mapped_column(String(40), comment="Comando simulado ao dispositivo")
    review_status: Mapped[str | None] = mapped_column(String(20))  # pending|approved|rejected
    reviewed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


__all__ = [
    "AccessLocation",
    "AccessGroup",
    "AccessRule",
    "Terminal",
    "TerminalStatus",
    "VerificationEvent",
    "AccessEvent",
]

_ = Integer
