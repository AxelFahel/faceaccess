"""Organizational structure: organizations, units, departments, sectors,
positions, schedules, shifts, holidays and schedule assignments (escalas)."""
from __future__ import annotations

import uuid
from datetime import date, time

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    ForeignKey,
    Integer,
    String,
    Text,
    Time,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, Timestamps, UUIDPk


class Organization(UUIDPk, Timestamps, Base):
    __tablename__ = "organizations"
    name: Mapped[str] = mapped_column(String(200))
    legal_name: Mapped[str | None] = mapped_column(String(250))
    tax_id: Mapped[str | None] = mapped_column(String(32), comment="CNPJ da organização (pessoa jurídica)")
    timezone: Mapped[str] = mapped_column(String(64), default="America/Fortaleza")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Unit(UUIDPk, Timestamps, Base):
    __tablename__ = "units"
    __table_args__ = (UniqueConstraint("organization_id", "code"),)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="RESTRICT"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    code: Mapped[str] = mapped_column(String(40))
    address: Mapped[str | None] = mapped_column(String(300), comment="Endereço comercial da unidade")
    timezone: Mapped[str | None] = mapped_column(String(64))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    organization: Mapped[Organization] = relationship()


class Department(UUIDPk, Timestamps, Base):
    __tablename__ = "departments"
    __table_args__ = (UniqueConstraint("organization_id", "code"),)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="RESTRICT"), index=True)
    unit_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("units.id", ondelete="SET NULL"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    code: Mapped[str] = mapped_column(String(40))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Sector(UUIDPk, Timestamps, Base):
    __tablename__ = "sectors"
    __table_args__ = (UniqueConstraint("department_id", "name"),)
    department_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("departments.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Position(UUIDPk, Timestamps, Base):
    __tablename__ = "positions"
    __table_args__ = (UniqueConstraint("organization_id", "code"),)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="RESTRICT"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    code: Mapped[str] = mapped_column(String(40))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class WorkSchedule(UUIDPk, Timestamps, Base):
    """Jornada de trabalho.

    ``days`` is a list of ``{"weekday": 0-6 (Mon=0), "start": "08:00", "end": "17:00",
    "break_minutes": 60}``. Weekdays absent from the list are days off.
    """

    __tablename__ = "work_schedules"
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="RESTRICT"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    days: Mapped[list] = mapped_column(JSON, default=list)
    tolerance_minutes: Mapped[int] = mapped_column(Integer, default=10)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class WorkShift(UUIDPk, Timestamps, Base):
    """Turno (ex.: manhã, tarde, noturno)."""

    __tablename__ = "work_shifts"
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="RESTRICT"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    start_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time] = mapped_column(Time)
    break_minutes: Mapped[int] = mapped_column(Integer, default=0)
    crosses_midnight: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Holiday(UUIDPk, Timestamps, Base):
    __tablename__ = "holidays"
    __table_args__ = (UniqueConstraint("organization_id", "unit_id", "date"),)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="RESTRICT"), index=True)
    unit_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("units.id", ondelete="CASCADE"))
    date: Mapped[date] = mapped_column(Date, index=True)
    name: Mapped[str] = mapped_column(String(200))
    recurring: Mapped[bool] = mapped_column(Boolean, default=False)


class ScheduleAssignment(UUIDPk, Timestamps, Base):
    """Escala: vincula funcionário a jornada/turno num intervalo de datas."""

    __tablename__ = "schedule_assignments"
    employee_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), index=True)
    work_schedule_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("work_schedules.id", ondelete="RESTRICT"))
    work_shift_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("work_shifts.id", ondelete="RESTRICT"))
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text)
