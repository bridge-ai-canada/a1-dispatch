"""Route optimization for a technician's daily schedule.

We don't have a geocoding API in this environment, so we use a lightweight
proximity heuristic:
  1. Extract ZIP code from the address (5-digit pattern at the end).
  2. Group jobs by ZIP, ordered ascending so geographically-clustered jobs
     get neighbouring slots.
  3. Within a ZIP group, sort by street-number to keep close addresses adjacent.
The optimized order then re-spaces `scheduled_at` starting at the earliest job's
time, advancing by each job's `duration_min` + a configurable gap (default 30 min).
"""
import re
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from deps import db, now_iso, require_role, log_activity


router = APIRouter()

ZIP_RE = re.compile(r"(\d{5})(?:-\d{4})?\s*$")
STREET_NUM_RE = re.compile(r"^\s*(\d+)")


def _zip_of(addr: str) -> str:
    m = ZIP_RE.search(addr or "")
    return m.group(1) if m else "99999"  # missing zip = tail


def _street_num(addr: str) -> int:
    m = STREET_NUM_RE.match(addr or "")
    try:
        return int(m.group(1)) if m else 99999
    except Exception:
        return 99999


class OptimizeIn(BaseModel):
    technician_id: str
    date: str  # YYYY-MM-DD (UTC)
    gap_min: int = 30
    dry_run: bool = False


@router.post("/jobs/optimize-route")
async def optimize_route(body: OptimizeIn,
                         user: dict = Depends(require_role("owner", "dispatcher", "office_manager"))):
    # Pull jobs assigned to that tech on that date (UTC date prefix match)
    q = {
        "company_id": user["company_id"],
        "assigned_to": body.technician_id,
        "status": {"$in": ["scheduled_installation", "scheduled", "in_progress"]},
        "scheduled_at": {"$regex": f"^{body.date}"},
    }
    jobs = await db.jobs.find(q, {"_id": 0}).to_list(200)
    if not jobs:
        return {"ok": True, "reordered": 0, "jobs": []}

    # Sort by (zip, street_num); fallback to original time
    sorted_jobs = sorted(jobs, key=lambda j: (_zip_of(j.get("address", "")),
                                              _street_num(j.get("address", "")),
                                              j.get("scheduled_at") or ""))

    # Re-space scheduled_at starting from the earliest currently-scheduled time
    start_iso = min(j.get("scheduled_at") or "" for j in jobs)
    start = datetime.fromisoformat(start_iso) if start_iso else datetime.now(timezone.utc)
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)

    cursor_time = start
    plan = []
    for j in sorted_jobs:
        new_scheduled = cursor_time.isoformat()
        plan.append({
            "id": j["id"],
            "title": j.get("title"),
            "address": j.get("address"),
            "old_scheduled_at": j.get("scheduled_at"),
            "new_scheduled_at": new_scheduled,
            "duration_min": j.get("duration_min", 60),
        })
        cursor_time += timedelta(minutes=int(j.get("duration_min", 60)) + body.gap_min)

    if not body.dry_run:
        for p in plan:
            await db.jobs.update_one(
                {"id": p["id"], "company_id": user["company_id"]},
                {"$set": {"scheduled_at": p["new_scheduled_at"], "updated_at": now_iso()}},
            )
        await log_activity(user, "route.optimized", "user", body.technician_id,
                           {"date": body.date, "count": len(plan)})

    return {"ok": True, "reordered": len(plan), "jobs": plan, "dry_run": body.dry_run}
