import base64
import os
import uuid
import tempfile
from pathlib import Path
import pytest
from guest_enrollment_case import test_guest_capture_enroll_revoke_and_scope
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

test_directory = tempfile.TemporaryDirectory(prefix="faceaccess-tests-")
os.environ["DATABASE_URL"] = "sqlite:///" + (Path(test_directory.name) / "test.db").as_posix()
os.environ["JWT_SECRET"] = "super-secret-jwt-key-with-at-least-32-chars!"
os.environ["AUDIT_HMAC_KEY"] = "super-secret-audit-hmac-key-min-32-bytes!"
os.environ["BIOMETRIC_KEYS"] = '{"k1": "' + base64.b64encode(b"0" * 32).decode() + '"}'
os.environ["BIOMETRIC_ACTIVE_KEY_ID"] = "k1"
os.environ["DATA_ENCRYPTION_KEY"] = base64.b64encode(b"1" * 32).decode()
os.environ["BIOMETRIC_ENGINE"] = "fake"
os.environ["APP_ENV"] = "test"
os.environ["COOKIE_SECURE"] = "false"

from app.db.base import Base
from app.db.session import get_db
from app.main import create_app
from scripts.bootstrap import seed_db

test_engine = create_engine(os.environ["DATABASE_URL"], connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

app = create_app()
app.dependency_overrides[get_db] = override_get_db

@pytest.fixture(scope="session", autouse=True)
def setup_db():
    Base.metadata.create_all(bind=test_engine)
    seed_db()
    yield
    test_engine.dispose()
    from app.db.session import get_engine
    get_engine().dispose()
    test_directory.cleanup()

@pytest.fixture
def client():
    return TestClient(app)

def test_health(client):
    res = client.get("/api/v1/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"

def test_login_flow(client):
    res = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@faceaccess.com", "password": "Admin@Secure2026!"},
    )
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert data["user"]["email"] == "admin@faceaccess.com"

def test_employee_and_kiosk_flow(client, monkeypatch):
    # 1. Login as admin
    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@faceaccess.com", "password": "Admin@Secure2026!"},
    )
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Get units
    units = client.get("/api/v1/organization/units", headers=headers).json()
    assert len(units) > 0
    unit_id = units[0]["id"]

    # 3. Create employee with unique registration
    unique_reg = f"EMP-{uuid.uuid4().hex[:6]}"
    unique_email = f"emp-{uuid.uuid4().hex[:6]}@empresa.com"
    emp_res = client.post(
        "/api/v1/employees",
        json={
            "full_name": "Carlos Silva",
            "registration_number": unique_reg,
            "email": unique_email,
            "unit_id": unit_id,
            "pin": "123456",
        },
        headers=headers,
    )
    assert emp_res.status_code == 200
    emp_data = emp_res.json()
    emp_id = emp_data["id"]

    # 4. Enroll fake biometrics
    lb = client.get("/api/v1/privacy/legal-basis", headers=headers).json()[0]
    dummy_b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
    capture_payload = {"employee_id": emp_id, "image_base64": dummy_b64}
    assert client.post("/api/v1/biometrics/capture-check", json=capture_payload).status_code == 401
    check = client.post("/api/v1/biometrics/capture-check", json=capture_payload, headers=headers)
    assert check.status_code == 200
    assert check.json()["accepted"] is True
    assert check.json()["required_captures"] == 3

    # A frame without a face must never advance the enrollment guide.
    from app.biometrics.engine import get_biometric_engine
    with monkeypatch.context() as patch:
        patch.setattr(get_biometric_engine(), "process_face", lambda *a, **kw: None)
        rejected = client.post("/api/v1/biometrics/capture-check", json=capture_payload, headers=headers)
        assert rejected.json()["accepted"] is False

    # Missing liveness fails closed both in the guide and the final write.
    from dataclasses import replace
    import numpy as np
    feature = get_biometric_engine().process_face(np.zeros((1, 1, 3), dtype=np.uint8))
    with monkeypatch.context() as patch:
        patch.setattr(get_biometric_engine(), "process_face", lambda *a, **kw: replace(feature, liveness=None))
        rejected = client.post("/api/v1/biometrics/capture-check", json=capture_payload, headers=headers)
        assert rejected.json()["accepted"] is False
        rejected_enrollment = client.post("/api/v1/biometrics/enroll", json={
            "employee_id": emp_id, "images_base64": [dummy_b64] * 3, "legal_basis_record_id": lb["id"],
        }, headers=headers)
        assert rejected_enrollment.status_code == 422

    incomplete = client.post("/api/v1/biometrics/enroll", json={
        "employee_id": emp_id, "images_base64": [dummy_b64], "legal_basis_record_id": lb["id"],
    }, headers=headers)
    assert incomplete.status_code == 422
    enroll_res = client.post(
        "/api/v1/biometrics/enroll",
        json={
            "employee_id": emp_id,
            "images_base64": [dummy_b64] * 3,
            "legal_basis_record_id": lb["id"],
        },
        headers=headers,
    )
    assert enroll_res.status_code == 200

    # 5. Create and activate a terminal
    term_code = f"TERM-{uuid.uuid4().hex[:4].upper()}"
    term_res = client.post(
        "/api/v1/terminals",
        json={"code": term_code, "name": "Terminal Teste", "unit_id": unit_id},
        headers=headers,
    )
    assert term_res.status_code == 200

    assert client.post("/api/v1/terminals/activate", json={
        "code": term_code, "activation_code": "wrong-code",
    }).status_code == 403

    act_res = client.post(
        "/api/v1/terminals/activate",
        json={"code": term_code, "activation_code": term_res.json()["activation_code"]},
    )
    assert act_res.status_code == 200
    term_secret = act_res.json()["terminal_secret"]
    assert client.post("/api/v1/terminals/activate", json={
        "code": term_code, "activation_code": term_res.json()["activation_code"],
    }).status_code == 403

    # 6. Kiosk verify with PIN
    term_headers = {
        "X-Terminal-Code": term_code,
        "X-Terminal-Secret": term_secret,
    }
    # Guidance is terminal-authenticated and does not register attendance.
    import cv2
    image = np.zeros((480, 640, 3), dtype=np.uint8)
    _, encoded = cv2.imencode('.jpg', image)
    guidance_payload = {"image_base64": base64.b64encode(encoded).decode()}
    assert client.post('/api/v1/kiosk/capture-check', json=guidance_payload).status_code == 401
    with monkeypatch.context() as patch:
        patch.setattr(get_biometric_engine(), 'process_face', lambda *a, **kw: replace(feature, bbox=[200, 100, 440, 380]))
        guidance = client.post('/api/v1/kiosk/capture-check', json=guidance_payload, headers=term_headers)
        assert guidance.status_code == 200 and guidance.json()['accepted']
        assert 'access_decision' not in guidance.json()
    with monkeypatch.context() as patch:
        patch.setattr(get_biometric_engine(), 'process_face', lambda *a, **kw: None)
        assert not client.post('/api/v1/kiosk/capture-check', json=guidance_payload, headers=term_headers).json()['accepted']
    pin_verify = client.post(
        "/api/v1/kiosk/verify",
        json={
            "identifier": unique_reg,
            "method": "pin",
            "pin": "123456",
            "operation_type": "attendance",
        },
        headers=term_headers,
    )
    assert pin_verify.status_code == 200
    assert pin_verify.json()["status"] == "verified"
    assert pin_verify.json()["access_decision"] == "granted"
    assert pin_verify.json()["attendance_record_id"]

    # Face-only recognition uses the saved template and returns the person's name.
    face_payload = {"method": "face", "image_base64": dummy_b64, "operation_type": "attendance"}
    face_verify = client.post("/api/v1/kiosk/verify", json=face_payload, headers=term_headers)
    assert face_verify.status_code == 200
    assert face_verify.json()["status"] == "verified"
    assert face_verify.json()["employee_name"] == "Carlos Silva"
    assert face_verify.json()["employee_id"] == emp_id
    # The prior PIN record must not be written a second time.
    assert face_verify.json()["attendance_record_id"] is None
    assert face_verify.json()["reasons"]

    # A missing or spoofed face must not produce attendance.
    with monkeypatch.context() as patch:
        patch.setattr(get_biometric_engine(), "process_face", lambda *a, **kw: None)
        no_face = client.post("/api/v1/kiosk/verify", json=face_payload, headers=term_headers).json()
        assert no_face["status"] == "inconclusive"
        assert no_face["attendance_record_id"] is None
        assert no_face["retryable"]
    with monkeypatch.context() as patch:
        patch.setattr(get_biometric_engine(), "process_face", lambda *a, **kw: replace(feature, liveness=None))
        spoof = client.post("/api/v1/kiosk/verify", json=face_payload, headers=term_headers).json()
        assert spoof["status"] == "rejected"
        assert spoof["employee_name"] is None

    # Identical candidate templates must not result in guessing someone's identity.
    second = client.post("/api/v1/employees", json={
        "full_name": "Outra Pessoa", "registration_number": "OTHER-" + uuid.uuid4().hex[:8],
        "email": uuid.uuid4().hex + "@empresa.com", "unit_id": unit_id,
    }, headers=headers).json()
    assert client.post("/api/v1/biometrics/enroll", json={
        "employee_id": second["id"], "images_base64": [dummy_b64] * 3, "legal_basis_record_id": lb["id"],
    }, headers=headers).status_code == 200
    ambiguous = client.post("/api/v1/kiosk/verify", json=face_payload, headers=term_headers).json()
    assert ambiguous["status"] == "inconclusive"
    assert ambiguous["employee_name"] is None
    assert ambiguous["attendance_record_id"] is None

    # An equally matching person in another unit is not a candidate for this terminal.
    from app.models.employee import Employee
    with TestingSessionLocal() as db:
        other = db.get(Employee, uuid.UUID(second["id"]))
        from app.models.organization import Unit
        other_unit = Unit(organization_id=other.organization_id, name="Outra unidade de teste",
                          code="TEST-" + uuid.uuid4().hex[:8])
        db.add(other_unit)
        db.flush()
        other.unit_id = other_unit.id
        db.commit()
    scoped = client.post("/api/v1/kiosk/verify", json=face_payload, headers=term_headers).json()
    assert scoped["status"] == "verified"
    assert scoped["employee_id"] == emp_id

    # 7. Check attendance records
    att_res = client.get("/api/v1/attendance", headers=headers)
    assert att_res.status_code == 200
    assert att_res.json()["total"] >= 1
