"""Health, readiness, version, metrics endpoints — used by load balancer + monitors."""
import os
import time
from fastapi import APIRouter

from deps import db, logger
from middleware import MetricsMiddleware

router = APIRouter()

_BOOT_TS = time.time()
_VERSION = os.environ.get("APP_VERSION", "dev")
_GIT_SHA = os.environ.get("GIT_SHA", "unknown")


@router.get("/health")
async def health() -> dict:
    """Liveness probe — process is up."""
    return {"status": "ok", "service": "a1-field-pro", "version": _VERSION,
            "git_sha": _GIT_SHA, "uptime_s": int(time.time() - _BOOT_TS),
            "sentry": bool(os.environ.get("SENTRY_DSN"))}


@router.get("/health/ready")
async def ready() -> dict:
    """Readiness — DB reachable and writable."""
    try:
        await db.command("ping")
        return {"ready": True, "db": "ok"}
    except Exception as e:
        logger.error(f"readiness: db ping failed: {e}")
        return {"ready": False, "db": str(e)[:200]}


@router.get("/metrics")
async def metrics() -> dict:
    """JSON metrics (Prometheus exporter can scrape this via a sidecar)."""
    return {
        "version": _VERSION,
        "uptime_s": int(time.time() - _BOOT_TS),
        "requests_by_route": dict(MetricsMiddleware.counters),
        "avg_latency_ms_by_route": {
            r: round((MetricsMiddleware.latency_sum[r] / max(MetricsMiddleware.latency_count[r], 1)) * 1000, 2)
            for r in MetricsMiddleware.counters
        },
        "status_codes": dict(MetricsMiddleware.status_counts),
    }


@router.get("/metrics/prom")
async def metrics_prom():
    """Bare-bones Prometheus exposition format (text/plain)."""
    lines: list[str] = []
    lines.append("# HELP a1fp_uptime_seconds Process uptime in seconds")
    lines.append("# TYPE a1fp_uptime_seconds counter")
    lines.append(f"a1fp_uptime_seconds {int(time.time() - _BOOT_TS)}")
    lines.append("# HELP a1fp_requests_total Total HTTP requests by route prefix")
    lines.append("# TYPE a1fp_requests_total counter")
    for route, count in MetricsMiddleware.counters.items():
        lines.append(f'a1fp_requests_total{{route="{route}"}} {count}')
    lines.append("# HELP a1fp_request_latency_ms_avg Average request latency in milliseconds")
    lines.append("# TYPE a1fp_request_latency_ms_avg gauge")
    for route in MetricsMiddleware.counters:
        avg = (MetricsMiddleware.latency_sum[route] / max(MetricsMiddleware.latency_count[route], 1)) * 1000
        lines.append(f'a1fp_request_latency_ms_avg{{route="{route}"}} {avg:.2f}')
    for code, n in MetricsMiddleware.status_counts.items():
        lines.append(f'a1fp_responses_total{{status="{code}"}} {n}')
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse("\n".join(lines) + "\n")
