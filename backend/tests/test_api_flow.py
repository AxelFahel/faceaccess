import base64
import os
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

os.environ["DATABASE_URL"] = "sqlite:///./test.db"
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

test_engine = create_engine("sqlite:///./test.db", connect_args={"check_same_thread": False})
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

def test_employee_and_kiosk_flow(client):
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
    enroll_res = client.post(
        "/api/v1/biometrics/enroll",
        json={
            "employee_id": emp_id,
            "images_base64": [dummy_b64, dummy_b64],
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

    act_res = client.post(
        "/api/v1/terminals/activate",
        json={"code": term_code, "activation_code": "00000000"},
    )
    assert act_res.status_code == 200
    term_secret = act_res.json()["terminal_secret"]

    # 6. Kiosk verify with PIN
    term_headers = {
        "X-Terminal-Code": term_code,
        "X-Terminal-Secret": term_secret,
    }
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

    # 7. Check attendance records
    att_res = client.get("/api/v1/attendance", headers=headers)
    assert att_res.status_code == 200
    assert att_res.json()["total"] >= 1
