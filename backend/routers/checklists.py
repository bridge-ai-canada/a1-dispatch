"""Checklist templates + per-job checklist completion."""
import uuid
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from deps import db, now_iso, get_current_user, log_activity

router = APIRouter()


class ChecklistItemIn(BaseModel):
    title: str
    required: bool = False


class ChecklistTemplateIn(BaseModel):
    name: str
    job_type: Optional[str] = ""
    items: List[ChecklistItemIn]


class ChecklistTemplateUpdate(BaseModel):
    name: Optional[str] = None
    job_type: Optional[str] = None
    items: Optional[List[ChecklistItemIn]] = None


class ApplyTemplateIn(BaseModel):
    template_id: str


class ToggleIn(BaseModel):
    item_id: str
    completed: bool


# -------------------- Templates --------------------
@router.post("/checklist-templates")
async def create_template(body: ChecklistTemplateIn, user: dict = Depends(get_current_user)):
    tid = str(uuid.uuid4())
    doc = {
        "id": tid,
        "company_id": user["company_id"],
        "name": body.name,
        "job_type": body.job_type or "",
        "items": [{**i.dict(), "id": str(uuid.uuid4())} for i in body.items],
        "created_by": user["id"],
        "created_at": now_iso(),
    }
    await db.checklist_templates.insert_one(doc)
    await log_activity(user, "checklist_template.created", "checklist_template", tid, {"name": body.name})
    doc.pop("_id", None)
    return doc


@router.get("/checklist-templates")
async def list_templates(user: dict = Depends(get_current_user)):
    items = await db.checklist_templates.find(
        {"company_id": user["company_id"]}, {"_id": 0}
    ).sort("created_at", -1).to_list(100)
    return items


@router.put("/checklist-templates/{tid}")
async def update_template(tid: str, body: ChecklistTemplateUpdate, user: dict = Depends(get_current_user)):
    doc = await db.checklist_templates.find_one({"id": tid, "company_id": user["company_id"]}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Template not found")
    updates = body.dict(exclude_none=True)
    if "items" in updates:
        updates["items"] = [{**(i if isinstance(i, dict) else i.dict()),
                             "id": (i.get("id") if isinstance(i, dict) else None) or str(uuid.uuid4())}
                            for i in updates["items"]]
    await db.checklist_templates.update_one({"id": tid}, {"$set": updates})
    return await db.checklist_templates.find_one({"id": tid}, {"_id": 0})


@router.delete("/checklist-templates/{tid}")
async def delete_template(tid: str, user: dict = Depends(get_current_user)):
    res = await db.checklist_templates.delete_one({"id": tid, "company_id": user["company_id"]})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Template not found")
    return {"ok": True}


# -------------------- Per-job checklist --------------------
@router.post("/jobs/{job_id}/checklist/apply")
async def apply_template(job_id: str, body: ApplyTemplateIn, user: dict = Depends(get_current_user)):
    job = await db.jobs.find_one({"id": job_id, "company_id": user["company_id"]}, {"_id": 0})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    tpl = await db.checklist_templates.find_one(
        {"id": body.template_id, "company_id": user["company_id"]}, {"_id": 0}
    )
    if not tpl:
        raise HTTPException(status_code=404, detail="Template not found")
    checklist = [
        {
            "id": str(uuid.uuid4()),
            "title": it["title"],
            "required": bool(it.get("required")),
            "completed": False,
            "completed_at": None,
            "completed_by": None,
        }
        for it in (tpl.get("items") or [])
    ]
    await db.jobs.update_one({"id": job_id}, {"$set": {"checklist": checklist}})
    return {"checklist": checklist}


@router.post("/jobs/{job_id}/checklist/toggle")
async def toggle_item(job_id: str, body: ToggleIn, user: dict = Depends(get_current_user)):
    job = await db.jobs.find_one({"id": job_id, "company_id": user["company_id"]}, {"_id": 0})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    items = list(job.get("checklist") or [])
    for it in items:
        if it.get("id") == body.item_id:
            it["completed"] = bool(body.completed)
            it["completed_at"] = now_iso() if body.completed else None
            it["completed_by"] = user["id"] if body.completed else None
            break
    else:
        raise HTTPException(status_code=404, detail="Checklist item not found")
    await db.jobs.update_one({"id": job_id}, {"$set": {"checklist": items}})
    return {"checklist": items}
