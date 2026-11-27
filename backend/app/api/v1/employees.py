"""Employees management API: list, create, edit, activate/inactivate, and PIN fallback setup."""
from __future__ import annotations

import math
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import AuthenticatedPrincipal, get_current_user, require_permission
from app.core.errors import Conflict, NotFound
from app.core.security import hash_secret
from app.db.session import get_db
from app.models.employee import BiometricStatus, Employee, EmploymentStatus
from app.models.organization import WorkSchedule
from app.schemas.dto import (
    EmployeeCreate,
    EmployeeRead,
    EmployeeUpdate,
    MessageResponse,
    PaginatedResponse,
)
from app.services.audit import AuditService

router = APIRouter(prefix="/employees", tags=["Funcionários"])


@router.get("", response_model=PaginatedResponse)
def list_employees(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    q: str | None = None,
    unit_id: uuid.UUID | None = None,
    department_id: uuid.UUID | None = None,
    status: str | None = None,
    principal: AuthenticatedPrincipal = Depends(require_permission("employees:read")),
    db: Session = Depends(get_db),
):
    stmt = select(Employee)

    # Apply data scoping
    if not principal.all_units and "superadmin" not in principal.roles:
        if principal.unit_ids:
            stmt = stmt.where(Employee.unit_id.in_(principal.unit_ids))
        if principal.department_ids:
            stmt = stmt.where(Employee.department_id.in_(principal.department_ids))

    if unit_id:
        stmt = stmt.where(Employee.unit_id == unit_id)
    if department_id:
        stmt = stmt.where(Employee.department_id == department_id)
    if status:
        stmt = stmt.where(Employee.employment_status == status)
    if q:
        like_expr = f"%{q.strip()}%"
        stmt = stmt.where(
            (Employee.full_name.ilike(like_expr))
            | (Employee.registration_number.ilike(like_expr))
            | (Employee.email.ilike(like_expr))
        )

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    pages = math.ceil(total / page_size) if total > 0 else 1

    items = db.execute(
        stmt.order_by(Employee.full_name.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).scalars().all()

    def _to_read(e: Employee) -> EmployeeRead:
        read = EmployeeRead.model_validate(e)
        if e.work_schedule_id:
            sched = db.get(WorkSchedule, e.work_schedule_id)
            if sched:
                read.work_schedule_name = sched.name
        return read

    return PaginatedResponse(
        items=[_to_read(e) for e in items],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.post("", response_model=EmployeeRead)
def create_employee(
    req: EmployeeCreate,
    request: Request,
    principal: AuthenticatedPrincipal = Depends(require_permission("employees:manage")),
    db: Session = Depends(get_db),
):
    # Verify unique registration number & email
    existing = db.execute(
        select(Employee).where(
            (Employee.registration_number == req.registration_number)
            | (Employee.email == req.email)
        )
    ).scalar_one_or_none()
    if existing:
        raise Conflict("Matrícula funcional ou e-mail já cadastrado.")

    pin_hash = hash_secret(req.pin) if req.pin else None

    org_id = principal.organization_id or uuid.uuid4()
    emp = Employee(
        organization_id=org_id,
        unit_id=req.unit_id,
        department_id=req.department_id,
        full_name=req.full_name,
        registration_number=req.registration_number,
        badge_code=req.badge_code,
        email=req.email,
        phone=req.phone,
        admission_date=req.admission_date,
        employment_status=EmploymentStatus.ACTIVE,
        biometric_status=BiometricStatus.NOT_ENROLLED,
        access_profile=req.access_profile,
        work_schedule_id=req.work_schedule_id,
        notes=req.notes,
        pin_hash=pin_hash,
    )
    db.add(emp)
    db.commit()
    db.refresh(emp)

    AuditService.record(
        db,
        actor_type="user",
        actor_id=str(principal.id),
        actor_label=principal.label,
        action="employee:created",
        resource_type="employee",
        resource_id=str(emp.id),
        details={"registration": emp.registration_number, "name": emp.full_name},
    )

    return EmployeeRead.model_validate(emp)


@router.get("/{employee_id}", response_model=EmployeeRead)
def get_employee(
    employee_id: uuid.UUID,
    principal: AuthenticatedPrincipal = Depends(require_permission("employees:read")),
    db: Session = Depends(get_db),
):
    emp = db.get(Employee, employee_id)
    if not emp:
        raise NotFound("Funcionário não encontrado.")
    return EmployeeRead.model_validate(emp)


@router.put("/{employee_id}", response_model=EmployeeRead)
def update_employee(
    employee_id: uuid.UUID,
    req: EmployeeUpdate,
    request: Request,
    principal: AuthenticatedPrincipal = Depends(require_permission("employees:manage")),
    db: Session = Depends(get_db),
):
    emp = db.get(Employee, employee_id)
    if not emp:
        raise NotFound("Funcionário não encontrado.")

    if req.full_name is not None:
        emp.full_name = req.full_name
    if req.badge_code is not None:
        emp.badge_code = req.badge_code
    if req.email is not None:
        emp.email = req.email
    if req.phone is not None:
        emp.phone = req.phone
    if req.unit_id is not None:
        emp.unit_id = req.unit_id
    if req.department_id is not None:
        emp.department_id = req.department_id
    if req.employment_status is not None:
        emp.employment_status = req.employment_status
    if req.access_profile is not None:
        emp.access_profile = req.access_profile
    if req.work_schedule_id is not None:
        emp.work_schedule_id = req.work_schedule_id
    if req.notes is not None:
        emp.notes = req.notes
    if req.pin is not None:
        emp.pin_hash = hash_secret(req.pin)

    db.commit()
    db.refresh(emp)

    AuditService.record(
        db,
        actor_type="user",
        actor_id=str(principal.id),
        actor_label=principal.label,
        action="employee:updated",
        resource_type="employee",
        resource_id=str(emp.id),
    )

    return EmployeeRead.model_validate(emp)
