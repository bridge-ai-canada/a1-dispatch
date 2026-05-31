"""Super-admin tenant management: list/suspend/activate/delete companies + data export."""
import json
from datetime import datetime, timezone
from typing import Optional, Literal
from fastapi import APIRouter, HTTPException, Depends, Response
from pydantic import BaseModel

from deps import db, now_iso, require_role, log_activity
from whitelabel_service import plan as _plan

router = APIRouter()


class TenantStatusIn(BaseModel):
    status: Literal["active", "suspended"]
    reason: Optional[str] = ""


@router.get("/tenants")
async def list_tenants(
    user: dict = Depends(require_role("super_admin")),
    q: Optional[str] = None, status: Optional[str] = None, plan: Optional[str] = None,
):
    query: dict = {}
    if q:
        query["name"] = {"$regex": q, "$options": "i"}
    if status:
        query["subscription.status"] = status
    if plan:
        query["subscription.plan"] = plan
    companies = await db.companies.find(query, {"_id": 0}).sort("created_at", -1).to_list(2000)
    # Attach rollup counts
    out = []
    for c in companies:
        cid = c["id"]
        c["users_count"] = await db.users.count_documents({"company_id": cid, "active": True})
        c["jobs_count"] = await db.jobs.count_documents({"company_id": cid})
        agg = await db.jobs.aggregate([
            {"$match": {"company_id": cid, "paid": True}},
            {"$group": {"_id": None, "rev": {"$sum": "$price"}}},
        ]).to_list(1)
        c["paid_revenue"] = (agg[0]["rev"] if agg else 0) or 0
        out.append(c)
    return out


@router.get("/tenants/{company_id}")
async def get_tenant(company_id: str, user: dict = Depends(require_role("super_admin"))):
    company = await db.companies.find_one({"id": company_id}, {"_id": 0})
    if not company:
        raise HTTPException(status_code=404, detail="Tenant not found")
    company["users_count"] = await db.users.count_documents({"company_id": company_id})
    company["jobs_count"] = await db.jobs.count_documents({"company_id": company_id})
    company["customers_count"] = await db.customers.count_documents({"company_id": company_id})
    company["invoices_count"] = await db.invoices.count_documents({"company_id": company_id})
    return company


@router.patch("/tenants/{company_id}/status")
async def update_tenant_status(
    company_id: str, body: TenantStatusIn,
    user: dict = Depends(require_role("super_admin")),
):
    company = await db.companies.find_one({"id": company_id}, {"_id": 0})
    if not company:
        raise HTTPException(status_code=404, detail="Tenant not found")
    await db.companies.update_one(
        {"id": company_id},
        {"$set": {
            "subscription.status": body.status,
            "suspended_reason": body.reason if body.status == "suspended" else None,
            "subscription.updated_at": now_iso(),
        }},
    )
    # Suspend users if suspended (so they can't log in)
    if body.status == "suspended":
        await db.users.update_many(
            {"company_id": company_id, "role": {"$ne": "super_admin"}},
            {"$set": {"active": False}},
        )
    elif body.status == "active":
        await db.users.update_many(
            {"company_id": company_id}, {"$set": {"active": True}},
        )
    await log_activity(user, "tenant.status_changed",
                       meta={"company_id": company_id, "status": body.status})
    return {"ok": True, "status": body.status}


@router.delete("/tenants/{company_id}")
async def delete_tenant(company_id: str, user: dict = Depends(require_role("super_admin"))):
    """Hard delete a tenant and all its data. Irreversible."""
    company = await db.companies.find_one({"id": company_id}, {"_id": 0})
    if not company:
        raise HTTPException(status_code=404, detail="Tenant not found")
    collections = [
        "users", "jobs", "customers", "estimates", "invoices",
        "branches", "message_templates", "branding_audit",
        "activity", "communications", "properties", "equipment",
        "customer_files", "recurring_jobs", "sms_log", "ai_logs",
        "chatbot_messages", "shifts", "materials", "checklist_templates",
        "checklists", "subscription_checkouts", "api_keys",
    ]
    counts = {}
    for col in collections:
        try:
            res = await db[col].delete_many({"company_id": company_id})
            counts[col] = res.deleted_count
        except Exception:
            counts[col] = -1
    await db.companies.delete_one({"id": company_id})
    await log_activity(user, "tenant.deleted",
                       meta={"company_id": company_id, "name": company.get("name"), "counts": counts})
    return {"ok": True, "deleted": counts}


@router.get("/tenants/{company_id}/export")
async def export_tenant(company_id: str, user: dict = Depends(require_role("super_admin"))):
    """Dump all tenant data as JSON. Used for tenant data-export requests (GDPR/portability)."""
    company = await db.companies.find_one({"id": company_id}, {"_id": 0})
    if not company:
        raise HTTPException(status_code=404, detail="Tenant not found")
    bundle: dict = {
        "exported_at": now_iso(),
        "exported_by": user["id"],
        "company": company,
    }
    for col in [
        "users", "jobs", "customers", "estimates", "invoices",
        "branches", "message_templates", "communications",
        "properties", "equipment", "shifts", "materials", "sms_log",
    ]:
        bundle[col] = await db[col].find(
            {"company_id": company_id}, {"_id": 0, "password_hash": 0},
        ).to_list(None)
    # Strip sensitive fields from users
    for u in bundle.get("users", []):
        u.pop("password_hash", None)
        u.pop("mfa_secret", None)
    return Response(
        content=json.dumps(bundle, default=str, indent=2),
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="tenant-{company_id}-{datetime.now(timezone.utc).strftime("%Y%m%d")}.json"',
        },
    )


@router.get("/tenants/_/metrics")
async def platform_metrics(user: dict = Depends(require_role("super_admin"))):
    """Platform-wide MRR + tenant counts (dashboard)."""
    pipeline_companies = await db.companies.aggregate([
        {"$group": {"_id": "$subscription.plan", "count": {"$sum": 1}}},
    ]).to_list(50)
    by_plan = {item["_id"] or "basic": item["count"] for item in pipeline_companies}
    mrr = 0
    for plan_key, count in by_plan.items():
        p = _plan(plan_key)
        mrr += int(p["price_usd"]) * int(count)
    total_tenants = await db.companies.count_documents({})
    suspended = await db.companies.count_documents({"subscription.status": "suspended"})
    active = total_tenants - suspended
    return {
        "tenants_total": total_tenants,
        "tenants_active": active,
        "tenants_suspended": suspended,
        "by_plan": by_plan,
        "mrr_usd": mrr,
        "arr_usd": mrr * 12,
    }
