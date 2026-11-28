"""Offline regression tests: no camera, live server or production database."""
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace as NS
from unittest.mock import Mock

import numpy as np
import pytest

from app.core.errors import Forbidden, ValidationFailed
from app.services import enrollment as service
from app.services.enrollment_policy import eligible_employee, eligible_guest, scoped_employee, scoped_guest


def feature(vector=(1.0, 0.0), live=True):
    return NS(embedding=np.array(vector), quality=NS(passed=True, errors=[], score=.9),
              liveness=NS(is_real=live, confidence=.99))


@pytest.fixture
def pipeline(monkeypatch):
    monkeypatch.setattr(service, 'decode_image', lambda _: np.zeros((4, 4, 3)))
    engine = Mock()
    engine.process_face.return_value = feature()
    engine.compute_similarity.return_value = .99
    return engine, NS(enrollment_captures=3, enrollment_min_consistency=.7)


def test_normalized_template_and_all_captures_checked(pipeline):
    engine, settings = pipeline
    result = service.build_enrollment(['a', 'b', 'c'], engine, settings)
    assert result.capture_count == 3
    assert np.linalg.norm(result.template) == pytest.approx(1)
    assert engine.compute_similarity.call_count == 3
    assert all(call.kwargs['check_liveness'] for call in engine.process_face.call_args_list)


@pytest.mark.parametrize('count', [0, 1, 2, 4])
def test_capture_count_is_enforced(pipeline, count):
    engine, settings = pipeline
    with pytest.raises(ValidationFailed):
        service.build_enrollment(['a'] * count, engine, settings)
    engine.process_face.assert_not_called()


@pytest.mark.parametrize('bad', [None, feature(live=False), feature((float('nan'), 1)), feature((0, 0))])
def test_invalid_or_spoofed_face_is_rejected(pipeline, bad):
    engine, settings = pipeline
    engine.process_face.return_value = bad
    with pytest.raises(ValidationFailed):
        service.build_enrollment(['a', 'b', 'c'], engine, settings)


def test_mixed_people_rejected(pipeline):
    engine, settings = pipeline
    engine.compute_similarity.return_value = .1
    with pytest.raises(ValidationFailed):
        service.build_enrollment(['a', 'b', 'c'], engine, settings)


def test_future_invitation_can_enroll_but_expired_cannot():
    now = datetime.now(UTC)
    event = NS(is_active=True, ends_at=now + timedelta(days=1), late_entry_minutes=30)
    guest = NS(status='active')
    eligible_guest(guest, event, now)
    with pytest.raises(ValidationFailed):
        eligible_guest(guest, event, now + timedelta(days=2))
    guest.status = 'cancelled'
    with pytest.raises(ValidationFailed):
        eligible_guest(guest, event, now)


@pytest.mark.parametrize('status', ['inactive', 'terminated', 'on_leave'])
def test_non_active_employee_cannot_enroll(status):
    with pytest.raises(ValidationFailed):
        eligible_employee(NS(employment_status=status))


def test_employee_cross_organization_rejected():
    db = Mock()
    db.get.return_value = NS(organization_id='other', unit_id='unit', department_id=None)
    principal = NS(organization_id='own', can_access_unit=lambda _: True, can_access_department=lambda _: True)
    with pytest.raises(Forbidden):
        scoped_employee(db, 'employee', principal)


@pytest.mark.parametrize('organization,allowed', [('other', True), ('own', False)])
def test_guest_checks_event_organization_and_unit(organization, allowed):
    db = Mock()
    db.get.side_effect = [NS(event_id='event'), NS(unit_id='unit'), NS(id='unit', organization_id=organization)]
    principal = NS(organization_id='own', can_access_unit=lambda _: allowed)
    with pytest.raises(Forbidden):
        scoped_guest(db, 'guest', principal)
