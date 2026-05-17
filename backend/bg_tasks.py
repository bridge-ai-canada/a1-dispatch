"""Background tasks for geocoding + dashboard widgets."""
import asyncio
import logging
from typing import Optional

from deps import db, now_iso
from geocode_service import geocode

logger = logging.getLogger("a1fieldpro.bg")


async def geocode_and_attach_to_job(job_id: str, company_id: str, address: str) -> None:
    if not address:
        return
    result = await geocode(address)
    if not result:
        return
    location = {"lat": result["lat"], "lng": result["lng"], "geocoded_at": now_iso(),
                "display_name": result.get("display_name", "")}
    await db.jobs.update_one(
        {"id": job_id, "company_id": company_id},
        {"$set": {"location": location}},
    )
    # Broadcast so the dispatch map updates live
    try:
        from ws_hub import hub
        await hub.broadcast(company_id, "job.geocoded", {"job_id": job_id, "location": location})
    except Exception:
        pass


def schedule_geocode(job_id: str, company_id: str, address: str) -> None:
    """Fire-and-forget — never awaited. Used inline from create/update handlers."""
    if not address:
        return
    try:
        asyncio.create_task(geocode_and_attach_to_job(job_id, company_id, address))
    except RuntimeError:
        pass
