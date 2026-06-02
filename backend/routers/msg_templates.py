"""Email + SMS message templates (per-tenant). Variable substitution via whitelabel_service."""
import uuid
from typing import Optional, Literal
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from deps import db, now_iso, get_current_user, require_role, log_activity
from whitelabel_service import (
    DEFAULT_TEMPLATES, TEMPLATE_VARIABLES, render_template, find_variables,
)

router = APIRouter()


class TemplateIn(BaseModel):
    key: str
    kind: Literal["email", "sms"]
    event: str
    subject: Optional[str] = ""
    body: str
    enabled: bool = True


class TemplateUpdate(BaseModel):
    subject: Optional[str] = None
    body: Optional[str] = None
    enabled: Optional[bool] = None
    event: Optional[str] = None


class PreviewIn(BaseModel):
    body: str
    subject: Optional[str] = ""
    ctx: Optional[dict] = None


async def _seed_defaults_for(company_id: str):
    """Idempotently seed default templates for a company."""
    existing_keys = {
        t["key"] async for t in db.message_templates.find(
            {"company_id": company_id}, {"_id": 0, "key": 1},
        )
    }
    to_insert = []
    for t in DEFAULT_TEMPLATES:
        if t["key"] in existing_keys:
            continue
        to_insert.append({
            "id": str(uuid.uuid4()),
            "company_id": company_id,
            "key": t["key"], "kind": t["kind"], "event": t["event"],
            "subject": t.get("subject", ""), "body": t["body"],
            "enabled": True, "is_system_default": True,
            "created_at": now_iso(),
        })
    if to_insert:
        await db.message_templates.insert_many(to_insert)


@router.get("/message-templates")
async def list_templates(user: dict = Depends(get_current_user), kind: Optional[str] = None):
    await _seed_defaults_for(user["company_id"])
    q = {"company_id": user["company_id"]}
    if kind:
        q["kind"] = kind
    items = await db.message_templates.find(q, {"_id": 0}).sort("created_at", 1).to_list(500)
    return items


@router.get("/message-templates/variables")
async def template_variables(user: dict = Depends(get_current_user)):
    return {"variables": TEMPLATE_VARIABLES}


@router.post("/message-templates")
async def create_template(
    body: TemplateIn,
    user: dict = Depends(require_role("owner", "office_manager", "super_admin")),
):
    existing = await db.message_templates.find_one(
        {"company_id": user["company_id"], "key": body.key},
    )
    if existing:
        raise HTTPException(status_code=409, detail="A template with that key already exists")
    tid = str(uuid.uuid4())
    doc = body.model_dump()
    doc.update({
        "id": tid, "company_id": user["company_id"],
        "is_system_default": False, "created_at": now_iso(),
    })
    await db.message_templates.insert_one(doc)
    await log_activity(user, "template.created", meta={"key": body.key, "kind": body.kind})
    return {k: v for k, v in doc.items() if k != "_id"}


@router.patch("/message-templates/{template_id}")
async def update_template(
    template_id: str, body: TemplateUpdate,
    user: dict = Depends(require_role("owner", "office_manager", "super_admin")),
):
    payload = body.model_dump(exclude_unset=True, exclude_none=True)
    if payload:
        res = await db.message_templates.update_one(
            {"id": template_id, "company_id": user["company_id"]}, {"$set": payload},
        )
        if res.matched_count == 0:
            raise HTTPException(status_code=404, detail="Template not found")
        await log_activity(user, "template.updated", meta={"id": template_id, "fields": list(payload.keys())})
    return await db.message_templates.find_one(
        {"id": template_id}, {"_id": 0},
    )


@router.delete("/message-templates/{template_id}")
async def delete_template(
    template_id: str,
    user: dict = Depends(require_role("owner", "office_manager", "super_admin")),
):
    tpl = await db.message_templates.find_one(
        {"id": template_id, "company_id": user["company_id"]}, {"_id": 0},
    )
    if not tpl:
        raise HTTPException(status_code=404, detail="Template not found")
    if tpl.get("is_system_default"):
        raise HTTPException(status_code=400, detail="System defaults cannot be deleted — toggle 'enabled' off instead")
    await db.message_templates.delete_one({"id": template_id})
    return {"ok": True}


@router.post("/message-templates/preview")
async def preview_template(body: PreviewIn, user: dict = Depends(get_current_user)):
    """Render with company defaults + provided ctx so users see exact final text."""
    company = await db.companies.find_one(
        {"id": user["company_id"]}, {"_id": 0, "name": 1, "branding": 1},
    ) or {}
    b = company.get("branding") or {}
    sample_ctx = {
        "company_name": b.get("app_name") or company.get("name") or "Your Company",
        "company_phone": b.get("support_phone") or "(555) 123-4567",
        "support_email": b.get("support_email") or "support@example.com",
        "support_phone": b.get("support_phone") or "(555) 123-4567",
        "customer_name": "Sarah Johnson",
        "customer_email": "sarah@example.com",
        "customer_phone": "(555) 234-1122",
        "job_title": "AC Tune-up",
        "job_scheduled_at": "Mon Feb 24 at 2:00 PM",
        "job_address": "1421 Oak St, Austin TX",
        "job_url": "https://app.example.com/jobs/sample",
        "invoice_number": "INV-001",
        "invoice_total": "$189.00",
        "invoice_url": "https://app.example.com/pay/sample",
        "estimate_number": "EST-001",
        "estimate_url": "https://app.example.com/proposal/sample",
        "eta_minutes": "20",
        "tracking_url": "https://app.example.com/track/sample",
        "branch_name": "Downtown",
    }
    if body.ctx:
        sample_ctx.update(body.ctx)
    return {
        "subject_rendered": render_template(body.subject or "", sample_ctx),
        "body_rendered": render_template(body.body, sample_ctx),
        "detected_variables": find_variables(body.body),
    }
