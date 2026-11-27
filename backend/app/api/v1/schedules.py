"""Work Schedules and Schedule Exceptions (Horários de Trabalho e Exceções Registradas) API."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import AuthenticatedPrincipal, require_permission
from app.core.errors import NotFound, ValidationFailed
from app.core.timeutil import utcnow
from app.db.session import get_db
from app.models.employee import Employee
from app.models.organization import Organization, ScheduleException, WorkSchedule
from app.schemas.dto import (
    MessageResponse,
    ScheduleExceptionCancel,
    ScheduleExceptionCreate,
    ScheduleExceptionRead,
    WorkScheduleCreate,
    WorkScheduleRead,
)
from app.services.audit import AuditService

router = APIRouter(prefix="/schedules", tags=["Jornadas e Exceções de Acesso"])


# --- Work Schedules ---
@router.get("", response_model=list[WorkScheduleRead])
def list_work_schedules(
    principal: AuthenticatedPrincipal = Depends(require_permission("org:read")),
    db: Session = Depends(get_db),
):
    schedules = db.execute(
        select(WorkSchedule).where(WorkSchedule.is_active == True).order_by(WorkSchedule.name.asc())
    ).scalars().all()

    # If no schedules exist, seed a standard corporate schedule automatically
    if not schedules:
        org = db.execute(select(Organization).limit(1)).scalar_one_or_none()
        org_id = org.id if org else uuid.uuid4()
        default_days = [
            {"weekday": i, "start": "08:00", "end": "17:00", "break_minutes": 60}
            for i in range(5)  # Mon (0) to Fri (4)
        ]
        std = WorkSchedule(
            organization_id=org_id,
            name="Comercial Padrão (Seg a Sex 08:00 às 17:00)",
            description="Jornada padrão de 40 horas semanais com 15 minutos de tolerância",
            days=default_days,
            tolerance_minutes=15,
            is_active=True,
        )
        db.add(std)
        db.commit()
        db.refresh(std)
        schedules = [std]

    return [WorkScheduleRead.model_validate(s) for s in schedules]


@router.post("", response_model=WorkScheduleRead)
def create_work_schedule(
    req: WorkScheduleCreate,
    principal: AuthenticatedPrincipal = Depends(require_permission("org:manage")),
    db: Session = Depends(get_db),
):
    org = db.execute(select(Organization).limit(1)).scalar_one_or_none()
    org_id = org.id if org else uuid.uuid4()

    days_dict = [d.model_dump() for d in req.days]

    sched = WorkSchedule(
        organization_id=org_id,
        name=req.name.strip(),
        description=req.description.strip() if req.description else None,
        days=days_dict,
        tolerance_minutes=req.tolerance_minutes,
        is_active=True,
    )
    db.add(sched)
    db.commit()
    db.refresh(sched)

    AuditService.record(
        db,
        actor_type="user",
        actor_id=str(principal.id),
        actor_label=principal.label,
        action="schedule:created",
        resource_type="work_schedule",
        resource_id=str(sched.id),
        details={"name": sched.name, "tolerance": sched.tolerance_minutes},
    )

    return WorkScheduleRead.model_validate(sched)


# --- Schedule Exceptions ---
@router.get("/exceptions", response_model=list[ScheduleExceptionRead])
def list_schedule_exceptions(
    employee_id: uuid.UUID | None = None,
    active_only: bool = False,
    principal: AuthenticatedPrincipal = Depends(require_permission("org:read")),
    db: Session = Depends(get_db),
):
    query = select(ScheduleException).order_by(ScheduleException.starts_at.desc())
    if employee_id:
        query = query.where(ScheduleException.employee_id == employee_id)
    if active_only:
        query = query.where(ScheduleException.is_active == True)

    exceptions = db.execute(query).scalars().all()

    result = []
    for exc in exceptions:
        read = ScheduleExceptionRead.model_validate(exc)
        emp = db.get(Employee, exc.employee_id)
        if emp:
            read.employee_name = emp.full_name
        result.append(read)
    return result


@router.post("/exceptions", response_model=ScheduleExceptionRead)
def create_schedule_exception(
    req: ScheduleExceptionCreate,
    principal: AuthenticatedPrincipal = Depends(require_permission("org:manage")),
    db: Session = Depends(get_db),
):
    emp = db.get(Employee, req.employee_id)
    if not emp:
        raise NotFound("Funcionário não encontrado.")

    if req.ends_at <= req.starts_at:
        raise ValidationFailed("O horário final da exceção deve ser posterior ao horário inicial.")

    if not req.reason.strip():
        raise ValidationFailed("O motivo da exceção é obrigatório para fins de conformidade e auditoria.")

    exc = ScheduleException(
        employee_id=req.employee_id,
        starts_at=req.starts_at,
        ends_at=req.ends_at,
        reason=req.reason.strip(),
        exception_type=req.exception_type,
        authorized_by_user_id=principal.id if principal.principal_type == "user" else None,
        authorized_by_name=principal.label,
        is_active=True,
    )
    db.add(exc)
    db.commit()
    db.refresh(exc)

    AuditService.record(
        db,
        actor_type="user",
        actor_id=str(principal.id),
        actor_label=principal.label,
        action="schedule_exception:created",
        resource_type="schedule_exception",
        resource_id=str(exc.id),
        details={
            "employee_id": str(emp.id),
            "employee_name": emp.full_name,
            "reason": exc.reason,
            "starts_at": exc.starts_at.isoformat(),
            "ends_at": exc.ends_at.isoformat(),
        },
    )

    read = ScheduleExceptionRead.model_validate(exc)
    read.employee_name = emp.full_name
    return read


@router.post("/exceptions/{exception_id}/cancel", response_model=ScheduleExceptionRead)
def cancel_schedule_exception(
    exception_id: uuid.UUID,
    req: ScheduleExceptionCancel,
    principal: AuthenticatedPrincipal = Depends(require_permission("org:manage")),
    db: Session = Depends(get_db),
):
    exc = db.get(ScheduleException, exception_id)
    if not exc:
        raise NotFound("Exceção de horário não encontrada.")
    if not exc.is_active:
        raise ValidationFailed("Esta exceção já está inativa ou cancelada.")

    exc.is_active = False
    exc.reason = f"{exc.reason} [Cancelada: {req.cancel_reason}]"
    db.commit()
    db.refresh(exc)

    AuditService.record(
        db,
        actor_type="user",
        actor_id=str(principal.id),
        actor_label=principal.label,
        action="schedule_exception:cancelled",
        resource_type="schedule_exception",
        resource_id=str(exc.id),
        details={"cancel_reason": req.cancel_reason},
    )

    read = ScheduleExceptionRead.model_validate(exc)
    emp = db.get(Employee, exc.employee_id)
    if emp:
        read.employee_name = emp.full_name
    return read
