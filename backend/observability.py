"""Sentry initialization for backend.

Activates ONLY when SENTRY_DSN is set in env — silent no-op otherwise so dev
and tests never accidentally ship events. Captures:
- Uncaught exceptions (via FastAPI/Starlette integrations)
- Slow request log records (from perf.SlowRequestLoggerMiddleware) tagged at WARNING
- App version + git sha tags for release tracking
- Request IDs (from RequestIDMiddleware) as scope tags
"""
import logging
import os


def init_sentry() -> bool:
    """Return True if Sentry was initialized, False otherwise."""
    dsn = os.environ.get("SENTRY_DSN")
    if not dsn:
        return False
    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.starlette import StarletteIntegration
        from sentry_sdk.integrations.logging import LoggingIntegration
        from sentry_sdk.integrations.asyncio import AsyncioIntegration
    except Exception as e:
        logging.getLogger("a1fieldpro").error(f"sentry: import failed: {e}")
        return False

    env = os.environ.get("APP_ENV") or os.environ.get("APP_VERSION", "dev")
    release_tag = os.environ.get("GIT_SHA") or os.environ.get("APP_VERSION") or "dev"

    sentry_sdk.init(
        dsn=dsn,
        environment=env,
        release=f"a1-field-pro@{release_tag}",
        # Performance — sampled fraction of requests get full trace data
        traces_sample_rate=float(os.environ.get("SENTRY_TRACES_SAMPLE_RATE", "0.1")),
        # Profiling (Sentry feature) — small overhead, set to 0 to disable
        profiles_sample_rate=float(os.environ.get("SENTRY_PROFILES_SAMPLE_RATE", "0.0")),
        # Send PII (user emails, IPs) — leave OFF by default for SOC2; opt-in
        send_default_pii=os.environ.get("SENTRY_SEND_PII", "false").lower() == "true",
        attach_stacktrace=True,
        max_breadcrumbs=50,
        integrations=[
            StarletteIntegration(transaction_style="endpoint"),
            FastApiIntegration(transaction_style="endpoint"),
            AsyncioIntegration(),
            # WARNING+ logs become breadcrumbs, ERROR+ become events
            LoggingIntegration(level=logging.INFO, event_level=logging.ERROR),
        ],
    )
    # One-time tags shared across the process
    try:
        sentry_sdk.set_tag("service", "a1-field-pro-backend")
    except Exception:
        pass
    return True
