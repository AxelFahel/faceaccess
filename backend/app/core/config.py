"""Application configuration loaded from environment variables / Docker secrets.

No secret has a usable default: in production the application refuses to start
when required secrets are missing or weak.
"""
from __future__ import annotations

import base64
import json
import os
from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_SECRETS_DIR = "/run/secrets" if os.path.isdir("/run/secrets") else None


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=None,
        secrets_dir=_SECRETS_DIR,
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "FaceAccess"
    app_version: str = "1.0.0"
    app_env: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"

    # --- Database -------------------------------------------------------
    database_url: str = Field(..., description="URL used by the application (least-privilege role)")
    migration_database_url: str | None = Field(None, description="URL used by Alembic (owner role)")
    db_pool_size: int = 10

    # --- Auth -----------------------------------------------------------
    jwt_secret: str = Field(..., min_length=32)
    jwt_issuer: str = "faceaccess"
    access_token_ttl_minutes: int = 10
    refresh_token_ttl_hours: int = 12
    mfa_setup_token_ttl_minutes: int = 10
    mfa_required_roles: list[str] = ["superadmin", "admin"]
    cookie_secure: bool = True
    password_min_length: int = 12
    login_max_failures: int = 5
    login_lockout_minutes: int = 15

    # --- Crypto ---------------------------------------------------------
    # JSON object {"key_id": "<base64 32 bytes>"}; the active id encrypts, all ids decrypt.
    biometric_keys: str = Field(..., description="Key ring for biometric templates")
    biometric_active_key_id: str = Field(...)
    # Separate key for TOTP secrets & other non-biometric secrets at rest.
    data_encryption_key: str = Field(..., description="base64 32-byte key")
    audit_hmac_key: str = Field(..., min_length=32)

    # --- HTTP -----------------------------------------------------------
    cors_origins: list[str] = []
    enable_api_docs: bool = False
    trusted_proxy_count: int = 1
    max_upload_bytes: int = 3_000_000
    rate_limit_login_per_minute: int = 10
    rate_limit_default_per_minute: int = 300
    rate_limit_terminal_per_minute: int = 60

    # --- Domain ---------------------------------------------------------
    timezone: str = "America/Fortaleza"
    attendance_duplicate_window_seconds: int = 120
    terminal_online_seconds: int = 300
    terminal_activation_ttl_minutes: int = 60
    max_failed_verifications_before_manual: int = 3

    # --- Biometrics -----------------------------------------------------
    biometric_engine: Literal["uniface", "fake"] = "uniface"
    uniface_cache_dir: str = "/models"
    biometric_allow_model_download: bool = False
    biometric_providers: list[str] = ["CPUExecutionProvider"]
    # Cosine similarity thresholds (AdaFace IR-18). MUST be calibrated locally.
    match_threshold: float = 0.45
    identification_min_margin: float = Field(0.08, ge=0, le=2)
    inconclusive_threshold: float = 0.30
    liveness_threshold: float = 0.70
    liveness_enabled: bool = True
    quality_min_score: float = 0.35
    min_face_size_ratio: float = 0.18
    min_brightness: float = 60.0
    max_brightness: float = 200.0
    min_sharpness: float = 40.0
    enrollment_captures: int = Field(3, ge=1, le=5)
    enrollment_min_consistency: float = 0.55

    # --- Background jobs ------------------------------------------------
    enable_scheduler: bool = True
    retention_interval_hours: int = 24

    # --- Bootstrap ------------------------------------------------------
    bootstrap_admin_email: str | None = None
    bootstrap_admin_password: str | None = None

    @field_validator("cors_origins", "mfa_required_roles", "biometric_providers", mode="before")
    @classmethod
    def _split_csv(cls, v):  # noqa: N805
        if isinstance(v, str):
            v = v.strip()
            if v.startswith("["):
                return json.loads(v)
            return [s.strip() for s in v.split(",") if s.strip()]
        return v

    # ------------------------------------------------------------------
    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    def biometric_key_ring(self) -> dict[str, bytes]:
        raw = json.loads(self.biometric_keys)
        ring = {kid: base64.b64decode(val) for kid, val in raw.items()}
        for kid, key in ring.items():
            if len(key) != 32:
                raise ValueError(f"Biometric key '{kid}' must be 32 bytes (AES-256)")
        if self.biometric_active_key_id not in ring:
            raise ValueError("BIOMETRIC_ACTIVE_KEY_ID not present in BIOMETRIC_KEYS")
        return ring

    def data_key(self) -> bytes:
        key = base64.b64decode(self.data_encryption_key)
        if len(key) != 32:
            raise ValueError("DATA_ENCRYPTION_KEY must be 32 bytes base64")
        return key

    def validate_for_runtime(self) -> None:
        """Fail fast on insecure configuration."""
        self.biometric_key_ring()
        self.data_key()
        weak = {"change-me", "changeme", "secret", "password"}
        for name in ("jwt_secret", "audit_hmac_key"):
            if getattr(self, name).lower() in weak:
                raise ValueError(f"{name.upper()} is a placeholder value")
        if self.is_production:
            if not self.cookie_secure:
                raise ValueError("COOKIE_SECURE must be true in production")
            if "*" in self.cors_origins:
                raise ValueError("Wildcard CORS is not allowed in production")
            if self.biometric_engine == "fake":
                raise ValueError("The fake biometric engine is not allowed in production")


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
