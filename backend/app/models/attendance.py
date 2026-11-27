"""Attendance records, adjustments and justifications.

Records are immutable: corrections happen through ``AttendanceAdjustment``
rows (approved by an authorised person) that either void a record or create a
new one with ``source='adjustment'``. Nothing is silently changed.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPk


class RecordType:
    ENTRY = "entry"
    EXIT = "exit"
    BREAK_START = "break_start"
    BREAK_END = "break_end"
    ALL = (ENTRY, EXIT, BREAK_START, BREAK_END)


class AttendanceRecord(UUIDPk, Base):
    __tablename__ = "attendance_records"
    __table_args__ = (
        Index("ix_attendance_employee_time", "employee_id", "recorded_at"),
        Index("ix_attendance_local_date", "local_date"),
    )
    employee_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("employees.id", ondelete="RESTRICT"))
    record_type: Mapped[str] = mapped_column(String(20))
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), comment="Horário do servidor (UTC)")
    local_date: Mapped[date] = mapped_column(Date, comment="Data no fuso configurado")
    unit_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("units.id", ondelete="SET NULL"), index=True)
    terminal_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("terminals.id", ondelete="SET NULL"), index=True)
    verification_method: Mapped[str] = mapped_column(String(20))  # face|pin|manual
    verification_event_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("verification_events.id", ondelete="SET NULL"))
    result: Mapped[str] = mapped_column(String(20), default="accepted")  # accepted|flagged
    source: Mapped[str] = mapped_column(String(20))  # terminal|manual|adjustment
    consistency: Mapped[str] = mapped_column(String(20), default="ok")  # ok|inconsistent
    consistency_reason: Mapped[str | None] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(20), default="valid", index=True)  # valid|voided
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    adjustment_id: Mapped[uuid.UUID | None] = mapped_column()
    voided_by_adjustment_id: Mapped[uuid.UUID | None] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AttendanceAdjustment(UUIDPk, Base):
    __tablename__ = "attendance_adjustments"
    employee_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("employees.id", ondelete="RESTRICT"), index=True)
    adjustment_type: Mapped[str] = mapped_column(String(20))  # add|void
    attendance_record_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("attendance_records.id", ondelete="RESTRICT"))
    requested_record_type: Mapped[str | None] = mapped_column(String(20))
    requested_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reason: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)  # pending|approved|rejected
    requested_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    reviewed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_notes: Mapped[str | None] = mapped_column(Text)
    resulting_record_id: Mapped[uuid.UUID | None] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AttendanceJustification(UUIDPk, Base):
    __tablename__ = "attendance_justifications"
    employee_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("employees.id", ondelete="RESTRICT"), index=True)
    date_from: Mapped[date] = mapped_column(Date)
    date_to: Mapped[date] = mapped_column(Date)
    justification_type: Mapped[str] = mapped_column(String(30))  # absence|late|early_leave|missing_record|other
    description: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    submitted_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    reviewed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


__all__ = ["AttendanceRecord", "AttendanceAdjustment", "AttendanceJustification", "RecordType"]
