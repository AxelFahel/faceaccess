"""Blocked Persons (Blacklist) Management API."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import AuthenticatedPrincipal, require_permission
from app.core.errors import NotFound, ValidationFailed
from app.core.timeutil import utcnow
from app.db.session import get_db
from app.models.guest import BlockedPerson
from app.models.organization import Organization
from app.schemas.dto import (
    BlockedPersonCreate,
    BlockedPersonRead,
    BlockedPersonUnblock,
    MessageResponse,
)
from app.services.audit import AuditService

router = APIRouter(prefix="/blocked-persons", tags=["Lista de Bloqueados"])


@router.get("", response_model=list[BlockedPersonRead])
def list_blocked_persons(
    include_inactive: bool = False,
    principal: AuthenticatedPrincipal = Depends(require_permission("org:read")),
    db: Session = Depends(get_db),
):
    query = select(BlockedPerson).order_by(BlockedPerson.blocked_at.desc())
    if not include_inactive:
        query = query.where(BlockedPerson.is_active == True)
    blocked = db.execute(query).scalars().all()
    return [BlockedPersonRead.model_validate(b) for b in blocked]


@router.post("", response_model=BlockedPersonRead)
def block_person(
    req: BlockedPersonCreate,
    principal: AuthenticatedPrincipal = Depends(require_permission("org:manage")),
    db: Session = Depends(get_db),
):
    clean_ident = req.identifier.strip().upper()
    existing = db.execute(
        select(BlockedPerson).where(
            BlockedPerson.identifier == clean_ident,
            BlockedPerson.is_active == True,
        )
    ).scalar_one_or_none()
    if existing:
        raise ValidationFailed(f"A pessoa com documento {clean_ident} já está na lista de bloqueados.")

    org = db.execute(select(Organization).limit(1)).scalar_one_or_none()
    org_id = org.id if org else None

    blocked = BlockedPerson(
        organization_id=org_id,
        full_name=req.full_name.strip(),
        identifier=clean_ident,
        reason=req.reason.strip(),
        blocked_by_user_id=principal.id if principal.principal_type == "user" else None,
        blocked_by_name=principal.label,
        is_active=True,
        blocked_at=utcnow(),
    )
    db.add(blocked)
    db.commit()
    db.refresh(blocked)

    AuditService.record(
        db,
        actor_type="user",
        actor_id=str(principal.id),
        actor_label=principal.label,
        action="security:person_blocked",
        resource_type="blocked_person",
        resource_id=str(blocked.id),
        details={"name": blocked.full_name, "identifier": clean_ident, "reason": blocked.reason},
    )

    return BlockedPersonRead.model_validate(blocked)


@router.post("/{blocked_id}/unblock", response_model=BlockedPersonRead)
def unblock_person(
    blocked_id: uuid.UUID,
    req: BlockedPersonUnblock,
    principal: AuthenticatedPrincipal = Depends(require_permission("org:manage")),
    db: Session = Depends(get_db),
):
    blocked = db.get(BlockedPerson, blocked_id)
    if not blocked:
        raise NotFound("Registro de bloqueio não encontrado.")
    if not blocked.is_active:
        raise ValidationFailed("Este registro já foi desbloqueado anteriormente.")

    blocked.is_active = False
    blocked.unblocked_at = utcnow()
    blocked.unblocked_reason = req.unblock_reason
    db.commit()
    db.refresh(blocked)

    AuditService.record(
        db,
        actor_type="user",
        actor_id=str(principal.id),
        actor_label=principal.label,
        action="security:person_unblocked",
        resource_type="blocked_person",
        resource_id=str(blocked.id),
        details={"name": blocked.full_name, "unblock_reason": req.unblock_reason},
    )

    return BlockedPersonRead.model_validate(blocked)
