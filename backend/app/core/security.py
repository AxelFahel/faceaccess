"""Password hashing (Argon2id), JWT issuing/validation and TOTP helpers."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
import pyotp
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from app.core.config import get_settings

# argon2-cffi defaults to Argon2id (RFC 9106 low-memory profile).
_hasher = PasswordHasher()
_DUMMY_HASH = _hasher.hash("dummy-password-for-timing-equalisation")


def hash_secret(value: str) -> str:
    return _hasher.hash(value)


def verify_secret(stored_hash: str | None, value: str) -> bool:
    """Constant-ish time verification; runs a dummy verify when hash is absent."""
    try:
        return _hasher.verify(stored_hash or _DUMMY_HASH, value) and stored_hash is not None
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(stored_hash: str) -> bool:
    return _hasher.check_needs_rehash(stored_hash)


COMMON_PASSWORDS = {
    "123456789012", "password1234", "senha1234567", "qwertyuiop12", "administrador",
    "faceaccess123", "admin1234567",
}


def password_policy_errors(password: str) -> list[str]:
    s = get_settings()
    errors = []
    if len(password) < s.password_min_length:
        errors.append(f"A senha deve ter ao menos {s.password_min_length} caracteres.")
    classes = sum(
        [any(c.islower() for c in password), any(c.isupper() for c in password),
         any(c.isdigit() for c in password), any(not c.isalnum() for c in password)]
    )
    if classes < 3:
        errors.append("Use ao menos 3 tipos: minúsculas, maiúsculas, números e símbolos.")
    if password.lower() in COMMON_PASSWORDS:
        errors.append("Senha muito comum.")
    return errors


# --- JWT ---------------------------------------------------------------

ALGORITHM = "HS256"


def create_token(subject: str, token_type: str, ttl: timedelta, extra: dict[str, Any] | None = None) -> str:
    s = get_settings()
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": subject,
        "typ": token_type,
        "iss": s.jwt_issuer,
        "iat": int(now.timestamp()),
        "nbf": int(now.timestamp()),
        "exp": int((now + ttl).timestamp()),
        "jti": uuid.uuid4().hex,
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, s.jwt_secret, algorithm=ALGORITHM)


def decode_token(token: str, expected_type: str) -> dict[str, Any]:
    s = get_settings()
    payload = jwt.decode(
        token,
        s.jwt_secret,
        algorithms=[ALGORITHM],
        issuer=s.jwt_issuer,
        options={"require": ["exp", "iat", "sub", "typ"]},
    )
    if payload.get("typ") != expected_type:
        raise jwt.InvalidTokenError("wrong token type")
    return payload


# --- TOTP --------------------------------------------------------------

def new_totp_secret() -> str:
    return pyotp.random_base32()


def totp_uri(secret: str, account: str) -> str:
    return pyotp.TOTP(secret).provisioning_uri(name=account, issuer_name=get_settings().app_name)


def verify_totp(secret: str, code: str) -> bool:
    code = (code or "").strip().replace(" ", "")
    if not code.isdigit() or len(code) != 6:
        return False
    return pyotp.TOTP(secret).verify(code, valid_window=1)
