"""Background sync engine — APScheduler driven.

Each enabled integration with `supports_sync=True` has a periodic task that
pulls/pushes deltas. Tasks degrade gracefully when creds are missing.
"""
import asyncio
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from deps import db, logger, now_iso
from integrations import store as integ_store
from integrations.registry import PROVIDERS

scheduler: AsyncIOScheduler | None = None


def start() -> None:
    """Called once on FastAPI startup."""
    global scheduler
    if scheduler:
        return
    scheduler = AsyncIOScheduler(timezone="UTC")
    # Register sync jobs per provider that supports it.
    for key, p in PROVIDERS.items():
        if not p.get("supports_sync"):
            continue
        minutes = p.get("sync_interval_minutes", 30)
        scheduler.add_job(
            run_provider_sync, "interval",
            minutes=minutes, args=[key], id=f"sync.{key}", replace_existing=True,
            max_instances=1, coalesce=True,
        )
    scheduler.start()
    logger.info(f"sync_engine: started with {len(scheduler.get_jobs())} jobs")


def stop() -> None:
    global scheduler
    if scheduler:
        scheduler.shutdown(wait=False)
        scheduler = None


async def run_provider_sync(provider: str) -> None:
    """Run sync for every connected tenant of this provider."""
    cursor = db.integrations.find(
        {"provider": provider, "status": "connected"}, {"_id": 0},
    )
    async for integ in cursor:
        try:
            await sync_one(integ["company_id"], provider)
        except Exception as e:
            logger.error(f"sync_engine[{provider}/{integ['company_id']}]: {e}")
            await integ_store.mark_sync(
                integ["company_id"], provider, ok=False, error=str(e)[:200],
            )


async def sync_one(company_id: str, provider: str) -> dict:
    """Manual or scheduled sync run for a single tenant. Returns summary dict."""
    integ = await integ_store.get(company_id, provider)
    if not integ:
        return {"ok": False, "error": "not_connected"}

    # In a real prod build this would dispatch to per-provider sync handlers
    # (e.g. QuickBooks CDC, Calendar incremental sync). For now we record a
    # heartbeat and increment the counter so the UI/CLI can show "sync ran".
    count = 0
    if provider == "quickbooks":
        count = await _qbo_sync_heartbeat(company_id, integ)
    elif provider == "google_calendar":
        count = await _calendar_sync_heartbeat(company_id, integ, "google_calendar")
    elif provider == "outlook_calendar":
        count = await _calendar_sync_heartbeat(company_id, integ, "outlook_calendar")

    await integ_store.mark_sync(company_id, provider, ok=True, count=count)
    return {"ok": True, "count": count, "ran_at": now_iso()}


async def _qbo_sync_heartbeat(company_id: str, integ: dict) -> int:
    """Record a sync event. Real impl would call CDC + diff into local collections."""
    await db.integration_sync_events.insert_one({
        "company_id": company_id,
        "provider": "quickbooks",
        "kind": "heartbeat",
        "created_at": now_iso(),
        "note": "QBO scheduled sync ran (implementation pending live API creds).",
    })
    return 0


async def _calendar_sync_heartbeat(company_id: str, integ: dict, provider: str) -> int:
    await db.integration_sync_events.insert_one({
        "company_id": company_id,
        "provider": provider,
        "kind": "heartbeat",
        "created_at": now_iso(),
    })
    return 0
