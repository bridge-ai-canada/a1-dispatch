"""CRM: customers, properties, equipment, communications, files, timeline, AI summary."""
import uuid
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File

from deps import (
    db, logger, now_iso, APP_NAME, EMERGENT_KEY,
    put_object, get_current_user, log_activity,
    CustomerIn, CustomerUpdate, PropertyIn, EquipmentIn, CommunicationIn,
)

router = APIRouter()


@router.get("/customers")
async def list_customers(
    user: dict = Depends(get_current_user),
    q: Optional[str] = None, status: Optional[str] = None, tag: Optional[str] = None,
    limit: int = 50, skip: int = 0,
):
    query = {"company_id": user["company_id"]}
    if status:
        query["status"] = status
    if tag:
        query["tags"] = tag
    if q:
        rx = {"$regex": q, "$options": "i"}
        query["$or"] = [{"name": rx}, {"phone": rx}, {"email": rx}, {"address": rx}]
    total = await db.customers.count_documents(query)
    items = await db.customers.find(
        query, {"_id": 0}
    ).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    return {"items": items, "total": total, "has_more": skip + len(items) < total, "limit": limit, "skip": skip}


@router.post("/customers")
async def create_customer(body: CustomerIn, user: dict = Depends(get_current_user)):
    doc = {
        "id": str(uuid.uuid4()),
        "company_id": user["company_id"],
        "created_at": now_iso(),
        "created_by": user["id"],
        "tags": body.tags or [],
        **body.model_dump(exclude={"tags"}),
    }
    await db.customers.insert_one(doc)
    doc.pop("_id", None)
    await log_activity(user, "customer.created", "customer", doc["id"], {"name": body.name})
    return doc


@router.get("/customers/{customer_id}")
async def get_customer(customer_id: str, user: dict = Depends(get_current_user)):
    cust = await db.customers.find_one({"id": customer_id, "company_id": user["company_id"]}, {"_id": 0})
    if not cust:
        raise HTTPException(status_code=404, detail="Customer not found")
    return cust


@router.patch("/customers/{customer_id}")
async def update_customer(customer_id: str, body: CustomerUpdate, user: dict = Depends(get_current_user)):
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields")
    updates["updated_at"] = now_iso()
    result = await db.customers.update_one(
        {"id": customer_id, "company_id": user["company_id"]}, {"$set": updates}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Customer not found")
    return await db.customers.find_one({"id": customer_id}, {"_id": 0})


# -------- Properties ----------
@router.get("/customers/{customer_id}/properties")
async def list_properties(customer_id: str, user: dict = Depends(get_current_user)):
    items = await db.properties.find(
        {"customer_id": customer_id, "company_id": user["company_id"]}, {"_id": 0}
    ).sort("created_at", -1).to_list(100)
    return items


@router.post("/customers/{customer_id}/properties")
async def create_property(customer_id: str, body: PropertyIn, user: dict = Depends(get_current_user)):
    cust = await db.customers.find_one({"id": customer_id, "company_id": user["company_id"]}, {"_id": 0})
    if not cust:
        raise HTTPException(status_code=404, detail="Customer not found")
    doc = {
        "id": str(uuid.uuid4()),
        "company_id": user["company_id"],
        "customer_id": customer_id,
        "created_at": now_iso(),
        **body.model_dump(),
    }
    await db.properties.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.delete("/properties/{property_id}")
async def delete_property(property_id: str, user: dict = Depends(get_current_user)):
    await db.equipment.delete_many({"property_id": property_id, "company_id": user["company_id"]})
    res = await db.properties.delete_one({"id": property_id, "company_id": user["company_id"]})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Not found")
    return {"ok": True}


# -------- Equipment ----------
@router.get("/customers/{customer_id}/equipment")
async def list_equipment(customer_id: str, user: dict = Depends(get_current_user)):
    items = await db.equipment.find(
        {"customer_id": customer_id, "company_id": user["company_id"]}, {"_id": 0}
    ).sort("created_at", -1).to_list(200)
    return items


@router.post("/customers/{customer_id}/equipment")
async def create_equipment(customer_id: str, body: EquipmentIn, user: dict = Depends(get_current_user)):
    prop = await db.properties.find_one(
        {"id": body.property_id, "customer_id": customer_id, "company_id": user["company_id"]}, {"_id": 0}
    )
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    doc = {
        "id": str(uuid.uuid4()),
        "company_id": user["company_id"],
        "customer_id": customer_id,
        "created_at": now_iso(),
        **body.model_dump(),
    }
    await db.equipment.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.delete("/equipment/{equipment_id}")
async def delete_equipment(equipment_id: str, user: dict = Depends(get_current_user)):
    res = await db.equipment.delete_one({"id": equipment_id, "company_id": user["company_id"]})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Not found")
    return {"ok": True}


# -------- Communications ----------
@router.get("/customers/{customer_id}/communications")
async def list_communications(customer_id: str, user: dict = Depends(get_current_user)):
    items = await db.communications.find(
        {"customer_id": customer_id, "company_id": user["company_id"]}, {"_id": 0}
    ).sort("created_at", -1).to_list(500)
    return items


@router.post("/customers/{customer_id}/communications")
async def create_communication(customer_id: str, body: CommunicationIn, user: dict = Depends(get_current_user)):
    doc = {
        "id": str(uuid.uuid4()),
        "company_id": user["company_id"],
        "customer_id": customer_id,
        "actor_id": user["id"],
        "actor_name": user["name"],
        "created_at": now_iso(),
        **body.model_dump(),
    }
    await db.communications.insert_one(doc)
    doc.pop("_id", None)
    return doc


# -------- Files ----------
@router.post("/customers/{customer_id}/files")
async def upload_customer_file(customer_id: str, file: UploadFile = File(...), user: dict = Depends(get_current_user)):
    cust = await db.customers.find_one({"id": customer_id, "company_id": user["company_id"]}, {"_id": 0})
    if not cust:
        raise HTTPException(status_code=404, detail="Customer not found")
    ext = (file.filename or "f").rsplit(".",1)[-1].lower() if "." in (file.filename or "") else "bin"
    path = f"{APP_NAME}/{user['company_id']}/customers/{customer_id}/{uuid.uuid4()}.{ext}"
    data = await file.read()
    result = put_object(path, data, file.content_type or "application/octet-stream")
    rec = {
        "id": str(uuid.uuid4()),
        "company_id": user["company_id"],
        "customer_id": customer_id,
        "filename": file.filename or "file",
        "path": result["path"],
        "content_type": file.content_type,
        "size": result.get("size", len(data)),
        "uploaded_by": user["id"],
        "uploaded_at": now_iso(),
    }
    await db.customer_files.insert_one(rec)
    rec.pop("_id", None)
    return rec


@router.get("/customers/{customer_id}/files")
async def list_customer_files(customer_id: str, user: dict = Depends(get_current_user)):
    items = await db.customer_files.find(
        {"customer_id": customer_id, "company_id": user["company_id"]}, {"_id": 0}
    ).sort("uploaded_at", -1).to_list(200)
    return items


@router.delete("/customers/{customer_id}/files/{file_id}")
async def delete_customer_file(customer_id: str, file_id: str, user: dict = Depends(get_current_user)):
    res = await db.customer_files.delete_one(
        {"id": file_id, "customer_id": customer_id, "company_id": user["company_id"]}
    )
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Not found")
    return {"ok": True}


# -------- Timeline ----------
@router.get("/customers/{customer_id}/timeline")
async def customer_timeline(customer_id: str, user: dict = Depends(get_current_user), limit: int = 100):
    cust = await db.customers.find_one({"id": customer_id, "company_id": user["company_id"]}, {"_id": 0})
    if not cust:
        raise HTTPException(status_code=404, detail="Customer not found")
    jobs = await db.jobs.find({"customer_id": customer_id, "company_id": user["company_id"]}, {"_id": 0}).to_list(200)
    comms = await db.communications.find({"customer_id": customer_id, "company_id": user["company_id"]}, {"_id": 0}).to_list(200)
    files = await db.customer_files.find({"customer_id": customer_id, "company_id": user["company_id"]}, {"_id": 0}).to_list(200)
    events = []
    for j in jobs:
        events.append({"kind": "job", "ts": j.get("created_at"), "title": j["title"], "ref": j["id"], "status": j.get("status"), "price": j.get("price")})
    for c in comms:
        events.append({"kind": "comm", "ts": c["created_at"], "channel": c.get("channel"), "summary": c["summary"], "actor": c.get("actor_name"), "ref": c["id"]})
    for f in files:
        events.append({"kind": "file", "ts": f["uploaded_at"], "title": f["filename"], "ref": f["id"]})
    events.sort(key=lambda e: e.get("ts") or "", reverse=True)
    return events[:limit]


# -------- AI summary ----------
@router.get("/customers/{customer_id}/summary")
async def customer_ai_summary(customer_id: str, user: dict = Depends(get_current_user)):
    cust = await db.customers.find_one({"id": customer_id, "company_id": user["company_id"]}, {"_id": 0})
    if not cust:
        raise HTTPException(status_code=404, detail="Customer not found")
    jobs = await db.jobs.find({"customer_id": customer_id, "company_id": user["company_id"]}, {"_id": 0}).sort("created_at", -1).to_list(50)
    equip = await db.equipment.find({"customer_id": customer_id, "company_id": user["company_id"]}, {"_id": 0}).to_list(50)
    if not EMERGENT_KEY:
        return {"summary": "AI summary unavailable (no LLM key configured).", "model": None, "error_code": "no_key"}
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        chat = LlmChat(
            api_key=EMERGENT_KEY,
            session_id=f"cust-summary-{customer_id}",
            system_message=(
                "You are a senior dispatcher writing a briefing AND a next-best-action for a field-service company. "
                "Reply with STRICT JSON only — no prose, no markdown fences. "
                'Schema: {"summary": "<4 short sentences, plain text>", '
                '"next_action": {"label": "<short imperative CTA, max 7 words>", '
                '"job_title": "<title for a draft job>", '
                '"job_type": "<HVAC|Plumbing|Electrical|Garage Doors|Roofing|Appliance Repair|Other>", '
                '"description": "<2-line note>", "price": <number, 0 if unknown>}}'
            ),
        ).with_model("anthropic", "claude-sonnet-4-5-20250929")
        job_lines = [f"- {j.get('created_at','')[:10]} {j.get('job_type','')} \"{j.get('title','')}\" status={j.get('status','')} ${j.get('price',0):.0f}" for j in jobs[:8]]
        equip_lines = [f"- {e.get('kind','')} {e.get('brand','')} {e.get('model','')} (installed {e.get('install_date') or '?'})" for e in equip[:8]]
        prompt = (
            f"Customer: {cust.get('name')} ({cust.get('status','active')}). Tags: {', '.join(cust.get('tags',[]))}. "
            f"Phone {cust.get('phone','')}. Address {cust.get('address','')}.\n\n"
            f"Recent jobs ({len(jobs)} total):\n" + ("\n".join(job_lines) or "- none") +
            f"\n\nEquipment ({len(equip)}):\n" + ("\n".join(equip_lines) or "- none") +
            "\n\nReturn the JSON now."
        )
        response = await chat.send_message(UserMessage(text=prompt))
        import json as _json, re as _re
        text = str(response).strip()
        m = _re.search(r"\{.*\}", text, _re.DOTALL)
        parsed = {}
        try:
            parsed = _json.loads(m.group(0) if m else text)
        except Exception:
            parsed = {"summary": text, "next_action": None}
        return {
            "summary": parsed.get("summary", text),
            "next_action": parsed.get("next_action"),
            "model": "claude-sonnet-4-5-20250929",
            "error_code": None,
        }
    except Exception as e:
        logger.error(f"AI summary error: {e}")
        return {"summary": f"Couldn't generate summary right now ({type(e).__name__}). Try again later.",
                "next_action": None, "model": None, "error_code": "llm_failure"}
