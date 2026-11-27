"""Events and Guest Management API."""
from __future__ import annotations

import base64
import uuid
from datetime import UTC, datetime

import cv2
import numpy as np
from fastapi import APIRouter, Depends, Query, Request
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
from app.core.security import hash_secret
from app.core.timeutil import utcnow
from app.db.session import get_db
from app.models.guest import Event, EventGuest
from app.models.organization import Unit
from app.schemas.dto import (
    EventCreate,
    EventGuestCreate,
    EventGuestRead,
    EventRead,
    GuestBiometricEnroll,
    MessageResponse,
)
from app.services.audit import AuditService

router = APIRouter(prefix="/events", tags=["Eventos e Convidados"])


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


@router.get("", response_model=list[EventRead])
def list_events(
    unit_id: uuid.UUID | None = None,
    principal: AuthenticatedPrincipal = Depends(require_permission("org:read")),
    db: Session = Depends(get_db),
):
    query = select(Event).order_by(Event.starts_at.desc())
    if unit_id:
        query = query.where(Event.unit_id == unit_id)
    events = db.execute(query).scalars().all()

    result = []
    for ev in events:
        read = EventRead.model_validate(ev)
        read.guest_count = len(ev.guests)
        result.append(read)
    return result


@router.post("", response_model=EventRead)
def create_event(
    req: EventCreate,
    principal: AuthenticatedPrincipal = Depends(require_permission("org:manage")),
    db: Session = Depends(get_db),
):
    unit = db.get(Unit, req.unit_id)
    if not unit:
        raise NotFound("Unidade não encontrada.")
    if req.ends_at <= req.starts_at:
        raise ValidationFailed("O horário de término deve ser posterior ao horário de início.")

    event = Event(
        unit_id=req.unit_id,
        name=req.name,
        description=req.description,
        location_name=req.location_name,
        starts_at=req.starts_at,
        ends_at=req.ends_at,
        early_entry_minutes=req.early_entry_minutes,
        late_entry_minutes=req.late_entry_minutes,
        is_active=True,
    )
    db.add(event)
    db.commit()
    db.refresh(event)

    AuditService.record(
        db,
        actor_type="user",
        actor_id=str(principal.id),
        actor_label=principal.label,
        action="event:created",
        resource_type="event",
        resource_id=str(event.id),
        details={"name": event.name, "starts_at": event.starts_at.isoformat()},
    )

    return EventRead.model_validate(event)


@router.get("/{event_id}", response_model=EventRead)
def get_event(
    event_id: uuid.UUID,
    principal: AuthenticatedPrincipal = Depends(require_permission("org:read")),
    db: Session = Depends(get_db),
):
    event = db.get(Event, event_id)
    if not event:
        raise NotFound("Evento não encontrado.")
    read = EventRead.model_validate(event)
    read.guest_count = len(event.guests)
    return read


@router.get("/{event_id}/guests", response_model=list[EventGuestRead])
def list_event_guests(
    event_id: uuid.UUID,
    principal: AuthenticatedPrincipal = Depends(require_permission("org:read")),
    db: Session = Depends(get_db),
):
    event = db.get(Event, event_id)
    if not event:
        raise NotFound("Evento não encontrado.")
    guests = db.execute(
        select(EventGuest).where(EventGuest.event_id == event_id).order_by(EventGuest.full_name.asc())
    ).scalars().all()
    return [EventGuestRead.model_validate(g) for g in guests]


@router.post("/{event_id}/guests", response_model=EventGuestRead)
def add_guest(
    event_id: uuid.UUID,
    req: EventGuestCreate,
    principal: AuthenticatedPrincipal = Depends(require_permission("org:manage")),
    db: Session = Depends(get_db),
):
    event = db.get(Event, event_id)
    if not event:
        raise NotFound("Evento não encontrado.")

    clean_ident = req.identifier.strip().upper()
    existing = db.execute(
        select(EventGuest).where(
            EventGuest.event_id == event_id,
            EventGuest.identifier == clean_ident,
        )
    ).scalar_one_or_none()
    if existing:
        raise ValidationFailed("Este documento/identificador já está cadastrado para este evento.")

    pin_hash = hash_secret(req.pin) if req.pin else None

    guest = EventGuest(
        event_id=event_id,
        full_name=req.full_name.strip(),
        identifier=clean_ident,
        email=req.email,
        phone=req.phone,
        organization_represented=req.organization_represented,
        pin_hash=pin_hash,
        biometric_status="pending",
        status="active",
    )
    db.add(guest)
    db.commit()
    db.refresh(guest)

    AuditService.record(
        db,
        actor_type="user",
        actor_id=str(principal.id),
        actor_label=principal.label,
        action="guest:added",
        resource_type="event_guest",
        resource_id=str(guest.id),
        details={"name": guest.full_name, "event_id": str(event_id)},
    )

    return EventGuestRead.model_validate(guest)


@router.delete("/guests/{guest_id}", response_model=MessageResponse)
def remove_guest(
    guest_id: uuid.UUID,
    principal: AuthenticatedPrincipal = Depends(require_permission("org:manage")),
    db: Session = Depends(get_db),
):
    guest = db.get(EventGuest, guest_id)
    if not guest:
        raise NotFound("Convidado não encontrado.")
    db.delete(guest)
    db.commit()
    return MessageResponse(message="Convidado removido com sucesso.")


@router.post("/guests/enroll", response_model=EventGuestRead)
def enroll_guest_biometrics(
    req: GuestBiometricEnroll,
    principal: AuthenticatedPrincipal = Depends(require_permission("biometrics:enroll")),
    db: Session = Depends(get_db),
):
    guest = db.get(EventGuest, req.guest_id)
    if not guest:
        raise NotFound("Convidado não encontrado.")

    s = get_settings()
    engine = get_biometric_engine()

    embeddings = []
    for idx, b64_img in enumerate(req.images_base64):
        img_bgr = _decode_image(b64_img)
        feature = engine.process_face(img_bgr, check_liveness=s.liveness_enabled)
        if not feature:
            raise ValidationFailed(f"Nenhum rosto detectado na captura #{idx + 1}.")
        if not feature.quality.passed:
            err_msg = "; ".join(feature.quality.errors)
            raise ValidationFailed(f"Qualidade insuficiente na captura #{idx + 1}: {err_msg}")
        embeddings.append(feature.embedding)

    # Average and L2-normalize master embedding
    master_emb = np.mean(embeddings, axis=0)
    norm = np.linalg.norm(master_emb)
    if norm > 0:
        master_emb /= norm

    # Encrypt template using AES-256-GCM
    keyring = biometric_key_ring()
    aad = template_aad(str(guest.id), str(guest.event_id), engine.version)
    plaintext_template = serialize_template(master_emb)
    encrypted_blob = keyring.encrypt(plaintext_template, aad)

    guest.template_ciphertext = encrypted_blob.ciphertext
    guest.template_nonce = encrypted_blob.nonce
    guest.key_id = encrypted_blob.key_id
    guest.engine_version = engine.version
    guest.biometric_status = "enrolled"
    db.commit()
    db.refresh(guest)

    AuditService.record(
        db,
        actor_type="user",
        actor_id=str(principal.id),
        actor_label=principal.label,
        action="guest:biometric_enrolled",
        resource_type="event_guest",
        resource_id=str(guest.id),
        details={"name": guest.full_name},
    )

    return EventGuestRead.model_validate(guest)
