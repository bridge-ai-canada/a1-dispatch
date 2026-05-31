"""Production middleware — security headers, request ID, simple rate limiting.

All middleware here is additive and tolerates missing config. Designed to be
safe under both single-pod dev and multi-pod production deployments.
"""
import asyncio
import os
import time
import uuid
from collections import defaultdict, deque
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, JSONResponse


# -------------------- Request ID --------------------
class RequestIDMiddleware(BaseHTTPMiddleware):
    """Attach an X-Request-ID to every request/response for traceability."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        rid = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:16]
        request.state.request_id = rid
        # Tag Sentry scope (best-effort — no-op if Sentry not initialized)
        try:
            import sentry_sdk
            sentry_sdk.set_tag("request_id", rid)
        except Exception:
            pass
        try:
            response = await call_next(request)
        except Exception:
            raise
        response.headers["X-Request-ID"] = rid
        return response


# -------------------- Security headers --------------------
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """SOC2-friendly response headers (CSP relaxed for the API host;
    front-end host should override CSP via nginx)."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        h = response.headers
        h.setdefault("X-Content-Type-Options", "nosniff")
        h.setdefault("X-Frame-Options", "DENY")
        h.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        h.setdefault("Permissions-Policy", "geolocation=(self), microphone=(), camera=()")
        h.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        h.setdefault("X-XSS-Protection", "0")
        return response


# -------------------- In-memory token-bucket rate limiter --------------------
class RateLimitMiddleware(BaseHTTPMiddleware):
    """Token-bucket per IP + per route prefix. Defaults are deliberately lenient
    to avoid impacting normal traffic; tighten per-route in env.

    Env:
      RATE_LIMIT_DEFAULT_RPM=600   (requests / minute / IP)
      RATE_LIMIT_AUTH_RPM=20       (auth endpoints)
    """

    def __init__(self, app, default_rpm: int = 600, auth_rpm: int = 20):
        super().__init__(app)
        self.default_rpm = int(os.environ.get("RATE_LIMIT_DEFAULT_RPM", default_rpm))
        self.auth_rpm = int(os.environ.get("RATE_LIMIT_AUTH_RPM", auth_rpm))
        self._hits: dict[str, deque] = defaultdict(deque)
        self._lock = asyncio.Lock()

    def _key(self, request: Request) -> tuple[str, int]:
        # Honor X-Forwarded-For so we don't rate-limit by the ingress address.
        xff = request.headers.get("x-forwarded-for", "")
        ip = xff.split(",")[0].strip() if xff else (request.client.host if request.client else "unknown")
        path = request.url.path
        if path.startswith("/api/auth/login") or path.startswith("/api/auth/register") \
                or path.startswith("/api/auth/forgot") or path.startswith("/api/auth/reset"):
            return f"{ip}|auth", self.auth_rpm
        return f"{ip}|default", self.default_rpm

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.method in ("OPTIONS", "HEAD"):
            return await call_next(request)
        key, limit = self._key(request)
        now = time.time()
        window = 60.0
        async with self._lock:
            dq = self._hits[key]
            while dq and now - dq[0] > window:
                dq.popleft()
            if len(dq) >= limit:
                retry = int(window - (now - dq[0]))
                return JSONResponse(
                    {"detail": "Rate limit exceeded", "retry_after": retry},
                    status_code=429,
                    headers={"Retry-After": str(retry)},
                )
            dq.append(now)
        return await call_next(request)


# -------------------- Tiny metrics counter --------------------
class MetricsMiddleware(BaseHTTPMiddleware):
    """Counts requests + latencies per route prefix. Exposed via /api/metrics."""

    counters: dict[str, int] = defaultdict(int)
    latency_sum: dict[str, float] = defaultdict(float)
    latency_count: dict[str, int] = defaultdict(int)
    status_counts: dict[int, int] = defaultdict(int)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.url.path
        bucket = "/api/" + (path.split("/api/", 1)[-1].split("/", 1)[0] if "/api/" in path else "other")
        t0 = time.perf_counter()
        response = await call_next(request)
        dt = time.perf_counter() - t0
        self.counters[bucket] += 1
        self.latency_sum[bucket] += dt
        self.latency_count[bucket] += 1
        self.status_counts[response.status_code] += 1
        return response
