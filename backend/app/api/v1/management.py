"""Organization, terminals, attendance, reports and dashboard API routes."""
from __future__ import annotations

import csv
import io
import math
import uuid
from datetime import UTC, date, datetime, timedelta

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import AuthenticatedPrincipal, require_permission
from app.core.crypto import constant_time_equals, random_numeric_code, random_token, sha256_hex
from app.core.errors import Forbidden, NotFound
from app.core.config import get_settings
from app.core.timeutil import local_day_bounds_utc, local_today, utcnow
from app.db.session import get_db
from app.models.access import AccessEvent, Terminal, TerminalStatus
from app.models.attendance import AttendanceRecord
from app.models.biometric import BiometricEnrollment, EnrollmentStatus
from app.models.employee import BiometricStatus, Employee, EmploymentStatus
from app.models.organization import Department, Organization, Unit
from app.schemas.dto import (
    AttendanceManualCreate,
    AttendanceRecordRead,
    DashboardMetrics,
    DepartmentCreate,
    DepartmentRead,
    PaginatedResponse,
    TerminalActivateRequest,
    TerminalActivateResponse,
    TerminalCreate,
    TerminalCreated,
    TerminalRead,
    UnitCreate,
    UnitRead,
)
from app.services.audit import AuditService

org_router = APIRouter(prefix="/organization", tags=["Organização"])
terminals_router = APIRouter(prefix="/terminals", tags=["Terminais"])
attendance_router = APIRouter(prefix="/attendance", tags=["Presença"])
dashboard_router = APIRouter(prefix="/dashboard", tags=["Dashboard"])
reports_router = APIRouter(prefix="/reports", tags=["Relatórios"])


# --- Organization ---
@org_router.get("/units", response_model=list[UnitRead])
def list_units(
    principal: AuthenticatedPrincipal = Depends(require_permission("org:read")),
    db: Session = Depends(get_db),
):
    stmt = select(Unit).where(Unit.is_active == True)
    if not principal.all_units and "superadmin" not in principal.roles and principal.unit_ids:
        stmt = stmt.where(Unit.id.in_(principal.unit_ids))
    return db.execute(stmt.order_by(Unit.name.asc())).scalars().all()


@org_router.post("/units", response_model=UnitRead)
def create_unit(
    req: UnitCreate,
    principal: AuthenticatedPrincipal = Depends(require_permission("org:manage")),
    db: Session = Depends(get_db),
):
    org = db.execute(select(Organization).limit(1)).scalar_one_or_none()
    org_id = org.id if org else uuid.uuid4()
    unit = Unit(
        organization_id=org_id,
        name=req.name,
        code=req.code,
        address=req.address,
        timezone=req.timezone,
    )
    db.add(unit)
    db.commit()
    db.refresh(unit)
    return UnitRead.model_validate(unit)


@org_router.get("/departments", response_model=list[DepartmentRead])
def list_departments(
    principal: AuthenticatedPrincipal = Depends(require_permission("org:read")),
    db: Session = Depends(get_db),
):
    return db.execute(
        select(Department).where(Department.is_active == True).order_by(Department.name.asc())
    ).scalars().all()


@org_router.post("/departments", response_model=DepartmentRead)
def create_department(
    req: DepartmentCreate,
    principal: AuthenticatedPrincipal = Depends(require_permission("org:manage")),
    db: Session = Depends(get_db),
):
    org = db.execute(select(Organization).limit(1)).scalar_one_or_none()
    org_id = org.id if org else uuid.uuid4()
    dept = Department(
        organization_id=org_id,
        unit_id=req.unit_id,
        name=req.name,
        code=req.code,
    )
    db.add(dept)
    db.commit()
    db.refresh(dept)
    return DepartmentRead.model_validate(dept)


# --- Terminals ---
@terminals_router.get("", response_model=list[TerminalRead])
def list_terminals(
    principal: AuthenticatedPrincipal = Depends(require_permission("terminals:read")),
    db: Session = Depends(get_db),
):
    return db.execute(select(Terminal).order_by(Terminal.name.asc())).scalars().all()


@terminals_router.post("", response_model=TerminalCreated)
def create_terminal(
    req: TerminalCreate,
    principal: AuthenticatedPrincipal = Depends(require_permission("terminals:manage")),
    db: Session = Depends(get_db),
):
    activation_code = random_numeric_code(8)
    act_hash = sha256_hex(activation_code)

    term = Terminal(
        code=req.code,
        name=req.name,
        unit_id=req.unit_id,
        terminal_type=req.terminal_type,
        allowed_operations=req.allowed_operations,
        status=TerminalStatus.PENDING,
        activation_code_hash=act_hash,
        activation_expires_at=utcnow() + timedelta(minutes=get_settings().terminal_activation_ttl_minutes),
    )
    db.add(term)
    db.commit()
    db.refresh(term)
    return TerminalCreated(**TerminalRead.model_validate(term).model_dump(), activation_code=activation_code)


@terminals_router.post("/{terminal_id}/activation-code")
def renew_activation_code(
    terminal_id: uuid.UUID,
    principal: AuthenticatedPrincipal = Depends(require_permission("terminals:manage")),
    db: Session = Depends(get_db),
):
    term = db.get(Terminal, terminal_id)
    if not term:
        raise NotFound("Terminal não encontrado.")
    unit = db.get(Unit, term.unit_id)
    if not unit or unit.organization_id != principal.organization_id or not principal.can_access_unit(term.unit_id):
        raise Forbidden("Terminal fora do seu escopo de acesso.")
    if term.status != TerminalStatus.PENDING:
        raise Forbidden("Somente terminais pendentes podem receber código de ativação.")
    code = random_numeric_code(8)
    term.activation_code_hash = sha256_hex(code)
    term.activation_expires_at = utcnow() + timedelta(minutes=get_settings().terminal_activation_ttl_minutes)
    db.commit()
    return {"code": term.code, "activation_code": code}


@terminals_router.post("/activate", response_model=TerminalActivateResponse)
def activate_terminal(
    req: TerminalActivateRequest,
    db: Session = Depends(get_db),
):
    term = db.execute(select(Terminal).where(Terminal.code == req.code).with_for_update()).scalar_one_or_none()
    if not term:
        raise NotFound("Terminal não encontrado.")

    expires = term.activation_expires_at
    if expires and expires.tzinfo is None:
        expires = expires.replace(tzinfo=UTC)
    if (term.status != TerminalStatus.PENDING or not term.activation_code_hash
            or not expires or expires <= utcnow()
            or not constant_time_equals(sha256_hex(req.activation_code), term.activation_code_hash)):
        raise Forbidden("Código de ativação inválido, expirado ou já utilizado.")

    # Generate permanent secret
    secret = random_token(32)
    term.credential_prefix = secret[:8]
    term.credential_hash = sha256_hex(secret)
    term.status = TerminalStatus.ACTIVE
    term.credential_issued_at = utcnow()
    term.activation_code_hash = None
    db.commit()

    return TerminalActivateResponse(
        terminal_id=term.id,
        code=term.code,
        terminal_secret=secret,
        message="Terminal ativado com sucesso. Guarde a credencial em local seguro.",
    )


# --- Attendance ---
@attendance_router.get("", response_model=PaginatedResponse)
def list_attendance(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    employee_id: uuid.UUID | None = None,
    target_date: date | None = None,
    principal: AuthenticatedPrincipal = Depends(require_permission("attendance:read")),
    db: Session = Depends(get_db),
):
    stmt = (
        select(AttendanceRecord, Employee.full_name)
        .outerjoin(Employee, AttendanceRecord.employee_id == Employee.id)
        .where(AttendanceRecord.status == "valid")
    )
    if employee_id:
        stmt = stmt.where(AttendanceRecord.employee_id == employee_id)
    if target_date:
        stmt = stmt.where(AttendanceRecord.local_date == target_date)

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    pages = math.ceil(total / page_size) if total > 0 else 1

    rows = db.execute(
        stmt.order_by(AttendanceRecord.recorded_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    items = []
    for r, emp_name in rows:
        data = AttendanceRecordRead.model_validate(r)
        data.employee_name = emp_name
        items.append(data)

    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@attendance_router.post("/manual", response_model=AttendanceRecordRead)
def create_manual_attendance(
    req: AttendanceManualCreate,
    request: Request,
    principal: AuthenticatedPrincipal = Depends(require_permission("attendance:manual")),
    db: Session = Depends(get_db),
):
    emp = db.get(Employee, req.employee_id)
    if not emp:
        raise NotFound("Funcionário não encontrado.")

    record_time = req.recorded_at or utcnow()
    local_d = local_today()

    record = AttendanceRecord(
        employee_id=emp.id,
        record_type=req.record_type,
        recorded_at=record_time,
        local_date=local_d,
        unit_id=emp.unit_id,
        verification_method="manual",
        result="accepted",
        source="manual",
        status="valid",
        created_by_user_id=principal.id,
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    AuditService.record(
        db,
        actor_type="user",
        actor_id=str(principal.id),
        actor_label=principal.label,
        action="attendance:manual_created",
        resource_type="attendance",
        resource_id=str(record.id),
        details={"employee_id": str(emp.id), "record_type": req.record_type, "reason": req.reason},
    )

    res = AttendanceRecordRead.model_validate(record)
    res.employee_name = emp.full_name
    return res


# --- Dashboard ---
@dashboard_router.get("/metrics", response_model=DashboardMetrics)
def get_dashboard_metrics(
    principal: AuthenticatedPrincipal = Depends(require_permission("dashboard:read")),
    db: Session = Depends(get_db),
):
    today = local_today()
    start_utc, end_utc = local_day_bounds_utc(today)

    total_emp = db.scalar(select(func.count(Employee.id))) or 0
    active_emp = db.scalar(
        select(func.count(Employee.id)).where(Employee.employment_status == EmploymentStatus.ACTIVE)
    ) or 0
    inactive_emp = total_emp - active_emp

    enrolled = db.scalar(
        select(func.count(Employee.id)).where(Employee.biometric_status == BiometricStatus.ENROLLED)
    ) or 0

    today_att = db.scalar(
        select(func.count(AttendanceRecord.id)).where(
            AttendanceRecord.recorded_at >= start_utc,
            AttendanceRecord.recorded_at < end_utc,
            AttendanceRecord.status == "valid",
        )
    ) or 0

    present_emp = db.scalar(
        select(func.count(func.distinct(AttendanceRecord.employee_id))).where(
            AttendanceRecord.recorded_at >= start_utc,
            AttendanceRecord.recorded_at < end_utc,
            AttendanceRecord.status == "valid",
        )
    ) or 0

    auth_access = db.scalar(
        select(func.count(AccessEvent.id)).where(
            AccessEvent.created_at >= start_utc,
            AccessEvent.created_at < end_utc,
            AccessEvent.decision == "granted",
        )
    ) or 0

    denied_access = db.scalar(
        select(func.count(AccessEvent.id)).where(
            AccessEvent.created_at >= start_utc,
            AccessEvent.created_at < end_utc,
            AccessEvent.decision != "granted",
        )
    ) or 0

    active_term = db.scalar(
        select(func.count(Terminal.id)).where(Terminal.status == TerminalStatus.ACTIVE)
    ) or 0

    return DashboardMetrics(
        total_employees=total_emp,
        active_employees=active_emp,
        inactive_employees=inactive_emp,
        enrolled_biometrics=enrolled,
        today_attendances=today_att,
        present_employees=present_emp,
        authorized_accesses_today=auth_access,
        denied_accesses_today=denied_access,
        active_terminals=active_term,
        system_status="operational",
        timestamp=utcnow(),
    )


# --- Reports Export ---
@reports_router.get("/attendance/csv")
def export_attendance_csv(
    start_date: date | None = None,
    end_date: date | None = None,
    principal: AuthenticatedPrincipal = Depends(require_permission("reports:export")),
    db: Session = Depends(get_db),
):
    stmt = select(AttendanceRecord).where(AttendanceRecord.status == "valid")
    if start_date:
        stmt = stmt.where(AttendanceRecord.local_date >= start_date)
    if end_date:
        stmt = stmt.where(AttendanceRecord.local_date <= end_date)

    records = db.execute(stmt.order_by(AttendanceRecord.recorded_at.desc())).scalars().all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "ID_Evento", "ID_Funcionario", "Data_Local", "Horario_UTC",
        "Tipo_Registro", "Metodo_Verificacao", "Resultado", "Origem", "Status"
    ])
    for r in records:
        writer.writerow([
            str(r.id), str(r.employee_id), str(r.local_date), r.recorded_at.isoformat(),
            r.record_type, r.verification_method, r.result, r.source, r.status
        ])

    AuditService.record(
        db, actor_type="user", actor_id=str(principal.id), actor_label=principal.label,
        action="reports:export_csv", resource_type="attendance"
    )

    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=presenca_export.csv"},
    )
