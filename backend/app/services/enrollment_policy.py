"""Separate employee and invitation eligibility from biometric processing."""
from datetime import UTC, datetime, timedelta
from app.core.errors import Forbidden, NotFound, ValidationFailed
from app.models.employee import Employee, EmploymentStatus
from app.models.guest import Event, EventGuest
from app.models.organization import Unit


def scoped_employee(db, employee_id, principal):
    employee = db.get(Employee, employee_id)
    if not employee:
        raise NotFound('Funcionário não encontrado.')
    if (employee.organization_id != principal.organization_id
            or not principal.can_access_unit(employee.unit_id)
            or not principal.can_access_department(employee.department_id)):
        raise Forbidden('Funcionário fora do seu escopo de acesso.')
    return employee


def eligible_employee(employee):
    if employee.employment_status != EmploymentStatus.ACTIVE:
        raise ValidationFailed('O cadastro facial exige vínculo funcional ativo.')


def scoped_unit(db, unit_id, principal):
    unit = db.get(Unit, unit_id)
    if not unit:
        raise NotFound('Unidade não encontrada.')
    if unit.organization_id != principal.organization_id or not principal.can_access_unit(unit.id):
        raise Forbidden('Unidade fora do seu escopo de acesso.')
    return unit


def scoped_event(db, event_id, principal):
    event = db.get(Event, event_id)
    if not event:
        raise NotFound('Evento não encontrado.')
    scoped_unit(db, event.unit_id, principal)
    return event


def scoped_guest(db, guest_id, principal):
    guest = db.get(EventGuest, guest_id)
    if not guest:
        raise NotFound('Convidado não encontrado.')
    return guest, scoped_event(db, guest.event_id, principal)


def eligible_guest(guest, event, now=None):
    end = event.ends_at
    if end.tzinfo is None:
        end = end.replace(tzinfo=UTC)
    if not event.is_active or (now or datetime.now(UTC)) > end + timedelta(minutes=event.late_entry_minutes):
        raise ValidationFailed('Cadastro indisponível: evento inativo ou encerrado.')
    if guest.status not in ('active', 'attended'):
        raise ValidationFailed('Convite cancelado ou bloqueado. Cadastro facial não permitido.')
