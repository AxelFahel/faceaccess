"""FastAPI Application factory and router mount."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.auth import router as auth_router
from app.api.v1.biometrics import router as biometrics_router
from app.api.v1.blocked import router as blocked_router
from app.api.v1.employees import router as employees_router
from app.api.v1.events import router as events_router
from app.api.v1.kiosk import router as kiosk_router
from app.api.v1.schedules import router as schedules_router
from app.api.v1.management import (
    attendance_router,
    dashboard_router,
    org_router,
    reports_router,
    terminals_router,
)
from app.api.v1.privacy import router as privacy_router
from app.core.config import get_settings
from app.core.errors import install_exception_handlers
from app.core.middleware import (
    BodySizeLimitMiddleware,
    RateLimitMiddleware,
    RequestContextMiddleware,
    SecurityHeadersMiddleware,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup verification
    s = get_settings()
    s.validate_for_runtime()
    yield
    # Shutdown cleanup


def create_app() -> FastAPI:
    s = get_settings()
    app = FastAPI(
        title=s.app_name,
        version=s.app_version,
        docs_url="/api/docs" if s.enable_api_docs else None,
        redoc_url="/api/redoc" if s.enable_api_docs else None,
        openapi_url="/api/openapi.json" if s.enable_api_docs else None,
        lifespan=lifespan,
    )

    # Middlewares (outermost executed first)
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(BodySizeLimitMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestContextMiddleware)

    if s.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=s.cors_origins,
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            allow_headers=["*"],
        )

    install_exception_handlers(app)

    # Mount API v1 routes
    v1_prefix = "/api/v1"
    app.include_router(auth_router, prefix=v1_prefix)
    app.include_router(employees_router, prefix=v1_prefix)
    app.include_router(biometrics_router, prefix=v1_prefix)
    app.include_router(kiosk_router, prefix=v1_prefix)
    app.include_router(org_router, prefix=v1_prefix)
    app.include_router(terminals_router, prefix=v1_prefix)
    app.include_router(attendance_router, prefix=v1_prefix)
    app.include_router(dashboard_router, prefix=v1_prefix)
    app.include_router(reports_router, prefix=v1_prefix)
    app.include_router(privacy_router, prefix=v1_prefix)
    app.include_router(events_router, prefix=v1_prefix)
    app.include_router(blocked_router, prefix=v1_prefix)
    app.include_router(schedules_router, prefix=v1_prefix)

    @app.get("/api/v1/health", tags=["Health"])
    def health():
        return {"status": "ok", "app": s.app_name, "version": s.app_version}

    return app


app = create_app()
