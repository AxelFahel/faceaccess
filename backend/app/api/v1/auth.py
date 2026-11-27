"""Authentication API routes: login, logout, refresh, MFA and profile."""
from __future__ import annotations

import base64
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import AuthenticatedPrincipal, get_current_user
from app.core.config import get_settings
from app.core.crypto import random_token, sha256_hex
from app.core.errors import Forbidden, Unauthorized
from app.core.security import (
    create_token,
    decode_token,
    hash_secret,
    new_totp_secret,
    totp_uri,
    verify_secret,
    verify_totp,
)
from app.db.session import get_db
from app.models.auth import Role, User, UserSession
from app.schemas.dto import (
    LoginRequest,
    LoginResponse,
    MessageResponse,
    MfaVerifyRequest,
    RefreshTokenRequest,
    UserRead,
)
from app.services.audit import AuditService

router = APIRouter(prefix="/auth", tags=["Autenticação"])


@router.post("/login", response_model=LoginResponse)
def login(
    req: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    s = get_settings()
    user = db.execute(select(User).where(User.email == req.email)).scalar_one_or_none()

    now = datetime.now(UTC)
    if not user or not user.is_active:
        # Dummy check to equalize timing
        verify_secret(None, req.password)
        AuditService.record(
            db, actor_type="anonymous", action="auth:login_failed",
            result="failure", ip_address=request.state.client_ip,
            details={"email": req.email, "reason": "not_found_or_inactive"}
        )
        raise Unauthorized("E-mail ou senha incorretos.")

    if user.locked_until and user.locked_until > now:
        raise Forbidden("Conta bloqueada temporariamente devido a sucessivas tentativas incorretas.")

    if not verify_secret(user.password_hash, req.password):
        user.failed_login_count += 1
        if user.failed_login_count >= s.login_max_failures:
            user.locked_until = now + timedelta(minutes=s.login_lockout_minutes)
        db.commit()
        AuditService.record(
            db, actor_type="user", actor_id=str(user.id), action="auth:login_failed",
            result="failure", ip_address=request.state.client_ip,
            details={"reason": "invalid_password", "failed_count": user.failed_login_count}
        )
        raise Unauthorized("E-mail ou senha incorretos.")

    # Reset failure counters
    user.failed_login_count = 0
    user.locked_until = None
    user.last_login_at = now

    # Check MFA requirement
    user_roles = {r.code for r in user.roles}
    mfa_required = user.mfa_enabled or any(r in s.mfa_required_roles for r in user_roles)

    if mfa_required and user.mfa_enabled:
        # Return MFA ticket
        ticket = create_token(
            str(user.id),
            token_type="mfa_ticket",
            ttl=timedelta(minutes=s.mfa_setup_token_ttl_minutes),
        )
        db.commit()
        return LoginResponse(
            access_token="",
            expires_in=0,
            mfa_required=True,
            mfa_ticket=ticket,
        )

    # Issue access and refresh tokens
    access_token = create_token(
        str(user.id),
        token_type="access",
        ttl=timedelta(minutes=s.access_token_ttl_minutes),
        extra={"tv": user.token_version, "roles": list(user_roles)},
    )
    raw_refresh = random_token(48)
    rf_hash = sha256_hex(raw_refresh)
    session = UserSession(
        user_id=user.id,
        family_id=uuid.uuid4(),
        refresh_token_hash=rf_hash,
        created_at=now,
        expires_at=now + timedelta(hours=s.refresh_token_ttl_hours),
        ip_address=request.state.client_ip,
        user_agent=request.headers.get("user-agent"),
    )
    db.add(session)
    db.commit()

    if s.cookie_secure:
        response.set_cookie(
            key="access_token",
            value=access_token,
            httponly=True,
            secure=True,
            samesite="lax",
            max_age=s.access_token_ttl_minutes * 60,
        )
        response.set_cookie(
            key="refresh_token",
            value=raw_refresh,
            httponly=True,
            secure=True,
            samesite="lax",
            max_age=s.refresh_token_ttl_hours * 3600,
            path="/api/v1/auth/refresh",
        )

    AuditService.record(
        db, actor_type="user", actor_id=str(user.id), actor_label=user.email,
        action="auth:login_success", ip_address=request.state.client_ip
    )

    return LoginResponse(
        access_token=access_token,
        expires_in=s.access_token_ttl_minutes * 60,
        must_change_password=user.must_change_password,
        mfa_required=False,
        user=UserRead.model_validate(user),
    )


@router.post("/mfa/verify", response_model=LoginResponse)
def verify_mfa(
    req: MfaVerifyRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    s = get_settings()
    try:
        payload = decode_token(req.mfa_ticket, expected_type="mfa_ticket")
    except Exception:
        raise Unauthorized("Ticket MFA expirado ou inválido.")

    user = db.get(User, uuid.UUID(payload["sub"]))
    if not user or not user.is_active:
        raise Unauthorized("Usuário inválido.")

    if not user.mfa_secret_enc:
        raise Unauthorized("MFA não configurado.")

    # Decrypt TOTP secret
    from app.core.crypto import decrypt_str
    totp_secret = decrypt_str(user.mfa_secret_enc, f"mfa:{user.id}")

    if not verify_totp(totp_secret, req.code):
        AuditService.record(
            db, actor_type="user", actor_id=str(user.id), action="auth:mfa_failed",
            result="failure", ip_address=request.state.client_ip
        )
        raise Unauthorized("Código de segundo fator inválido.")

    now = datetime.now(UTC)
    user_roles = {r.code for r in user.roles}
    access_token = create_token(
        str(user.id),
        token_type="access",
        ttl=timedelta(minutes=s.access_token_ttl_minutes),
        extra={"tv": user.token_version, "roles": list(user_roles)},
    )
    raw_refresh = random_token(48)
    session = UserSession(
        user_id=user.id,
        family_id=uuid.uuid4(),
        refresh_token_hash=sha256_hex(raw_refresh),
        created_at=now,
        expires_at=now + timedelta(hours=s.refresh_token_ttl_hours),
        ip_address=request.state.client_ip,
        user_agent=request.headers.get("user-agent"),
    )
    db.add(session)
    db.commit()

    return LoginResponse(
        access_token=access_token,
        expires_in=s.access_token_ttl_minutes * 60,
        must_change_password=user.must_change_password,
        mfa_required=False,
        user=UserRead.model_validate(user),
    )


@router.post("/refresh", response_model=LoginResponse)
def refresh_token(
    req: RefreshTokenRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    s = get_settings()
    raw_token = req.refresh_token or request.cookies.get("refresh_token")
    if not raw_token:
        raise Unauthorized("Refresh token não informado.")

    token_hash = sha256_hex(raw_token)
    session = db.execute(
        select(UserSession).where(UserSession.refresh_token_hash == token_hash)
    ).scalar_one_or_none()

    now = datetime.now(UTC)
    if not session:
        raise Unauthorized("Sessão não encontrada.")

    # Re-use detection: if session already replaced or revoked, revoke entire family
    if session.revoked_at or session.replaced_at:
        db.query(UserSession).filter(UserSession.family_id == session.family_id).update(
            {"revoked_at": now, "revoke_reason": "token_reuse_detected"}
        )
        db.commit()
        raise Unauthorized("Tentativa de reuso de token detectada. Sessão invalidada.")

    if session.expires_at < now:
        session.revoked_at = now
        session.revoke_reason = "expired"
        db.commit()
        raise Unauthorized("Refresh token expirado.")

    user = db.get(User, session.user_id)
    if not user or not user.is_active:
        raise Unauthorized("Usuário inválido ou inativo.")

    # Issue new rotated refresh token
    new_raw_refresh = random_token(48)
    new_hash = sha256_hex(new_raw_refresh)
    session.replaced_at = now

    new_session = UserSession(
        user_id=user.id,
        family_id=session.family_id,
        refresh_token_hash=new_hash,
        created_at=now,
        expires_at=now + timedelta(hours=s.refresh_token_ttl_hours),
        ip_address=request.state.client_ip,
        user_agent=request.headers.get("user-agent"),
    )
    db.add(new_session)

    user_roles = {r.code for r in user.roles}
    access_token = create_token(
        str(user.id),
        token_type="access",
        ttl=timedelta(minutes=s.access_token_ttl_minutes),
        extra={"tv": user.token_version, "roles": list(user_roles)},
    )
    db.commit()

    return LoginResponse(
        access_token=access_token,
        expires_in=s.access_token_ttl_minutes * 60,
        user=UserRead.model_validate(user),
    )


@router.get("/me", response_model=UserRead)
def get_me(
    principal: AuthenticatedPrincipal = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = db.get(User, principal.id)
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")
    return UserRead.model_validate(user)
