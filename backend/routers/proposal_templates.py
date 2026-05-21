"""Reusable estimate / invoice templates."""
import uuid
from typing import Optional, Literal
from fastapi import APIRouter, HTTPException, Depends

from deps import db, now_iso, get_current_user, log_activity
from billing import TemplateIn, TemplateUpdate

router = APIRouter()


@router.post("/templates")
async def create_template(body: TemplateIn, user: dict = Depends(get_current_user)):
    tid = str(uuid.uuid4())
    doc = {
        "id": tid,
        "company_id": user["company_id"],
        "name": body.name,
        "kind": body.kind,
        "description": body.description,
        "tiers": [t.dict() for t in body.tiers] if body.tiers else None,
        "line_items": [li.dict() for li in body.line_items] if body.line_items else None,
        "tax_rate": body.tax_rate,
        "terms": body.terms,
        "created_by": user["id"],
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    await db.proposal_templates.insert_one(doc)
    await log_activity(user, "template.created", "template", tid, {"name": body.name})
    doc.pop("_id", None)
    return doc


@router.get("/templates")
async def list_templates(user: dict = Depends(get_current_user),
                         kind: Optional[Literal["estimate", "invoice"]] = None):
    q = {"company_id": user["company_id"]}
    if kind:
        q["kind"] = kind
    items = await db.proposal_templates.find(q, {"_id": 0}).sort("created_at", -1).to_list(200)
    return items


@router.get("/templates/{tid}")
async def get_template(tid: str, user: dict = Depends(get_current_user)):
    doc = await db.proposal_templates.find_one({"id": tid, "company_id": user["company_id"]}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Template not found")
    return doc


@router.put("/templates/{tid}")
async def update_template(tid: str, body: TemplateUpdate, user: dict = Depends(get_current_user)):
    doc = await db.proposal_templates.find_one({"id": tid, "company_id": user["company_id"]}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Template not found")
    updates = body.dict(exclude_none=True)
    if "tiers" in updates and updates["tiers"]:
        updates["tiers"] = [t if isinstance(t, dict) else t.dict() for t in updates["tiers"]]
    if "line_items" in updates and updates["line_items"]:
        updates["line_items"] = [li if isinstance(li, dict) else li.dict() for li in updates["line_items"]]
    updates["updated_at"] = now_iso()
    await db.proposal_templates.update_one({"id": tid}, {"$set": updates})
    await log_activity(user, "template.updated", "template", tid, {})
    return await db.proposal_templates.find_one({"id": tid}, {"_id": 0})


@router.delete("/templates/{tid}")
async def delete_template(tid: str, user: dict = Depends(get_current_user)):
    doc = await db.proposal_templates.find_one({"id": tid, "company_id": user["company_id"]}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Template not found")
    await db.proposal_templates.delete_one({"id": tid})
    await log_activity(user, "template.deleted", "template", tid, {})
    return {"ok": True}
