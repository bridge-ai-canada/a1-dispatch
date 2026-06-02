"""Materials catalog + per-job material usage."""
import uuid
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from deps import db, now_iso, get_current_user, log_activity

router = APIRouter()


class MaterialIn(BaseModel):
    name: str
    sku: Optional[str] = ""
    unit: Optional[str] = "each"
    unit_cost: float = 0.0
    unit_price: float = 0.0
    stock: Optional[int] = None  # null = not tracked


class MaterialUpdate(BaseModel):
    name: Optional[str] = None
    sku: Optional[str] = None
    unit: Optional[str] = None
    unit_cost: Optional[float] = None
    unit_price: Optional[float] = None
    stock: Optional[int] = None


class UseMaterialIn(BaseModel):
    material_id: Optional[str] = None  # use catalog item
    name: Optional[str] = None  # OR custom name
    qty: float = 1.0
    unit_cost: Optional[float] = None
    unit_price: Optional[float] = None


# -------------------- Catalog --------------------
@router.post("/materials")
async def create_material(body: MaterialIn, user: dict = Depends(get_current_user)):
    mid = str(uuid.uuid4())
    doc = {
        "id": mid,
        "company_id": user["company_id"],
        **body.dict(),
        "created_at": now_iso(),
    }
    await db.materials.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.get("/materials")
async def list_materials(user: dict = Depends(get_current_user), q: Optional[str] = None):
    query = {"company_id": user["company_id"]}
    if q:
        query["$or"] = [
            {"name": {"$regex": q, "$options": "i"}},
            {"sku": {"$regex": q, "$options": "i"}},
        ]
    items = await db.materials.find(query, {"_id": 0}).sort("name", 1).to_list(500)
    return items


@router.put("/materials/{mid}")
async def update_material(mid: str, body: MaterialUpdate, user: dict = Depends(get_current_user)):
    res = await db.materials.update_one(
        {"id": mid, "company_id": user["company_id"]},
        {"$set": body.dict(exclude_none=True)},
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Material not found")
    return await db.materials.find_one({"id": mid}, {"_id": 0})


@router.delete("/materials/{mid}")
async def delete_material(mid: str, user: dict = Depends(get_current_user)):
    res = await db.materials.delete_one({"id": mid, "company_id": user["company_id"]})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Material not found")
    return {"ok": True}


# -------------------- Per-job usage --------------------
@router.post("/jobs/{job_id}/materials")
async def add_to_job(job_id: str, body: UseMaterialIn, user: dict = Depends(get_current_user)):
    job = await db.jobs.find_one({"id": job_id, "company_id": user["company_id"]}, {"_id": 0})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    name = body.name
    unit_cost = body.unit_cost or 0.0
    unit_price = body.unit_price or 0.0
    if body.material_id:
        mat = await db.materials.find_one(
            {"id": body.material_id, "company_id": user["company_id"]}, {"_id": 0}
        )
        if not mat:
            raise HTTPException(status_code=404, detail="Catalog material not found")
        name = name or mat["name"]
        if body.unit_cost is None:
            unit_cost = float(mat.get("unit_cost") or 0)
        if body.unit_price is None:
            unit_price = float(mat.get("unit_price") or 0)
        # decrement stock if tracked
        if mat.get("stock") is not None:
            await db.materials.update_one(
                {"id": body.material_id},
                {"$inc": {"stock": -int(body.qty or 0)}},
            )
    if not name:
        raise HTTPException(status_code=400, detail="Material name or material_id required")

    entry = {
        "id": str(uuid.uuid4()),
        "material_id": body.material_id,
        "name": name,
        "qty": float(body.qty or 0),
        "unit_cost": float(unit_cost or 0),
        "unit_price": float(unit_price or 0),
        "added_by": user["id"],
        "added_by_name": user.get("name") or user.get("email"),
        "added_at": now_iso(),
    }
    existing = list(job.get("materials_used") or [])
    existing.append(entry)
    await db.jobs.update_one({"id": job_id}, {"$set": {"materials_used": existing}})
    await log_activity(user, "job.material_added", "job", job_id,
                       {"material": name, "qty": entry["qty"]})
    return entry


@router.delete("/jobs/{job_id}/materials/{entry_id}")
async def remove_from_job(job_id: str, entry_id: str, user: dict = Depends(get_current_user)):
    job = await db.jobs.find_one({"id": job_id, "company_id": user["company_id"]}, {"_id": 0})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    entries = [m for m in (job.get("materials_used") or []) if m.get("id") != entry_id]
    await db.jobs.update_one({"id": job_id}, {"$set": {"materials_used": entries}})
    return {"ok": True}
