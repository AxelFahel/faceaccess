"""Models for Events, Event Guests and Blocked Persons."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, Timestamps, UUIDPk


class Event(UUIDPk, Timestamps, Base):
    """Event occurring at a specific unit with guest access windows."""
    __tablename__ = "events"

    unit_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("units.id", ondelete="RESTRICT"), index=True)
    name: Mapped[str] = mapped_column(String(200), index=True)
    description: Mapped[str | None] = mapped_column(Text)
    location_name: Mapped[str | None] = mapped_column(String(200))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    early_entry_minutes: Mapped[int] = mapped_column(Integer, default=30)
    late_entry_minutes: Mapped[int] = mapped_column(Integer, default=60)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)

    guests: Mapped[list["EventGuest"]] = relationship(
        back_populates="event", cascade="all, delete-orphan"
    )


class EventGuest(UUIDPk, Timestamps, Base):
    """Guest / Visitor invited to an event (non-employee)."""
    __tablename__ = "event_guests"

    event_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), index=True)
    full_name: Mapped[str] = mapped_column(String(200), index=True)
    identifier: Mapped[str] = mapped_column(String(64), index=True)  # CPF, RG, Document, or Badge
    email: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(40))
    organization_represented: Mapped[str | None] = mapped_column(String(200))
    pin_hash: Mapped[str | None] = mapped_column(String(128))

    biometric_status: Mapped[str] = mapped_column(String(30), default="pending", index=True)
    template_ciphertext: Mapped[bytes | None] = mapped_column()
    template_nonce: Mapped[bytes | None] = mapped_column()
    key_id: Mapped[str | None] = mapped_column(String(32))
    engine_version: Mapped[str | None] = mapped_column(String(32))

    status: Mapped[str] = mapped_column(String(30), default="active", index=True)  # active, attended, cancelled, blocked
    first_access_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_access_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    access_count: Mapped[int] = mapped_column(Integer, default=0)

    event: Mapped["Event"] = relationship(back_populates="guests")


class BlockedPerson(UUIDPk, Timestamps, Base):
    """Administrative blacklist of blocked persons (employees, guests, or external)."""
    __tablename__ = "blocked_persons"

    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    full_name: Mapped[str] = mapped_column(String(200), index=True)
    identifier: Mapped[str] = mapped_column(String(64), index=True)  # CPF, Matricula, RG, etc.
    reason: Mapped[str] = mapped_column(Text)
    blocked_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    blocked_by_name: Mapped[str | None] = mapped_column(String(200))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    blocked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    unblocked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    unblocked_reason: Mapped[str | None] = mapped_column(Text)
