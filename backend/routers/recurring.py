"""Recurring jobs / maintenance plans.

A `recurring_jobs` doc holds the template + cadence + `next_run_at`. On any
list call (and on a manual /run) we materialize all due ones into real jobs.
"""
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, Literal
from fastapi import APIRouter, HTTPException, Depends

from deps import (
    db, now_iso,
    get_current_user, require_role, log_activity,
    RecurringJobIn, RecurringJobUpdate, _CADENCE_DAYS,
)

router = APIRouter()


def _interval_days(cadence: str, interval_days: Optional[int]) -> int:
    if cadence == "custom":
        if not interval_days or interval_days < 1:
            raise HTTPException(status_code=400, detail="custom cadence requires interval_days >= 1")
        return int(interval_days)
    return _CADENCE_DAYS[cadence]


def _next_run(prev_iso: Optional[str], days: int) -> str:
    prev = datetime.fromisoformat(prev_iso) if prev_iso else datetime.now(timezone.utc)
    if prev.tzinfo is None:
        prev = prev.replace(tzinfo=timezone.utc)
    return (prev + timedelta(days=days)).isoformat()


async def _materialize_due(company_id: str) -> int:
    """Find every due active recurring_job for the company and create a job for each.
    Returns count materialized. Updates next_run_at on the template.
    """
    now = datetime.now(timezone.utc).isoformat()
    cursor = db.recurring_jobs.find(
        {"company_id": company_id, "active": True, "next_run_at": {"$lte": now}},
        {"_id": 0},
    )
    count = 0
    async for rj in cursor:
        days = _interval_days(rj["cadence"], rj.get("interval_days"))
        scheduled_at = rj["next_run_at"]
        job_doc = {
            "id": str(uuid.uuid4()),
            "company_id": company_id,
            "created_by": rj.get("created_by", "system"),
            "created_at": now_iso(),
            "paid": False,
            "title": rj["title"],
            "description": rj.get("description", ""),
            "customer_id": rj.get("customer_id"),
            "customer_name": rj.get("customer_name", ""),
            "customer_phone": rj.get("customer_phone", ""),
            "customer_email": rj.get("customer_email", ""),
            "address": rj.get("address", ""),
            "job_type": rj.get("job_type", "HVAC"),
            "assigned_to": rj.get("assigned_to"),
            "scheduled_at": scheduled_at,
            "duration_min": rj.get("duration_min", 60),
            "price": rj.get("price", 0.0),
            "status": "scheduled",
            "source": "recurring",
            "recurring_id": rj["id"],
        }
        await db.jobs.insert_one(job_doc)
        await db.recurring_jobs.update_one(
            {"id": rj["id"]},
            {"$set": {
                "last_run_at": now_iso(),
                "next_run_at": _next_run(scheduled_at, days),
            }},
        )
        count += 1
    return count


@router.get("/recurring-jobs")
async def list_recurring(user: dict = Depends(get_current_user)):
    # Materialize lazily so list view always reflects fresh state
    await _materialize_due(user["company_id"])
    items = await db.recurring_jobs.find(
        {"company_id": user["company_id"]}, {"_id": 0}
    ).sort("created_at", -1).to_list(200)
    return items


@router.post("/recurring-jobs")
async def create_recurring(body: RecurringJobIn, user: dict = Depends(get_current_user)):
    days = _interval_days(body.cadence, body.interval_days)
    start = body.start_at or now_iso()
    doc = {
        "id": str(uuid.uuid4()),
        "company_id": user["company_id"],
        "created_by": user["id"],
        "created_at": now_iso(),
        "next_run_at": start,
        "last_run_at": None,
        **body.model_dump(),
    }
    # Normalize: ensure interval_days is set for non-custom too
    if body.cadence != "custom":
        doc["interval_days"] = days
    await db.recurring_jobs.insert_one(doc)
    doc.pop("_id", None)
    await log_activity(user, "recurring.created", "recurring_job", doc["id"],
                       {"title": body.title, "cadence": body.cadence, "interval_days": days})
    return doc


@router.patch("/recurring-jobs/{rid}")
async def update_recurring(rid: str, body: RecurringJobUpdate,
                           user: dict = Depends(get_current_user)):
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    if "cadence" in updates or "interval_days" in updates:
        existing = await db.recurring_jobs.find_one(
            {"id": rid, "company_id": user["company_id"]}, {"_id": 0}
        )
        if not existing:
            raise HTTPException(status_code=404, detail="Not found")
        cadence = updates.get("cadence", existing["cadence"])
        interval = updates.get("interval_days", existing.get("interval_days"))
        updates["interval_days"] = _interval_days(cadence, interval)
    updates["updated_at"] = now_iso()
    result = await db.recurring_jobs.update_one(
        {"id": rid, "company_id": user["company_id"]}, {"$set": updates}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Not found")
    return await db.recurring_jobs.find_one({"id": rid}, {"_id": 0})


@router.delete("/recurring-jobs/{rid}")
async def delete_recurring(rid: str, user: dict = Depends(require_role("owner", "dispatcher"))):
    result = await db.recurring_jobs.delete_one(
        {"id": rid, "company_id": user["company_id"]}
    )
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Not found")
    await log_activity(user, "recurring.deleted", "recurring_job", rid)
    return {"ok": True}


@router.post("/recurring-jobs/{rid}/run")
async def run_recurring(rid: str, user: dict = Depends(get_current_user)):
    """Force-materialize the next occurrence regardless of next_run_at."""
    rj = await db.recurring_jobs.find_one(
        {"id": rid, "company_id": user["company_id"]}, {"_id": 0}
    )
    if not rj:
        raise HTTPException(status_code=404, detail="Not found")
    days = _interval_days(rj["cadence"], rj.get("interval_days"))
    scheduled_at = now_iso()
    job_doc = {
        "id": str(uuid.uuid4()),
        "company_id": user["company_id"],
        "created_by": user["id"],
        "created_at": now_iso(),
        "paid": False,
        "title": rj["title"],
        "description": rj.get("description", ""),
        "customer_id": rj.get("customer_id"),
        "customer_name": rj.get("customer_name", ""),
        "customer_phone": rj.get("customer_phone", ""),
        "customer_email": rj.get("customer_email", ""),
        "address": rj.get("address", ""),
        "job_type": rj.get("job_type", "HVAC"),
        "assigned_to": rj.get("assigned_to"),
        "scheduled_at": scheduled_at,
        "duration_min": rj.get("duration_min", 60),
        "price": rj.get("price", 0.0),
        "status": "scheduled",
        "source": "recurring",
        "recurring_id": rj["id"],
    }
    await db.jobs.insert_one(job_doc)
    await db.recurring_jobs.update_one(
        {"id": rid},
        {"$set": {
            "last_run_at": now_iso(),
            "next_run_at": _next_run(scheduled_at, days),
        }},
    )
    job_doc.pop("_id", None)
    await log_activity(user, "recurring.materialized", "recurring_job", rid,
                       {"job_id": job_doc["id"]})
    return job_doc
