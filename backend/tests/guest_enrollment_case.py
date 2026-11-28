"""Guest enrollment API uses the same security gate as employees."""
import uuid
from datetime import UTC, datetime, timedelta
from dataclasses import replace

import numpy as np
from app.biometrics.engine import get_biometric_engine
from app.models.guest import EventGuest
from app.models.organization import Organization, Unit

IMAGE = 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII='


def test_guest_capture_enroll_revoke_and_scope(client, monkeypatch):
    from test_api_flow import TestingSessionLocal
    login = client.post('/api/v1/auth/login', json={'email': 'admin@faceaccess.com', 'password': 'Admin@Secure2026!'})
    headers = {'Authorization': 'Bearer ' + login.json()['access_token']}
    unit = client.get('/api/v1/organization/units', headers=headers).json()[0]['id']
    now = datetime.now(UTC)
    event = client.post('/api/v1/events', headers=headers, json={
        'unit_id': unit, 'name': 'Enrollment regression',
        'starts_at': now.isoformat(), 'ends_at': (now + timedelta(hours=2)).isoformat(),
    })
    assert event.status_code == 200, event.text
    guest = client.post(f"/api/v1/events/{event.json()['id']}/guests", headers=headers,
                        json={'full_name': 'Test Guest', 'identifier': uuid.uuid4().hex}).json()
    capture = {'guest_id': guest['id'], 'image_base64': IMAGE}
    assert client.post('/api/v1/events/guests/capture-check', json=capture).status_code == 401
    checked = client.post('/api/v1/events/guests/capture-check', headers=headers, json=capture)
    assert checked.status_code == 200 and checked.json()['accepted']
    enrollment = {'guest_id': guest['id'], 'images_base64': [IMAGE] * 3}
    assert client.post('/api/v1/events/guests/enroll', headers=headers,
                       json={**enrollment, 'images_base64': [IMAGE]}).status_code == 422
    engine = get_biometric_engine()
    face = engine.process_face(np.zeros((1, 1, 3), dtype=np.uint8))
    with monkeypatch.context() as patch:
        patch.setattr(engine, 'process_face', lambda *args, **kwargs: replace(face, liveness=None))
        assert not client.post('/api/v1/events/guests/capture-check', headers=headers, json=capture).json()['accepted']
        assert client.post('/api/v1/events/guests/enroll', headers=headers, json=enrollment).status_code == 422
    saved = client.post('/api/v1/events/guests/enroll', headers=headers, json=enrollment)
    assert saved.status_code == 200, saved.text
    assert saved.json()['biometric_status'] == 'enrolled'
    assert client.post(f"/api/v1/events/guests/{guest['id']}/revoke", headers=headers).status_code == 200
    with TestingSessionLocal() as db:
        stored = db.get(EventGuest, uuid.UUID(guest['id']))
        assert stored.biometric_status == 'revoked'
        assert stored.template_ciphertext is None and stored.template_nonce is None
        assert stored.status == 'active'
        stored.status = 'cancelled'
        db.commit()
    assert client.post('/api/v1/events/guests/enroll', headers=headers, json=enrollment).status_code == 422
    with TestingSessionLocal() as db:
        org = Organization(name='Other organization')
        db.add(org); db.flush()
        other_unit = Unit(name='Other unit', code=uuid.uuid4().hex[:8], organization_id=org.id)
        db.add(other_unit); db.commit()
        other_id = str(other_unit.id)
    assert client.post('/api/v1/events', headers=headers, json={
        'unit_id': other_id, 'name': 'Forbidden', 'starts_at': now.isoformat(),
        'ends_at': (now + timedelta(hours=1)).isoformat(),
    }).status_code == 403
