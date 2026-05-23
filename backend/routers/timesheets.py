"""Time tracking: shift clock-in/out + per-job time logs."""
import uuid
from datetime import datetime, timezone
from typing import Optional, Literal
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from deps import db, now_iso, get_current_user, log_activity

router = APIRouter()


def _iso_to_dt(iso: Optional[str]) -> Optional[datetime]:
    if not iso:
        return None
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except Exception:
        return None


def _minutes_between(a: Optional[datetime], b: Optional[datetime]) -> int:
    if not a or not b:
        return 0
    return max(0, int((b - a).total_seconds() // 60))


class BreakIn(BaseModel):
    minutes: int = 0  # add break minutes for this shift


# -------------------- Shifts (full work-day) --------------------
@router.post("/timesheets/clock-in")
async def clock_in(user: dict = Depends(get_current_user)):
    # forbid double clock-in
    active = await db.shifts.find_one(
        {"user_id": user["id"], "ended_at": None}, {"_id": 0}
    )
    if active:
        return {"already_clocked_in": True, "shift": active}
    sid = str(uuid.uuid4())
    shift = {
        "id": sid,
        "company_id": user["company_id"],
        "user_id": user["id"],
        "started_at": now_iso(),
        "ended_at": None,
        "break_minutes": 0,
        "total_minutes": 0,
    }
    await db.shifts.insert_one(shift)
    await log_activity(user, "shift.started", "shift", sid, {})
    return {"started": True, "shift": {k: v for k, v in shift.items() if k != "_id"}}


@router.post("/timesheets/clock-out")
async def clock_out(user: dict = Depends(get_current_user)):
    active = await db.shifts.find_one(
        {"user_id": user["id"], "ended_at": None}, {"_id": 0}
    )
    if not active:
        raise HTTPException(status_code=400, detail="Not currently clocked in")
    ended = datetime.now(timezone.utc)
    started = _iso_to_dt(active.get("started_at"))
    total = _minutes_between(started, ended) - int(active.get("break_minutes", 0) or 0)
    total = max(0, total)
    await db.shifts.update_one(
        {"id": active["id"]},
        {"$set": {"ended_at": ended.isoformat(), "total_minutes": total}},
    )
    await log_activity(user, "shift.ended", "shift", active["id"], {"minutes": total})
    active["ended_at"] = ended.isoformat()
    active["total_minutes"] = total
    return active


@router.post("/timesheets/break")
async def add_break(body: BreakIn, user: dict = Depends(get_current_user)):
    active = await db.shifts.find_one(
        {"user_id": user["id"], "ended_at": None}, {"_id": 0}
    )
    if not active:
        raise HTTPException(status_code=400, detail="Not currently clocked in")
    new_break = int(active.get("break_minutes", 0) or 0) + max(0, int(body.minutes or 0))
    await db.shifts.update_one({"id": active["id"]}, {"$set": {"break_minutes": new_break}})
    return {"break_minutes": new_break}


@router.get("/timesheets/active")
async def get_active(user: dict = Depends(get_current_user)):
    active = await db.shifts.find_one(
        {"user_id": user["id"], "ended_at": None}, {"_id": 0}
    )
    return {"active": active}


@router.get("/timesheets")
async def list_my_shifts(user: dict = Depends(get_current_user), days: int = 14):
    cutoff = (datetime.now(timezone.utc) - __import__("datetime").timedelta(days=days)).isoformat()
    items = await db.shifts.find(
        {"user_id": user["id"], "started_at": {"$gte": cutoff}},
        {"_id": 0},
    ).sort("started_at", -1).to_list(200)
    return items


# -------------------- Per-job time logs --------------------
class JobStartIn(BaseModel):
    note: Optional[str] = ""


@router.post("/jobs/{job_id}/time/start")
async def job_time_start(job_id: str, user: dict = Depends(get_current_user)):
    job = await db.jobs.find_one({"id": job_id, "company_id": user["company_id"]}, {"_id": 0})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    logs = list(job.get("time_logs") or [])
    # close any active log first
    for li in logs:
        if li.get("user_id") == user["id"] and not li.get("ended_at"):
            raise HTTPException(status_code=400, detail="Already tracking time on this job")
    entry = {
        "id": str(uuid.uuid4()),
        "user_id": user["id"],
        "user_name": user.get("name") or user.get("email"),
        "started_at": now_iso(),
        "ended_at": None,
        "duration_min": 0,
    }
    logs.append(entry)
    await db.jobs.update_one({"id": job_id}, {"$set": {"time_logs": logs}})
    return entry


@router.post("/jobs/{job_id}/time/stop")
async def job_time_stop(job_id: str, user: dict = Depends(get_current_user)):
    job = await db.jobs.find_one({"id": job_id, "company_id": user["company_id"]}, {"_id": 0})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    logs = list(job.get("time_logs") or [])
    found = None
    for li in logs:
        if li.get("user_id") == user["id"] and not li.get("ended_at"):
            ended = datetime.now(timezone.utc)
            li["ended_at"] = ended.isoformat()
            li["duration_min"] = _minutes_between(_iso_to_dt(li.get("started_at")), ended)
            found = li
            break
    if not found:
        raise HTTPException(status_code=400, detail="No active timer on this job")
    await db.jobs.update_one({"id": job_id}, {"$set": {"time_logs": logs}})
    return found


@router.get("/jobs/{job_id}/time")
async def job_time_summary(job_id: str, user: dict = Depends(get_current_user)):
    job = await db.jobs.find_one({"id": job_id, "company_id": user["company_id"]}, {"_id": 0})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    logs = list(job.get("time_logs") or [])
    total = 0
    active = None
    for li in logs:
        if li.get("ended_at"):
            total += int(li.get("duration_min", 0) or 0)
        elif li.get("user_id") == user["id"]:
            # currently active for me — include live elapsed
            active = li
    return {"total_minutes": total, "logs": logs, "active_for_me": active}
