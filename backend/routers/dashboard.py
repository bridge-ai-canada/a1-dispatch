"""Dashboard analytics widgets + per-user notification preferences."""
from datetime import datetime, timezone, timedelta
from typing import Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from deps import db, now_iso, get_current_user

router = APIRouter()


# ---------- Tech leaderboard ----------
@router.get("/dashboard/leaderboard")
async def tech_leaderboard(user: dict = Depends(get_current_user), days: int = 30):
    """Top techs by 30d rating average + tip total."""
    since_iso = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    pipeline = [
        {"$match": {
            "company_id": user["company_id"],
            "status": "completed",
            "assigned_to": {"$ne": None},
            "rated_at": {"$gte": since_iso},
        }},
        {"$group": {
            "_id": "$assigned_to",
            "ratings_count": {"$sum": 1},
            "rating_sum": {"$sum": {"$ifNull": ["$rating", 0]}},
            "tip_total": {"$sum": {"$ifNull": ["$tip", 0]}},
            "revenue": {"$sum": {"$ifNull": ["$price", 0]}},
        }},
        {"$sort": {"rating_sum": -1}},
        {"$limit": 25},
    ]
    rows = await db.jobs.aggregate(pipeline).to_list(25)
    # Fetch tech names
    tech_ids = [r["_id"] for r in rows]
    techs = await db.users.find(
        {"id": {"$in": tech_ids}}, {"id": 1, "name": 1}
    ).to_list(50)
    name_by_id = {t["id"]: t["name"] for t in techs}
    out = []
    for r in rows:
        avg = (r["rating_sum"] / r["ratings_count"]) if r["ratings_count"] else 0
        out.append({
            "tech_id": r["_id"],
            "name": name_by_id.get(r["_id"], "—"),
            "ratings_count": r["ratings_count"],
            "rating_avg": round(avg, 2),
            "tip_total": round(r["tip_total"], 2),
            "revenue": round(r["revenue"], 2),
        })
    out.sort(key=lambda x: (-x["rating_avg"], -x["tip_total"]))
    return out


# ---------- Recurring revenue forecast ----------
@router.get("/dashboard/recurring-forecast")
async def recurring_forecast(user: dict = Depends(get_current_user), days: int = 30):
    """Forecast revenue from active recurring plans over the next `days`."""
    horizon = datetime.now(timezone.utc) + timedelta(days=days)
    plans = await db.recurring_jobs.find(
        {"company_id": user["company_id"], "active": True}, {"_id": 0}
    ).to_list(500)

    total_expected = 0.0
    upcoming = []
    for p in plans:
        interval = int(p.get("interval_days") or 30)
        price = float(p.get("price") or 0)
        next_at = p.get("next_run_at")
        if not next_at:
            continue
        try:
            cur = datetime.fromisoformat(next_at)
            if cur.tzinfo is None:
                cur = cur.replace(tzinfo=timezone.utc)
        except Exception:
            continue
        occurrences = 0
        # Count occurrences within horizon
        while cur <= horizon:
            occurrences += 1
            cur = cur + timedelta(days=interval)
            if occurrences > 60:  # safety
                break
        if occurrences:
            total_expected += occurrences * price
            upcoming.append({
                "id": p["id"],
                "title": p["title"],
                "customer_name": p.get("customer_name", ""),
                "cadence": p["cadence"],
                "interval_days": interval,
                "price": price,
                "occurrences": occurrences,
                "expected_revenue": round(occurrences * price, 2),
                "next_run_at": next_at,
            })

    upcoming.sort(key=lambda x: -x["expected_revenue"])

    # Active contract value = sum of all active plans' annual run-rate
    annual = sum((365 / int(p.get("interval_days") or 30)) * float(p.get("price") or 0)
                 for p in plans if p.get("active"))
    return {
        "horizon_days": days,
        "total_expected": round(total_expected, 2),
        "active_plans": len(plans),
        "annual_contract_value": round(annual, 2),
        "plans": upcoming[:20],
    }


# ---------- Notification preferences ----------
class PushPrefs(BaseModel):
    job_assigned: bool = True
    job_rescheduled: bool = True
    payment_received: bool = True
    tip_received: bool = True
    rating_created: bool = True
    rating_low_alert: bool = True
    recurring_materialized: bool = True
    quiet_hours_start: Optional[int] = None  # 0..23 local hour
    quiet_hours_end: Optional[int] = None


PREF_BY_TAG_PREFIX = {
    "job": ("job_assigned", "job_rescheduled"),
    "pay": ("payment_received",),
    "tip": ("tip_received",),
    "rate": ("rating_created",),
    "low-rate": ("rating_low_alert",),
}


@router.get("/me/push-prefs")
async def get_push_prefs(user: dict = Depends(get_current_user)):
    u = await db.users.find_one({"id": user["id"]}, {"push_prefs": 1, "_id": 0})
    prefs = (u or {}).get("push_prefs") or {}
    return {**PushPrefs().model_dump(), **prefs}


@router.put("/me/push-prefs")
async def set_push_prefs(body: PushPrefs, user: dict = Depends(get_current_user)):
    await db.users.update_one(
        {"id": user["id"]},
        {"$set": {"push_prefs": body.model_dump(), "push_prefs_at": now_iso()}},
    )
    return {"ok": True, "prefs": body.model_dump()}
