"""Advanced analytics — executive-level KPI dashboards.

All endpoints respect tenant isolation via company_id and accept a date range
(start/end ISO strings). Sub-endpoints return both raw rows for tables and
time-bucketed series for charts (daily by default; weekly/monthly options).
"""
import csv
import io
from datetime import datetime, timezone, timedelta
from typing import Optional, Literal
from fastapi import APIRouter, Depends, Response, Query

from deps import db, get_current_user

router = APIRouter()


# -------------------- Date helpers --------------------
def _parse_range(start: Optional[str], end: Optional[str], default_days: int = 30):
    """Return (start_dt_utc, end_dt_utc) iso strings; defaults to last N days."""
    if end:
        end_dt = datetime.fromisoformat(end.replace("Z", "+00:00"))
    else:
        end_dt = datetime.now(timezone.utc)
    if start:
        start_dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
    else:
        start_dt = end_dt - timedelta(days=default_days)
    return start_dt, end_dt


def _bucket_format(granularity: str) -> dict:
    """Return $dateToString format for daily/weekly/monthly bucketing."""
    if granularity == "month":
        return {"format": "%Y-%m", "date": {"$dateFromString": {"dateString": "$created_at"}}}
    if granularity == "week":
        return {"format": "%G-W%V", "date": {"$dateFromString": {"dateString": "$created_at"}}}
    return {"format": "%Y-%m-%d", "date": {"$dateFromString": {"dateString": "$created_at"}}}


def _branch_match(branch_id: Optional[str], company_id: str) -> dict:
    q = {"company_id": company_id}
    if branch_id:
        q["branch_id"] = branch_id
    return q


# -------------------- Overview KPIs --------------------
@router.get("/analytics/overview")
async def overview(
    user: dict = Depends(get_current_user),
    start: Optional[str] = None,
    end: Optional[str] = None,
    branch_id: Optional[str] = None,
):
    start_dt, end_dt = _parse_range(start, end)
    match = _branch_match(branch_id, user["company_id"])
    s, e = start_dt.isoformat(), end_dt.isoformat()

    # Revenue (paid jobs in window)
    rev_agg = await db.jobs.aggregate([
        {"$match": {**match, "paid": True, "created_at": {"$gte": s, "$lte": e}}},
        {"$group": {"_id": None, "rev": {"$sum": "$price"}, "cnt": {"$sum": 1}}},
    ]).to_list(1)
    revenue = (rev_agg[0]["rev"] if rev_agg else 0) or 0
    jobs_paid = (rev_agg[0]["cnt"] if rev_agg else 0) or 0

    jobs_total = await db.jobs.count_documents({**match, "created_at": {"$gte": s, "$lte": e}})
    jobs_completed = await db.jobs.count_documents({
        **match, "status": "completed", "created_at": {"$gte": s, "$lte": e},
    })

    # Active customers (any job in window)
    customers_active = len(await db.jobs.distinct("customer_id", {
        **match, "created_at": {"$gte": s, "$lte": e}, "customer_id": {"$ne": None},
    }))

    # Avg ticket
    avg_ticket = round(revenue / jobs_paid, 2) if jobs_paid else 0.0

    # Compare to previous equal window
    prev_start = start_dt - (end_dt - start_dt)
    prev_end = start_dt
    prev_rev_agg = await db.jobs.aggregate([
        {"$match": {**match, "paid": True, "created_at": {"$gte": prev_start.isoformat(), "$lt": prev_end.isoformat()}}},
        {"$group": {"_id": None, "rev": {"$sum": "$price"}}},
    ]).to_list(1)
    prev_revenue = (prev_rev_agg[0]["rev"] if prev_rev_agg else 0) or 0
    rev_delta_pct = round(((revenue - prev_revenue) / prev_revenue * 100), 1) if prev_revenue else None

    # Financing volume
    fin_agg = await db.finance_applications.aggregate([
        {"$match": {**match, "status": "funded", "created_at": {"$gte": s, "$lte": e}}},
        {"$group": {"_id": None, "amount": {"$sum": "$amount"}, "cnt": {"$sum": 1}}},
    ]).to_list(1)
    finance_funded = (fin_agg[0]["amount"] if fin_agg else 0) or 0
    finance_funded_count = (fin_agg[0]["cnt"] if fin_agg else 0) or 0

    return {
        "window": {"start": s, "end": e},
        "revenue": revenue,
        "revenue_delta_pct": rev_delta_pct,
        "jobs_total": jobs_total,
        "jobs_completed": jobs_completed,
        "jobs_paid": jobs_paid,
        "avg_ticket": avg_ticket,
        "customers_active": customers_active,
        "finance_funded": finance_funded,
        "finance_funded_count": finance_funded_count,
    }


# -------------------- Revenue tracking --------------------
@router.get("/analytics/revenue")
async def revenue_series(
    user: dict = Depends(get_current_user),
    start: Optional[str] = None,
    end: Optional[str] = None,
    branch_id: Optional[str] = None,
    granularity: Literal["day", "week", "month"] = "day",
):
    start_dt, end_dt = _parse_range(start, end, default_days=60)
    match = _branch_match(branch_id, user["company_id"])
    bucket = _bucket_format(granularity)
    rows = await db.jobs.aggregate([
        {"$match": {**match, "paid": True,
                    "created_at": {"$gte": start_dt.isoformat(), "$lte": end_dt.isoformat()}}},
        {"$group": {
            "_id": {"$dateToString": bucket},
            "revenue": {"$sum": "$price"},
            "jobs": {"$sum": 1},
        }},
        {"$sort": {"_id": 1}},
    ]).to_list(500)
    return {
        "granularity": granularity,
        "series": [{"bucket": r["_id"], "revenue": round(r["revenue"], 2), "jobs": r["jobs"]} for r in rows if r["_id"]],
    }


# -------------------- Technician performance --------------------
@router.get("/analytics/technicians")
async def technician_performance(
    user: dict = Depends(get_current_user),
    start: Optional[str] = None,
    end: Optional[str] = None,
    branch_id: Optional[str] = None,
):
    start_dt, end_dt = _parse_range(start, end)
    match = _branch_match(branch_id, user["company_id"])
    s, e = start_dt.isoformat(), end_dt.isoformat()
    rows = await db.jobs.aggregate([
        {"$match": {**match, "assigned_to": {"$ne": None}, "created_at": {"$gte": s, "$lte": e}}},
        {"$group": {
            "_id": "$assigned_to",
            "jobs_total": {"$sum": 1},
            "jobs_completed": {"$sum": {"$cond": [{"$eq": ["$status", "completed"]}, 1, 0]}},
            "revenue": {"$sum": {"$cond": ["$paid", "$price", 0]}},
            "rating_sum": {"$sum": {"$ifNull": ["$rating", 0]}},
            "rating_count": {"$sum": {"$cond": [{"$ne": ["$rating", None]}, 1, 0]}},
            "tips": {"$sum": {"$ifNull": ["$tip", 0]}},
        }},
        {"$sort": {"revenue": -1}},
    ]).to_list(200)

    ids = [r["_id"] for r in rows]
    users = await db.users.find({"id": {"$in": ids}}, {"_id": 0, "id": 1, "name": 1, "role": 1}).to_list(500)
    by_id = {u["id"]: u for u in users}
    out = []
    for r in rows:
        u = by_id.get(r["_id"]) or {}
        out.append({
            "tech_id": r["_id"],
            "name": u.get("name", "Unknown"),
            "role": u.get("role"),
            "jobs_total": r["jobs_total"],
            "jobs_completed": r["jobs_completed"],
            "revenue": round(r["revenue"] or 0, 2),
            "avg_rating": round(r["rating_sum"] / r["rating_count"], 2) if r["rating_count"] else None,
            "rating_count": r["rating_count"],
            "tips": round(r["tips"] or 0, 2),
            "completion_rate": round(r["jobs_completed"] / r["jobs_total"] * 100, 1) if r["jobs_total"] else 0,
        })
    return {"techs": out}


# -------------------- Marketing ROI --------------------
@router.get("/analytics/marketing")
async def marketing_roi(
    user: dict = Depends(get_current_user),
    start: Optional[str] = None,
    end: Optional[str] = None,
    branch_id: Optional[str] = None,
):
    """Jobs grouped by source — leads, won jobs, revenue, conversion rate."""
    start_dt, end_dt = _parse_range(start, end)
    match = _branch_match(branch_id, user["company_id"])
    s, e = start_dt.isoformat(), end_dt.isoformat()
    rows = await db.jobs.aggregate([
        {"$match": {**match, "created_at": {"$gte": s, "$lte": e}}},
        {"$group": {
            "_id": {"$ifNull": ["$source", "direct"]},
            "leads": {"$sum": 1},
            "won": {"$sum": {"$cond": [{"$in": ["$status", ["completed", "in_progress", "scheduled_installation", "won_bid"]]}, 1, 0]}},
            "revenue": {"$sum": {"$cond": ["$paid", "$price", 0]}},
        }},
        {"$sort": {"revenue": -1}},
    ]).to_list(50)

    # Optional cost lookup per source from marketing_costs collection
    costs = {}
    async for c in db.marketing_costs.find(
        {**match, "period_start": {"$lte": e}, "period_end": {"$gte": s}}, {"_id": 0},
    ):
        costs[c.get("source")] = (costs.get(c.get("source")) or 0) + (c.get("cost") or 0)

    out = []
    for r in rows:
        src = r["_id"] or "direct"
        leads = r["leads"]
        won = r["won"]
        rev = round(r["revenue"] or 0, 2)
        cost = costs.get(src, 0)
        roi = round(((rev - cost) / cost * 100), 1) if cost else None
        cpl = round(cost / leads, 2) if cost and leads else None
        out.append({
            "source": src, "leads": leads, "won": won, "revenue": rev,
            "conversion_rate": round(won / leads * 100, 1) if leads else 0,
            "cost": cost, "roi_pct": roi, "cost_per_lead": cpl,
        })
    return {"sources": out}


# -------------------- Call conversion --------------------
@router.get("/analytics/calls")
async def call_conversion(
    user: dict = Depends(get_current_user),
    start: Optional[str] = None,
    end: Optional[str] = None,
    branch_id: Optional[str] = None,
):
    """How many inbound calls/leads actually became booked jobs."""
    start_dt, end_dt = _parse_range(start, end)
    match = _branch_match(branch_id, user["company_id"])
    s, e = start_dt.isoformat(), end_dt.isoformat()
    # communications collection logs inbound calls when present
    calls_total = await db.communications.count_documents({
        **match, "kind": "call", "direction": "inbound",
        "created_at": {"$gte": s, "$lte": e},
    })
    # Fallback to jobs.source=call when communications log isn't used
    if calls_total == 0:
        calls_total = await db.jobs.count_documents({
            **match, "source": "call", "created_at": {"$gte": s, "$lte": e},
        })
    booked = await db.jobs.count_documents({
        **match, "source": "call",
        "status": {"$in": ["scheduled_installation", "in_progress", "completed", "won_bid"]},
        "created_at": {"$gte": s, "$lte": e},
    })
    completed = await db.jobs.count_documents({
        **match, "source": "call", "status": "completed",
        "created_at": {"$gte": s, "$lte": e},
    })
    revenue_agg = await db.jobs.aggregate([
        {"$match": {**match, "source": "call", "paid": True,
                    "created_at": {"$gte": s, "$lte": e}}},
        {"$group": {"_id": None, "rev": {"$sum": "$price"}}},
    ]).to_list(1)
    revenue = (revenue_agg[0]["rev"] if revenue_agg else 0) or 0
    return {
        "calls_total": calls_total,
        "booked": booked,
        "completed": completed,
        "revenue": round(revenue, 2),
        "book_rate_pct": round(booked / calls_total * 100, 1) if calls_total else 0,
        "close_rate_pct": round(completed / calls_total * 100, 1) if calls_total else 0,
        "avg_ticket": round(revenue / completed, 2) if completed else 0,
    }


# -------------------- Financing conversion --------------------
@router.get("/analytics/financing-conversion")
async def financing_conversion(
    user: dict = Depends(get_current_user),
    start: Optional[str] = None,
    end: Optional[str] = None,
    branch_id: Optional[str] = None,
):
    start_dt, end_dt = _parse_range(start, end)
    match = _branch_match(branch_id, user["company_id"])
    s, e = start_dt.isoformat(), end_dt.isoformat()
    by_status = await db.finance_applications.aggregate([
        {"$match": {**match, "created_at": {"$gte": s, "$lte": e}}},
        {"$group": {"_id": "$status", "count": {"$sum": 1}, "amount": {"$sum": "$amount"}}},
    ]).to_list(50)
    statuses = {r["_id"] or "started": {"count": r["count"], "amount": round(r["amount"] or 0, 2)} for r in by_status}
    started = sum(v["count"] for v in statuses.values())
    decisioned = sum(statuses.get(k, {}).get("count", 0) for k in ("decisioned", "signed", "funded", "manual_review"))
    signed = sum(statuses.get(k, {}).get("count", 0) for k in ("signed", "funded"))
    funded = statuses.get("funded", {}).get("count", 0)
    funded_amount = statuses.get("funded", {}).get("amount", 0)
    return {
        "funnel": [
            {"step": "started", "count": started},
            {"step": "decisioned", "count": decisioned},
            {"step": "signed", "count": signed},
            {"step": "funded", "count": funded},
        ],
        "approval_rate_pct": round((started - statuses.get("declined", {}).get("count", 0)) / started * 100, 1) if started else 0,
        "sign_rate_pct": round(signed / decisioned * 100, 1) if decisioned else 0,
        "fund_rate_pct": round(funded / signed * 100, 1) if signed else 0,
        "funded_amount": funded_amount,
        "by_status": statuses,
    }


# -------------------- Membership retention --------------------
@router.get("/analytics/memberships")
async def membership_retention(user: dict = Depends(get_current_user)):
    """Membership churn + retention metrics. Uses `memberships` collection if present."""
    company_id = user["company_id"]
    active = await db.memberships.count_documents({"company_id": company_id, "status": "active"})
    paused = await db.memberships.count_documents({"company_id": company_id, "status": "paused"})
    cancelled = await db.memberships.count_documents({"company_id": company_id, "status": "cancelled"})
    total = active + paused + cancelled

    # MRR from active memberships
    mrr_agg = await db.memberships.aggregate([
        {"$match": {"company_id": company_id, "status": "active"}},
        {"$group": {"_id": None, "mrr": {"$sum": "$monthly_fee"}}},
    ]).to_list(1)
    mrr = (mrr_agg[0]["mrr"] if mrr_agg else 0) or 0

    # New / churned in last 30 days
    thirty = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    new_30 = await db.memberships.count_documents({
        "company_id": company_id, "created_at": {"$gte": thirty},
    })
    churned_30 = await db.memberships.count_documents({
        "company_id": company_id, "status": "cancelled", "cancelled_at": {"$gte": thirty},
    })
    churn_rate = round(churned_30 / active * 100, 1) if active else 0

    return {
        "active": active, "paused": paused, "cancelled": cancelled, "total": total,
        "mrr": round(mrr, 2),
        "new_30d": new_30, "churned_30d": churned_30,
        "churn_rate_pct": churn_rate,
        "retention_pct": round(100 - churn_rate, 1),
    }


# -------------------- Sales leaderboard --------------------
@router.get("/analytics/leaderboard")
async def sales_leaderboard(
    user: dict = Depends(get_current_user),
    start: Optional[str] = None,
    end: Optional[str] = None,
    branch_id: Optional[str] = None,
    metric: Literal["revenue", "jobs", "rating"] = "revenue",
):
    start_dt, end_dt = _parse_range(start, end)
    match = _branch_match(branch_id, user["company_id"])
    s, e = start_dt.isoformat(), end_dt.isoformat()
    rows = await db.jobs.aggregate([
        {"$match": {**match, "created_at": {"$gte": s, "$lte": e},
                    "assigned_to": {"$ne": None}}},
        {"$group": {
            "_id": "$assigned_to",
            "revenue": {"$sum": {"$cond": ["$paid", "$price", 0]}},
            "jobs": {"$sum": 1},
            "wins": {"$sum": {"$cond": [{"$eq": ["$status", "completed"]}, 1, 0]}},
            "rating_sum": {"$sum": {"$ifNull": ["$rating", 0]}},
            "rating_count": {"$sum": {"$cond": [{"$ne": ["$rating", None]}, 1, 0]}},
        }},
    ]).to_list(200)
    ids = [r["_id"] for r in rows]
    users_ = await db.users.find({"id": {"$in": ids}}, {"_id": 0, "id": 1, "name": 1, "role": 1}).to_list(500)
    by_id = {u["id"]: u for u in users_}
    enriched = []
    for r in rows:
        u = by_id.get(r["_id"]) or {}
        enriched.append({
            "user_id": r["_id"],
            "name": u.get("name", "Unknown"),
            "role": u.get("role"),
            "revenue": round(r["revenue"] or 0, 2),
            "jobs": r["jobs"],
            "wins": r["wins"],
            "win_rate_pct": round(r["wins"] / r["jobs"] * 100, 1) if r["jobs"] else 0,
            "avg_rating": round(r["rating_sum"] / r["rating_count"], 2) if r["rating_count"] else None,
        })
    sort_key = {"revenue": "revenue", "jobs": "wins", "rating": "avg_rating"}[metric]
    enriched.sort(key=lambda x: (x[sort_key] is None, -(x[sort_key] or 0)))
    return {"leaderboard": enriched[:25], "metric": metric}


# -------------------- Real-time ticker --------------------
@router.get("/analytics/realtime")
async def realtime_ticker(user: dict = Depends(get_current_user), branch_id: Optional[str] = None):
    """Today-so-far tile. Light query — safe to poll every 30s."""
    match = _branch_match(branch_id, user["company_id"])
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    jobs_in_progress = await db.jobs.count_documents({**match, "status": "in_progress"})
    jobs_completed_today = await db.jobs.count_documents({
        **match, "status": "completed", "updated_at": {"$gte": today},
    })
    rev_agg = await db.jobs.aggregate([
        {"$match": {**match, "paid": True, "updated_at": {"$gte": today}}},
        {"$group": {"_id": None, "rev": {"$sum": "$price"}}},
    ]).to_list(1)
    revenue_today = (rev_agg[0]["rev"] if rev_agg else 0) or 0
    new_apps_today = await db.finance_applications.count_documents({
        **match, "created_at": {"$gte": today},
    })
    funded_today = await db.finance_applications.count_documents({
        **match, "status": "funded", "funded_at": {"$gte": today},
    })
    return {
        "as_of": datetime.now(timezone.utc).isoformat(),
        "jobs_in_progress": jobs_in_progress,
        "jobs_completed_today": jobs_completed_today,
        "revenue_today": round(revenue_today, 2),
        "new_finance_apps_today": new_apps_today,
        "funded_today": funded_today,
    }


# -------------------- CSV export --------------------
@router.get("/analytics/export.csv")
async def export_csv(
    user: dict = Depends(get_current_user),
    report: Literal["revenue", "technicians", "marketing", "financing", "leaderboard"] = "revenue",
    start: Optional[str] = None,
    end: Optional[str] = None,
    branch_id: Optional[str] = None,
):
    """Single CSV export endpoint — switches on `report`."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    fname = f"{report}-{(start or '')[:10]}-to-{(end or '')[:10]}.csv"

    if report == "revenue":
        data = await revenue_series(user=user, start=start, end=end, branch_id=branch_id, granularity="day")
        writer.writerow(["bucket", "revenue", "jobs"])
        for r in data["series"]:
            writer.writerow([r["bucket"], r["revenue"], r["jobs"]])
    elif report == "technicians":
        data = await technician_performance(user=user, start=start, end=end, branch_id=branch_id)
        writer.writerow(["name", "role", "jobs_total", "jobs_completed", "revenue", "avg_rating", "tips", "completion_rate_pct"])
        for r in data["techs"]:
            writer.writerow([r["name"], r["role"] or "", r["jobs_total"], r["jobs_completed"], r["revenue"], r["avg_rating"] or "", r["tips"], r["completion_rate"]])
    elif report == "marketing":
        data = await marketing_roi(user=user, start=start, end=end, branch_id=branch_id)
        writer.writerow(["source", "leads", "won", "revenue", "conversion_rate_pct", "cost", "roi_pct", "cost_per_lead"])
        for r in data["sources"]:
            writer.writerow([r["source"], r["leads"], r["won"], r["revenue"], r["conversion_rate"], r["cost"] or "", r["roi_pct"] or "", r["cost_per_lead"] or ""])
    elif report == "financing":
        data = await financing_conversion(user=user, start=start, end=end, branch_id=branch_id)
        writer.writerow(["status", "count", "amount"])
        for k, v in data["by_status"].items():
            writer.writerow([k, v["count"], v["amount"]])
    elif report == "leaderboard":
        data = await sales_leaderboard(user=user, start=start, end=end, branch_id=branch_id)
        writer.writerow(["rank", "name", "role", "revenue", "jobs", "wins", "win_rate_pct", "avg_rating"])
        for i, r in enumerate(data["leaderboard"], 1):
            writer.writerow([i, r["name"], r["role"] or "", r["revenue"], r["jobs"], r["wins"], r["win_rate_pct"], r["avg_rating"] or ""])

    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


# -------------------- Marketing cost input (admin) --------------------
@router.post("/analytics/marketing-costs")
async def upsert_marketing_cost(
    payload: dict,
    user: dict = Depends(get_current_user),
):
    """Owner / office_manager can record marketing spend per source for ROI calc."""
    if user.get("role") not in ("owner", "office_manager", "accountant", "super_admin"):
        return Response(status_code=403, content="Forbidden")
    doc = {
        "company_id": user["company_id"],
        "source": payload.get("source"),
        "cost": float(payload.get("cost") or 0),
        "period_start": payload.get("period_start"),
        "period_end": payload.get("period_end"),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "updated_by": user["id"],
    }
    await db.marketing_costs.update_one(
        {"company_id": user["company_id"], "source": doc["source"],
         "period_start": doc["period_start"], "period_end": doc["period_end"]},
        {"$set": doc}, upsert=True,
    )
    return {"ok": True}
