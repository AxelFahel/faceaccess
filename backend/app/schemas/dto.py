"""Pydantic schemas for request / response serialization."""
from __future__ import annotations

import uuid
from datetime import date, datetime, time
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# --- Generic / Paginated envelope ---
class PaginatedResponse(BaseModel):
    items: list[Any]
    total: int
    page: int
    page_size: int
    pages: int


class MessageResponse(BaseModel):
    message: str
    success: bool = True


# --- Auth ---
class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "Bearer"
    expires_in: int
    must_change_password: bool = False
    mfa_required: bool = False
    mfa_ticket: str | None = None
    user: UserRead | None = None


class MfaVerifyRequest(BaseModel):
    mfa_ticket: str
    code: str


class RefreshTokenRequest(BaseModel):
    refresh_token: str | None = None


# --- Users & RBAC ---
class PermissionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    code: str
    description: str


class RoleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    code: str
    name: str
    description: str | None = None
    permissions: list[PermissionRead] = []


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    email: str
    full_name: str
    is_active: bool
    all_units: bool
    roles: list[RoleRead] = []
    created_at: datetime


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str
    password: str
    role_codes: list[str]
    all_units: bool = False
    unit_ids: list[uuid.UUID] = []
    department_ids: list[uuid.UUID] = []


class UserUpdate(BaseModel):
    full_name: str | None = None
    is_active: bool | None = None
    role_codes: list[str] | None = None
    all_units: bool | None = None
    unit_ids: list[uuid.UUID] | None = None
    department_ids: list[uuid.UUID] | None = None


# --- Organization ---
class OrganizationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    legal_name: str | None = None
    tax_id: str | None = None
    timezone: str
    is_active: bool


class UnitRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    code: str
    address: str | None = None
    timezone: str | None = None
    is_active: bool


class UnitCreate(BaseModel):
    name: str
    code: str
    address: str | None = None
    timezone: str | None = None


class DepartmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    organization_id: uuid.UUID
    unit_id: uuid.UUID | None = None
    name: str
    code: str
    is_active: bool


class DepartmentCreate(BaseModel):
    name: str
    code: str
    unit_id: uuid.UUID | None = None


# --- Employees ---
class EmployeeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    organization_id: uuid.UUID
    unit_id: uuid.UUID
    department_id: uuid.UUID | None = None
    full_name: str
    registration_number: str
    badge_code: str | None = None
    email: str
    phone: str | None = None
    admission_date: date | None = None
    employment_status: str
    biometric_status: str
    access_profile: str
    notes: str | None = None
    created_at: datetime
    updated_at: datetime


class EmployeeCreate(BaseModel):
    full_name: str
    registration_number: str
    badge_code: str | None = None
    email: EmailStr
    phone: str | None = None
    unit_id: uuid.UUID
    department_id: uuid.UUID | None = None
    admission_date: date | None = None
    access_profile: str = "standard"
    notes: str | None = None
    pin: str | None = Field(None, min_length=4, max_length=12)


class EmployeeUpdate(BaseModel):
    full_name: str | None = None
    badge_code: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    unit_id: uuid.UUID | None = None
    department_id: uuid.UUID | None = None
    employment_status: str | None = None
    access_profile: str | None = None
    notes: str | None = None
    pin: str | None = Field(None, min_length=4, max_length=12)


# --- Biometrics ---
class BiometricCaptureRequest(BaseModel):
    employee_id: uuid.UUID
    image_base64: str = Field(..., min_length=1, max_length=4_000_000)


class BiometricEnrollmentRequest(BaseModel):
    employee_id: uuid.UUID
    # Array of Base64-encoded JPEG/PNG images from voluntary enrollment
    images_base64: list[str] = Field(..., min_length=1, max_length=5)
    legal_basis_record_id: uuid.UUID
    privacy_notice_id: uuid.UUID | None = None


class BiometricEnrollmentResponse(BaseModel):
    enrollment_id: uuid.UUID
    employee_id: uuid.UUID
    status: str
    quality_score: float
    liveness_score: float | None
    capture_count: int
    created_at: datetime


# --- Access & Terminals ---
class TerminalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    code: str
    name: str
    unit_id: uuid.UUID
    terminal_type: str
    status: str
    last_seen_at: datetime | None = None
    last_ip: str | None = None
    app_version: str | None = None


class TerminalCreate(BaseModel):
    code: str
    name: str
    unit_id: uuid.UUID
    terminal_type: str = "attendance"
    allowed_operations: list[str] = ["attendance", "pin_fallback"]


class TerminalCreated(TerminalRead):
    activation_code: str


class TerminalActivateRequest(BaseModel):
    code: str
    activation_code: str


class TerminalActivateResponse(BaseModel):
    terminal_id: uuid.UUID
    code: str
    terminal_secret: str
    message: str


# --- Kiosk 1:1 Verification & Attendance ---
class KioskVerifyRequest(BaseModel):
    identifier: str = ""  # empty for automatic face identification; required for PIN
    method: Literal["face", "pin"] = "face"
    image_base64: str | None = None
    pin: str | None = None
    operation_type: Literal["attendance", "access"] = "attendance"
    record_type: Literal["entry", "exit", "break_start", "break_end"] | None = None


class KioskVerifyResponse(BaseModel):
    status: str  # verified | rejected | inconclusive | no_biometrics | pin_fallback_required
    message: str
    employee_name: str | None = None
    employee_id: uuid.UUID | None = None
    attendance_record_id: uuid.UUID | None = None
    access_decision: str | None = None  # granted | denied | review
    similarity: float | None = None
    quality_score: float | None = None
    liveness_passed: bool | None = None
    reasons: list[str] = []
    retryable: bool = False


# --- Attendance & Reports ---
class AttendanceManualCreate(BaseModel):
    employee_id: uuid.UUID
    record_type: str = "entry"  # entry | exit | break_start | break_end
    recorded_at: datetime | None = None
    reason: str = "Registro manual autorizado"


class AttendanceRecordRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    employee_id: uuid.UUID
    employee_name: str | None = None
    record_type: str
    recorded_at: datetime
    local_date: date
    verification_method: str
    result: str
    source: str
    status: str


class DashboardMetrics(BaseModel):
    total_employees: int
    active_employees: int
    inactive_employees: int
    enrolled_biometrics: int
    today_attendances: int
    present_employees: int
    authorized_accesses_today: int
    denied_accesses_today: int
    active_terminals: int
    system_status: str
    timestamp: datetime


# --- Events & Guests ---
class EventCreate(BaseModel):
    unit_id: uuid.UUID
    name: str
    description: str | None = None
    location_name: str | None = None
    starts_at: datetime
    ends_at: datetime
    early_entry_minutes: int = 30
    late_entry_minutes: int = 60


class EventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    unit_id: uuid.UUID
    name: str
    description: str | None = None
    location_name: str | None = None
    starts_at: datetime
    ends_at: datetime
    early_entry_minutes: int
    late_entry_minutes: int
    is_active: bool
    guest_count: int = 0
    created_at: datetime


class EventGuestCreate(BaseModel):
    event_id: uuid.UUID | None = None
    full_name: str
    identifier: str
    email: EmailStr | None = None
    phone: str | None = None
    organization_represented: str | None = None
    pin: str | None = Field(None, min_length=4, max_length=12)


class EventGuestRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    event_id: uuid.UUID
    full_name: str
    identifier: str
    email: str | None = None
    phone: str | None = None
    organization_represented: str | None = None
    biometric_status: str
    status: str
    first_access_at: datetime | None = None
    last_access_at: datetime | None = None
    access_count: int
    created_at: datetime


class GuestBiometricEnroll(BaseModel):
    guest_id: uuid.UUID
    images_base64: list[str] = Field(..., min_length=1, max_length=5)


# --- Blocked Persons (Blacklist) ---
class BlockedPersonCreate(BaseModel):
    full_name: str
    identifier: str
    reason: str


class BlockedPersonRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    organization_id: uuid.UUID | None = None
    full_name: str
    identifier: str
    reason: str
    blocked_by_name: str | None = None
    is_active: bool
    blocked_at: datetime
    unblocked_at: datetime | None = None
    unblocked_reason: str | None = None
    created_at: datetime


class BlockedPersonUnblock(BaseModel):
    unblock_reason: str = "Desbloqueio autorizado administrativamente"
