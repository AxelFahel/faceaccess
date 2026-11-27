from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    String,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, Timestamps, UUIDPk

employee_access_groups = Table(
    "employee_access_groups",
    Base.metadata,
    Column("employee_id", ForeignKey("employees.id", ondelete="CASCADE"), primary_key=True),
    Column("access_group_id", ForeignKey("access_groups.id", ondelete="CASCADE"), primary_key=True),
)


class EmploymentStatus:
    ACTIVE = "active"
    INACTIVE = "inactive"
    ON_LEAVE = "on_leave"
    TERMINATED = "terminated"
    ALL = (ACTIVE, INACTIVE, ON_LEAVE, TERMINATED)


class BiometricStatus:
    NOT_ENROLLED = "not_enrolled"
    ENROLLED = "enrolled"
    REVOKED = "revoked"
    OPTED_OUT = "opted_out"  # uses non-biometric alternative
    ALL = (NOT_ENROLLED, ENROLLED, REVOKED, OPTED_OUT)


class Employee(UUIDPk, Timestamps, Base):
    """Funcionário. Deliberately does NOT store CPF, home address, birth date,
    gender, race or any data unnecessary for access/attendance control."""

    __tablename__ = "employees"
    __table_args__ = (
        UniqueConstraint("organization_id", "registration_number"),
        UniqueConstraint("organization_id", "badge_code"),
        Index("ix_employees_name_lower", "full_name"),
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="RESTRICT"), index=True)
    unit_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("units.id", ondelete="RESTRICT"), index=True)
    department_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("departments.id", ondelete="SET NULL"), index=True)
    sector_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("sectors.id", ondelete="SET NULL"))
    position_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("positions.id", ondelete="SET NULL"))
    work_schedule_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("work_schedules.id", ondelete="SET NULL"))

    full_name: Mapped[str] = mapped_column(String(200))
    registration_number: Mapped[str] = mapped_column(String(40), comment="Matrícula funcional")
    badge_code: Mapped[str | None] = mapped_column(String(80), comment="Código do crachá/QR funcional")
    email: Mapped[str] = mapped_column(String(254), unique=True)
    phone: Mapped[str | None] = mapped_column(String(30))
    admission_date: Mapped[date | None] = mapped_column(Date)
    employment_status: Mapped[str] = mapped_column(String(20), default=EmploymentStatus.ACTIVE, index=True)
    biometric_status: Mapped[str] = mapped_column(String(20), default=BiometricStatus.NOT_ENROLLED, index=True)
    access_profile: Mapped[str] = mapped_column(String(40), default="standard")
    notes: Mapped[str | None] = mapped_column(Text, comment="Observações administrativas")
    pin_hash: Mapped[str | None] = mapped_column(String(200), comment="Argon2id do PIN (alternativa não biométrica)")
    pin_failed_count: Mapped[int] = mapped_column(default=0)
    pin_locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    anonymized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    access_groups: Mapped[list["AccessGroup"]] = relationship(  # noqa: F821
        secondary=employee_access_groups, back_populates="employees"
    )


class AccessProfile:
    STANDARD = "standard"
    RESTRICTED = "restricted"
    EXTENDED = "extended"
    ALL = (STANDARD, RESTRICTED, EXTENDED)


__all__ = ["Employee", "EmploymentStatus", "BiometricStatus", "AccessProfile", "employee_access_groups"]
