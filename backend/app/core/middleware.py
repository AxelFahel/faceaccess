"""HTTP middlewares: request id, security headers, body size limit and rate limiting."""
from __future__ import annotations

import logging
import threading
import time
import uuid
from collections import deque

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.config import get_settings

log = logging.getLogger("faceaccess.http")


def client_ip(request: Request) -> str:
    """Resolve client IP honouring only the configured number of trusted proxies."""
    s = get_settings()
    xff = request.headers.get("x-forwarded-for")
    if xff and s.trusted_proxy_count > 0:
        parts = [p.strip() for p in xff.split(",") if p.strip()]
        if len(parts) >= s.trusted_proxy_count:
            return parts[-s.trusted_proxy_count]
    return request.client.host if request.client else "unknown"


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        rid = request.headers.get("x-request-id", "")
        if not rid or len(rid) > 64 or not all(c.isalnum() or c in "-_" for c in rid):
            rid = uuid.uuid4().hex
        request.state.request_id = rid
        request.state.client_ip = client_ip(request)
        start = time.perf_counter()
        response: Response = await call_next(request)
        response.headers["X-Request-ID"] = rid
        # Method/path/status only: never log bodies, query strings or headers.
        log.info("%s %s %s %.1fms rid=%s", request.method, request.url.path, response.status_code,
                 (time.perf_counter() - start) * 1000, rid)
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        h = response.headers
        h.setdefault("X-Content-Type-Options", "nosniff")
        h.setdefault("X-Frame-Options", "DENY")
        h.setdefault("Referrer-Policy", "no-referrer")
        h.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        h.setdefault("Cross-Origin-Resource-Policy", "same-origin")
        h.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        if request.url.path.startswith("/api/"):
            h.setdefault("Cache-Control", "no-store")
            if not request.url.path.startswith("/api/docs"):
                h.setdefault("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'")
        return response


class BodySizeLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        limit = get_settings().max_upload_bytes * 4  # multi-capture enrollment
        cl = request.headers.get("content-length")
        if cl and cl.isdigit() and int(cl) > limit:
            return JSONResponse(
                {"error": {"code": "payload_too_large", "message": "Requisição muito grande.",
                           "details": None, "request_id": getattr(request.state, "request_id", None)}},
                413,
            )
        return await call_next(request)


class SlidingWindowLimiter:
    """In-process sliding-window limiter (single backend replica).

    For multiple replicas, replace with a shared store (e.g. Redis) — documented
    in ARCHITECTURE.md.
    """

    def __init__(self):
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def hit(self, key: str, limit: int, window: float = 60.0) -> bool:
        now = time.monotonic()
        with self._lock:
            q = self._hits.setdefault(key, deque())
            while q and now - q[0] > window:
                q.popleft()
            if len(q) >= limit:
                return False
            q.append(now)
            if len(self._hits) > 50_000:  # memory guard
                self._hits = {k: v for k, v in self._hits.items() if v and now - v[-1] < window}
            return True

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


limiter = SlidingWindowLimiter()


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        s = get_settings()
        path = request.url.path
        if path.startswith("/api/") and not path.startswith("/api/v1/health"):
            ip = getattr(request.state, "client_ip", None) or client_ip(request)
            if path.startswith("/api/v1/auth/login") or path.startswith("/api/v1/auth/mfa"):
                key, limit = f"login:{ip}", s.rate_limit_login_per_minute
            elif path.startswith("/api/v1/kiosk"):
                key, limit = f"kiosk:{ip}", s.rate_limit_terminal_per_minute
            else:
                key, limit = f"api:{ip}", s.rate_limit_default_per_minute
            if not limiter.hit(key, limit):
                return JSONResponse(
                    {"error": {"code": "rate_limited", "message": "Muitas requisições. Aguarde e tente novamente.",
                               "details": None, "request_id": getattr(request.state, "request_id", None)}},
                    429,
                    headers={"Retry-After": "60"},
                )
        return await call_next(request)
