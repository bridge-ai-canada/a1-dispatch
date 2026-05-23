"""AI feature endpoints — all powered by ai_service."""
import uuid
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from deps import db, now_iso, get_current_user
import ai_service

router = APIRouter()


# -------------------- Models --------------------
class GenerateEstimateIn(BaseModel):
    prompt: str


class CallSummaryIn(BaseModel):
    notes: str
    customer_id: Optional[str] = None


class TechNotesIn(BaseModel):
    notes: str


class JobSummaryIn(BaseModel):
    job_id: str


class UpsellIn(BaseModel):
    job_id: str


class DispatchAskIn(BaseModel):
    question: str
    session_id: Optional[str] = None


class ChatbotIn(BaseModel):
    company_id: str
    message: str
    session_id: Optional[str] = None


class MaintenanceScanIn(BaseModel):
    limit: int = 200


# -------------------- 1. Estimate generator --------------------
@router.post("/ai/estimates/generate")
async def ai_estimate_generate(body: GenerateEstimateIn, user: dict = Depends(get_current_user)):
    if not body.prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt required")
    company = await db.companies.find_one({"id": user["company_id"]}, {"_id": 0}) or {}
    try:
        result = await ai_service.generate_estimate(
            prompt=body.prompt, company=company, user_id=user["id"]
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"AI generation failed: {e}")
    return result


# -------------------- 2. Call summary --------------------
@router.post("/ai/calls/summarize")
async def ai_summarize_call(body: CallSummaryIn, user: dict = Depends(get_current_user)):
    if not body.notes.strip():
        raise HTTPException(status_code=400, detail="Notes required")
    try:
        result = await ai_service.summarize_call(
            notes=body.notes, company_id=user["company_id"], user_id=user["id"]
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"AI call summary failed: {e}")
    # Optionally persist on the customer record
    if body.customer_id:
        await db.communications.insert_one({
            "id": str(uuid.uuid4()),
            "company_id": user["company_id"],
            "customer_id": body.customer_id,
            "actor_id": user["id"], "actor_name": user.get("name"),
            "channel": "call", "direction": "inbound",
            "summary": result.get("summary", "")[:300],
            "body": "[AI-summarized] " + body.notes[:1500],
            "meta": {k: result.get(k) for k in ("intent", "sentiment", "next_step", "action_items")},
            "created_at": now_iso(),
        })
    return result


# -------------------- 3. Tech notes polish --------------------
@router.post("/ai/tech-notes/polish")
async def ai_polish_tech_notes(body: TechNotesIn, user: dict = Depends(get_current_user)):
    if not body.notes.strip():
        raise HTTPException(status_code=400, detail="Notes required")
    try:
        polished = await ai_service.polish_tech_notes(
            notes=body.notes, company_id=user["company_id"], user_id=user["id"]
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"AI failed: {e}")
    return {"polished": polished}


# -------------------- 4. Job summary --------------------
@router.post("/ai/jobs/summarize")
async def ai_summarize_job(body: JobSummaryIn, user: dict = Depends(get_current_user)):
    job = await db.jobs.find_one(
        {"id": body.job_id, "company_id": user["company_id"]}, {"_id": 0}
    )
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    try:
        summary = await ai_service.summarize_job(
            job=job, company_id=user["company_id"], user_id=user["id"]
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"AI failed: {e}")
    return {"summary": summary}


# -------------------- 5. Upsell --------------------
@router.post("/ai/jobs/upsell")
async def ai_upsell(body: UpsellIn, user: dict = Depends(get_current_user)):
    job = await db.jobs.find_one(
        {"id": body.job_id, "company_id": user["company_id"]}, {"_id": 0}
    )
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    customer_jobs: list = []
    if job.get("customer_id"):
        customer_jobs = await db.jobs.find(
            {"company_id": user["company_id"], "customer_id": job["customer_id"],
             "id": {"$ne": job["id"]}},
            {"_id": 0},
        ).sort("created_at", -1).to_list(8)
    company = await db.companies.find_one({"id": user["company_id"]}, {"_id": 0}) or {}
    try:
        result = await ai_service.upsell_for_job(
            job=job, customer_jobs=customer_jobs, company=company, user_id=user["id"]
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"AI failed: {e}")
    return result


# -------------------- 6. Maintenance reminders --------------------
@router.post("/ai/maintenance/scan")
async def ai_maintenance_scan(body: MaintenanceScanIn, user: dict = Depends(get_current_user)):
    """Scan customers (or recent ones) for maintenance due. Returns list of suggestions."""
    company = await db.companies.find_one({"id": user["company_id"]}, {"_id": 0}) or {}
    trade = company.get("industry", "HVAC")
    customers = await db.customers.find(
        {"company_id": user["company_id"], "status": "active"}, {"_id": 0}
    ).sort("created_at", -1).to_list(max(1, body.limit))
    suggestions: list = []
    for cust in customers[:body.limit]:
        jobs = await db.jobs.find(
            {"company_id": user["company_id"], "customer_id": cust["id"]}, {"_id": 0}
        ).sort("created_at", -1).to_list(12)
        if not jobs:
            continue
        try:
            res = await ai_service.maintenance_check(customer=cust, jobs=jobs, trade=trade)
        except Exception:
            continue
        if res.get("is_due"):
            doc = {
                "id": str(uuid.uuid4()),
                "company_id": user["company_id"],
                "customer_id": cust["id"],
                "customer_name": cust.get("name"),
                "service_type": res.get("service_type", "Maintenance"),
                "reason": res.get("reason", ""),
                "cadence": res.get("recommended_cadence", "annual"),
                "status": "pending",
                "created_at": now_iso(),
            }
            await db.maintenance_suggestions.update_one(
                {"company_id": user["company_id"], "customer_id": cust["id"], "status": "pending"},
                {"$set": doc},
                upsert=True,
            )
            suggestions.append(doc)
    return {"scanned": len(customers), "suggested": len(suggestions)}


@router.get("/ai/maintenance/suggestions")
async def list_maintenance(user: dict = Depends(get_current_user)):
    items = await db.maintenance_suggestions.find(
        {"company_id": user["company_id"], "status": "pending"},
        {"_id": 0},
    ).sort("created_at", -1).to_list(200)
    return items


@router.post("/ai/maintenance/{sid}/dismiss")
async def dismiss_maintenance(sid: str, user: dict = Depends(get_current_user)):
    await db.maintenance_suggestions.update_one(
        {"id": sid, "company_id": user["company_id"]},
        {"$set": {"status": "dismissed", "dismissed_at": now_iso()}},
    )
    return {"ok": True}


# -------------------- 7. Dispatcher assistant --------------------
@router.post("/ai/dispatcher/ask")
async def ai_dispatcher_ask(body: DispatchAskIn, user: dict = Depends(get_current_user)):
    if not body.question.strip():
        raise HTTPException(status_code=400, detail="Question required")
    jobs = await db.jobs.find(
        {"company_id": user["company_id"],
         "status": {"$in": ["unscheduled", "won_bid", "scheduled_installation", "in_progress"]}},
        {"_id": 0},
    ).sort("scheduled_at", 1).to_list(30)
    team = await db.users.find(
        {"company_id": user["company_id"], "role": {"$in": ["technician", "dispatcher", "owner"]}},
        {"_id": 0, "password_hash": 0},
    ).to_list(60)
    session_id = body.session_id or f"dispatch-{user['id']}-{uuid.uuid4().hex[:8]}"
    try:
        answer = await ai_service.dispatcher_ask(
            question=body.question, jobs=jobs, team=team,
            company_id=user["company_id"], user_id=user["id"], session_id=session_id,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"AI failed: {e}")
    return {"answer": answer, "session_id": session_id}


# -------------------- 8. Customer chatbot (PUBLIC, no auth) --------------------
@router.post("/public/ai/chatbot")
async def ai_chatbot(body: ChatbotIn):
    if not body.message.strip():
        raise HTTPException(status_code=400, detail="Message required")
    company = await db.companies.find_one({"id": body.company_id}, {"_id": 0}) or None
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    session_id = body.session_id or f"chat-{body.company_id}-{uuid.uuid4().hex[:10]}"
    # Pull last 6 turns from this session for context
    history = await db.chatbot_messages.find(
        {"session_id": session_id}, {"_id": 0}
    ).sort("created_at", 1).to_list(20)
    try:
        reply = await ai_service.chatbot_reply(
            message=body.message, company=company, session_id=session_id, history=history,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"AI failed: {e}")
    now = now_iso()
    await db.chatbot_messages.insert_many([
        {"id": str(uuid.uuid4()), "company_id": body.company_id, "session_id": session_id,
         "role": "user", "content": body.message[:2000], "created_at": now},
        {"id": str(uuid.uuid4()), "company_id": body.company_id, "session_id": session_id,
         "role": "assistant", "content": reply[:2000], "created_at": now_iso()},
    ])
    return {"reply": reply, "session_id": session_id}


# -------------------- AI logs (audit) --------------------
@router.get("/ai/logs")
async def ai_logs(user: dict = Depends(get_current_user), limit: int = 50):
    if user.get("role") not in ("owner", "admin", "office_manager"):
        raise HTTPException(status_code=403, detail="Insufficient permission")
    items = await db.ai_logs.find(
        {"company_id": user["company_id"]},
        {"_id": 0},
    ).sort("created_at", -1).to_list(max(1, min(200, limit)))
    return items
