"""Slow-request logger + simple in-memory cache for hot read paths.

Used in production to flag p95 outliers and reduce Mongo read pressure.
"""
import os
import time
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from deps import logger

SLOW_THRESHOLD_MS = int(os.environ.get("SLOW_REQUEST_THRESHOLD_MS", 800))


class SlowRequestLoggerMiddleware(BaseHTTPMiddleware):
    """Emit a structured log line whenever a request exceeds SLOW_THRESHOLD_MS.
    Sentry / CloudWatch can be wired to alert on these."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        t0 = time.perf_counter()
        response = await call_next(request)
        dt_ms = (time.perf_counter() - t0) * 1000
        if dt_ms >= SLOW_THRESHOLD_MS:
            rid = getattr(request.state, "request_id", "-")
            logger.warning(
                "slow_request rid=%s method=%s path=%s status=%s duration_ms=%.0f",
                rid, request.method, request.url.path, response.status_code, dt_ms,
            )
        # Always tag response so clients/proxies can correlate
        response.headers["X-Response-Time-ms"] = f"{dt_ms:.0f}"
        return response


# ----------------------- TTL cache ---------------------------------
class _TTLCache:
    """Thread-unsafe but asyncio-safe (single event loop) in-memory cache."""

    def __init__(self):
        self._store: dict[str, tuple[float, object]] = {}

    def get(self, key: str):
        item = self._store.get(key)
        if not item:
            return None
        exp, value = item
        if exp < time.time():
            self._store.pop(key, None)
            return None
        return value

    def set(self, key: str, value, ttl: float):
        self._store[key] = (time.time() + ttl, value)

    def invalidate_prefix(self, prefix: str) -> int:
        keys = [k for k in self._store if k.startswith(prefix)]
        for k in keys:
            self._store.pop(k, None)
        return len(keys)


cache = _TTLCache()
