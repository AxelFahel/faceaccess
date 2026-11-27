"""Tamper-evident audit service.

Every mutation or sensitive read produces an AuditLog entry linked to the
previous entry by SHA-256 hash chaining and authenticated via HMAC.
NEVER records passwords, tokens, raw biometric templates or image bytes.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.crypto import hmac_sha256_hex, sha256_hex
from app.models.privacy import AuditLog

GENESIS_HASH = "0000000000000000000000000000000000000000000000000000000000000000"


def _sanitize_details(d: dict[str, Any] | None) -> dict[str, Any]:
    if not d:
        return {}
    clean = {}
    sensitive_keys = {
        "password", "secret", "token", "refresh_token", "pin", "mfa_secret",
        "template", "image", "embedding", "key", "credential"
    }
    for k, v in d.items():
        if any(sk in k.lower() for sk in sensitive_keys):
            clean[k] = "[REDACTED]"
        elif isinstance(v, dict):
            clean[k] = _sanitize_details(v)
        elif isinstance(v, (list, tuple)):
            clean[k] = [
                _sanitize_details(x) if isinstance(x, dict) else x
                for x in v
            ]
        else:
            clean[k] = v
    return clean


class AuditService:
    @staticmethod
    def get_latest_hash(db: Session) -> str:
        latest = db.execute(
            select(AuditLog.hash).order_by(AuditLog.seq.desc()).limit(1)
        ).scalar_one_or_none()
        return latest or GENESIS_HASH

    @classmethod
    def record(
        cls,
        db: Session,
        *,
        actor_type: str,
        actor_id: str | None = None,
        actor_label: str | None = None,
        action: str,
        resource_type: str | None = None,
        resource_id: str | None = None,
        result: str = "success",
        ip_address: str | None = None,
        user_agent: str | None = None,
        request_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> AuditLog:
        now = datetime.now(UTC)
        prev_hash = cls.get_latest_hash(db)
        sanitized_details = _sanitize_details(details)

        # Hash entry payload
        entry_payload = {
            "created_at": now.isoformat(),
            "actor_type": actor_type,
            "actor_id": str(actor_id) if actor_id else None,
            "action": action,
            "resource_type": resource_type,
            "resource_id": str(resource_id) if resource_id else None,
            "result": result,
            "prev_hash": prev_hash,
            "details": sanitized_details,
        }
        serialized = json.dumps(entry_payload, sort_keys=True)
        s = get_settings()
        curr_hash = hmac_sha256_hex(s.audit_hmac_key, serialized)

        log = AuditLog(
            created_at=now,
            actor_type=actor_type,
            actor_id=str(actor_id) if actor_id else None,
            actor_label=actor_label,
            action=action,
            resource_type=resource_type,
            resource_id=str(resource_id) if resource_id else None,
            result=result,
            ip_address=ip_address,
            user_agent=user_agent[:300] if user_agent else None,
            request_id=request_id,
            details=sanitized_details,
            prev_hash=prev_hash,
            hash=curr_hash,
        )
        db.add(log)
        db.flush()
        return log
