"""Branches (sub-locations) + Franchises (parent-of-companies).

Branches live inside a single company (`branches.company_id`).
Franchises group multiple companies under a `franchises.id` (parent_franchise_id on company).
"""
import uuid
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from deps import db, now_iso, get_current_user, require_role, log_activity
from whitelabel_service import has_feature

router = APIRouter()


# -------------------- Models --------------------
class BranchIn(BaseModel):
    name: str
    address: Optional[str] = ""
    city: Optional[str] = ""
    state: Optional[str] = ""
    postal_code: Optional[str] = ""
    phone: Optional[str] = ""
    email: Optional[str] = ""
    manager_user_id: Optional[str] = None
    active: bool = True


class BranchUpdate(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    manager_user_id: Optional[str] = None
    active: Optional[bool] = None


class FranchiseIn(BaseModel):
    name: str
    description: Optional[str] = ""
    owner_email: Optional[str] = None  # optional contact


class FranchiseUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    owner_email: Optional[str] = None


# -------------------- Plan-gate helper --------------------
async def _require_branches(user: dict):
    company = await db.companies.find_one(
        {"id": user["company_id"]}, {"_id": 0, "subscription": 1},
    ) or {}
    plan_key = (company.get("subscription") or {}).get("plan")
    if not has_feature(plan_key, "branches"):
        raise HTTPException(status_code=402, detail="Multi-branch is not included in your plan. Upgrade to Pro or Enterprise.")


async def _require_franchise(user: dict):
    company = await db.companies.find_one(
        {"id": user["company_id"]}, {"_id": 0, "subscription": 1},
    ) or {}
    plan_key = (company.get("subscription") or {}).get("plan")
    if not has_feature(plan_key, "franchise"):
        raise HTTPException(status_code=402, detail="Franchise management requires the Enterprise plan.")


# -------------------- Branches --------------------
@router.get("/branches")
async def list_branches(user: dict = Depends(get_current_user)):
    items = await db.branches.find(
        {"company_id": user["company_id"]}, {"_id": 0},
    ).sort("created_at", 1).to_list(500)
    return items


@router.post("/branches")
async def create_branch(
    body: BranchIn,
    user: dict = Depends(require_role("owner", "office_manager", "super_admin")),
):
    await _require_branches(user)
    bid = str(uuid.uuid4())
    doc = body.model_dump()
    doc.update({
        "id": bid, "company_id": user["company_id"],
        "created_by": user["id"], "created_at": now_iso(),
    })
    await db.branches.insert_one(doc)
    await log_activity(user, "branch.created", meta={"branch_id": bid, "name": body.name})
    return {k: v for k, v in doc.items() if k != "_id"}


@router.patch("/branches/{branch_id}")
async def update_branch(
    branch_id: str,
    body: BranchUpdate,
    user: dict = Depends(require_role("owner", "office_manager", "super_admin")),
):
    payload = body.model_dump(exclude_unset=True, exclude_none=True)
    if not payload:
        existing = await db.branches.find_one(
            {"id": branch_id, "company_id": user["company_id"]}, {"_id": 0},
        )
        if not existing:
            raise HTTPException(status_code=404, detail="Branch not found")
        return existing
    res = await db.branches.update_one(
        {"id": branch_id, "company_id": user["company_id"]}, {"$set": payload},
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Branch not found")
    await log_activity(user, "branch.updated", meta={"branch_id": branch_id})
    return await db.branches.find_one({"id": branch_id}, {"_id": 0})


@router.delete("/branches/{branch_id}")
async def delete_branch(
    branch_id: str,
    user: dict = Depends(require_role("owner", "super_admin")),
):
    res = await db.branches.delete_one(
        {"id": branch_id, "company_id": user["company_id"]},
    )
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Branch not found")
    # Unset branch_id on jobs that referenced it
    await db.jobs.update_many(
        {"company_id": user["company_id"], "branch_id": branch_id},
        {"$set": {"branch_id": None}},
    )
    await log_activity(user, "branch.deleted", meta={"branch_id": branch_id})
    return {"ok": True}


@router.get("/branches/{branch_id}/metrics")
async def branch_metrics(branch_id: str, user: dict = Depends(get_current_user)):
    """Return rollup metrics (jobs, revenue, open invoices) for a branch."""
    branch = await db.branches.find_one(
        {"id": branch_id, "company_id": user["company_id"]}, {"_id": 0},
    )
    if not branch:
        raise HTTPException(status_code=404, detail="Branch not found")
    jobs_total = await db.jobs.count_documents({"company_id": user["company_id"], "branch_id": branch_id})
    jobs_open = await db.jobs.count_documents({
        "company_id": user["company_id"], "branch_id": branch_id,
        "status": {"$nin": ["completed", "cancelled"]},
    })
    inv_open = await db.invoices.count_documents({
        "company_id": user["company_id"], "branch_id": branch_id,
        "status": {"$in": ["sent", "overdue", "partial"]},
    })
    pipeline = await db.jobs.aggregate([
        {"$match": {"company_id": user["company_id"], "branch_id": branch_id, "paid": True}},
        {"$group": {"_id": None, "revenue": {"$sum": "$price"}}},
    ]).to_list(1)
    revenue = pipeline[0]["revenue"] if pipeline else 0
    return {
        "branch_id": branch_id, "name": branch.get("name"),
        "jobs_total": jobs_total, "jobs_open": jobs_open,
        "invoices_open": inv_open, "revenue_paid": revenue,
    }


# -------------------- Franchises (super_admin) --------------------
@router.get("/franchises")
async def list_franchises(user: dict = Depends(require_role("super_admin"))):
    items = await db.franchises.find({}, {"_id": 0}).sort("created_at", -1).to_list(500)
    # Attach child-company counts
    for f in items:
        f["company_count"] = await db.companies.count_documents({"parent_franchise_id": f["id"]})
    return items


@router.post("/franchises")
async def create_franchise(body: FranchiseIn, user: dict = Depends(require_role("super_admin"))):
    fid = str(uuid.uuid4())
    doc = body.model_dump()
    doc.update({"id": fid, "created_at": now_iso(), "created_by": user["id"]})
    await db.franchises.insert_one(doc)
    return {k: v for k, v in doc.items() if k != "_id"}


@router.patch("/franchises/{franchise_id}")
async def update_franchise(
    franchise_id: str, body: FranchiseUpdate,
    user: dict = Depends(require_role("super_admin")),
):
    payload = body.model_dump(exclude_unset=True, exclude_none=True)
    if payload:
        await db.franchises.update_one({"id": franchise_id}, {"$set": payload})
    return await db.franchises.find_one({"id": franchise_id}, {"_id": 0})


@router.post("/franchises/{franchise_id}/attach-company")
async def attach_company_to_franchise(
    franchise_id: str,
    company_id: str,
    user: dict = Depends(require_role("super_admin")),
):
    franchise = await db.franchises.find_one({"id": franchise_id}, {"_id": 0})
    if not franchise:
        raise HTTPException(status_code=404, detail="Franchise not found")
    company = await db.companies.find_one({"id": company_id}, {"_id": 0})
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    await db.companies.update_one(
        {"id": company_id}, {"$set": {"parent_franchise_id": franchise_id}},
    )
    return {"ok": True}


@router.delete("/franchises/{franchise_id}/companies/{company_id}")
async def detach_company_from_franchise(
    franchise_id: str, company_id: str,
    user: dict = Depends(require_role("super_admin")),
):
    await db.companies.update_one(
        {"id": company_id, "parent_franchise_id": franchise_id},
        {"$unset": {"parent_franchise_id": ""}},
    )
    return {"ok": True}


@router.get("/franchises/{franchise_id}/rollup")
async def franchise_rollup(
    franchise_id: str, user: dict = Depends(require_role("super_admin")),
):
    """Cross-company rollup of revenue, job counts, active tenants."""
    company_ids: List[str] = [
        c["id"] async for c in db.companies.find(
            {"parent_franchise_id": franchise_id}, {"_id": 0, "id": 1},
        )
    ]
    if not company_ids:
        return {"company_count": 0, "jobs_total": 0, "jobs_open": 0, "revenue_paid": 0}
    jobs_total = await db.jobs.count_documents({"company_id": {"$in": company_ids}})
    jobs_open = await db.jobs.count_documents({
        "company_id": {"$in": company_ids},
        "status": {"$nin": ["completed", "cancelled"]},
    })
    pipeline = await db.jobs.aggregate([
        {"$match": {"company_id": {"$in": company_ids}, "paid": True}},
        {"$group": {"_id": None, "revenue": {"$sum": "$price"}}},
    ]).to_list(1)
    revenue = pipeline[0]["revenue"] if pipeline else 0
    return {
        "franchise_id": franchise_id,
        "company_count": len(company_ids),
        "jobs_total": jobs_total, "jobs_open": jobs_open,
        "revenue_paid": revenue,
    }
