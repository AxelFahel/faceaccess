"""Dependency injection for FastAPI routes: authentication, RBAC, scopes, database."""
from __future__ import annotations

import uuid
from typing import Annotated, Callable

from fastapi import Depends, Header, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.crypto import constant_time_equals, sha256_hex
from app.core.errors import Forbidden, Unauthorized
from app.core.permissions import GLOBAL_SCOPE_ROLES
from app.core.security import decode_token
from app.db.session import get_db
from app.models.access import Terminal, TerminalStatus
from app.models.auth import User


class AuthenticatedPrincipal:
    def __init__(
        self,
        principal_type: str,
        id: uuid.UUID,
        label: str,
        permissions: set[str],
        roles: set[str],
        organization_id: uuid.UUID | None = None,
        unit_ids: set[uuid.UUID] | None = None,
        department_ids: set[uuid.UUID] | None = None,
        all_units: bool = False,
    ):
        self.principal_type = principal_type  # user | terminal
        self.id = id
        self.label = label
        self.permissions = permissions
        self.roles = roles
        self.organization_id = organization_id
        self.unit_ids = unit_ids or set()
        self.department_ids = department_ids or set()
        self.all_units = all_units

    def has_permission(self, perm: str) -> bool:
        return perm in self.permissions or "superadmin" in self.roles

    def can_access_unit(self, unit_id: uuid.UUID | None) -> bool:
        if self.all_units or any(r in GLOBAL_SCOPE_ROLES for r in self.roles):
            return True
        if unit_id is None:
            return True
        return unit_id in self.unit_ids

    def can_access_department(self, dept_id: uuid.UUID | None) -> bool:
        if self.all_units or any(r in GLOBAL_SCOPE_ROLES for r in self.roles):
            return True
        if not self.department_ids:
            return True
        if dept_id is None:
            return True
        return dept_id in self.department_ids


def get_current_user(
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
    db: Session = Depends(get_db),
) -> AuthenticatedPrincipal:
    token = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:].strip()
    elif "access_token" in request.cookies:
        token = request.cookies.get("access_token")

    if not token:
        raise Unauthorized("Credenciais de autenticação ausentes.")

    try:
        payload = decode_token(token, expected_type="access")
    except Exception as exc:
        raise Unauthorized(f"Token inválido ou expirado: {exc}")

    user_id = uuid.UUID(payload["sub"])
    user = db.get(User, user_id)
    if not user or not user.is_active:
        raise Unauthorized("Usuário inativo ou não encontrado.")

    if payload.get("tv", 0) < user.token_version:
        raise Unauthorized("Sessão revogada.")

    perms = user.permission_codes
    roles = user.role_codes
    unit_ids = {u.id for u in user.unit_scopes}
    dept_ids = {d.id for d in user.department_scopes}

    return AuthenticatedPrincipal(
        principal_type="user",
        id=user.id,
        label=user.email,
        permissions=perms,
        roles=roles,
        organization_id=user.organization_id,
        unit_ids=unit_ids,
        department_ids=dept_ids,
        all_units=user.all_units,
    )


def require_permission(permission: str) -> Callable:
    def dependency(
        principal: AuthenticatedPrincipal = Depends(get_current_user),
    ) -> AuthenticatedPrincipal:
        if not principal.has_permission(permission):
            raise Forbidden(f"Permissão insuficiente: {permission}")
        return principal
    return dependency


def get_current_terminal(
    request: Request,
    x_terminal_code: Annotated[str | None, Header(alias="X-Terminal-Code")] = None,
    x_terminal_secret: Annotated[str | None, Header(alias="X-Terminal-Secret")] = None,
    db: Session = Depends(get_db),
) -> AuthenticatedPrincipal:
    if not x_terminal_code or not x_terminal_secret:
        raise Unauthorized("Credenciais de terminal ausentes.")

    terminal = db.execute(
        select(Terminal).where(Terminal.code == x_terminal_code)
    ).scalar_one_or_none()

    if not terminal:
        raise Unauthorized("Terminal não encontrado.")
    if terminal.status != TerminalStatus.ACTIVE:
        raise Unauthorized(f"Terminal inativo ou revogado (status: {terminal.status}).")

    if not terminal.credential_hash:
        raise Unauthorized("Terminal sem credencial ativa configurada.")

    # Validate credential hash
    input_hash = sha256_hex(x_terminal_secret)
    if not constant_time_equals(input_hash, terminal.credential_hash):
        raise Unauthorized("Credencial de terminal incorreta.")

    return AuthenticatedPrincipal(
        principal_type="terminal",
        id=terminal.id,
        label=f"Terminal {terminal.code} ({terminal.name})",
        permissions={"terminal:operate"},
        roles={"terminal"},
        unit_ids={terminal.unit_id},
    )
