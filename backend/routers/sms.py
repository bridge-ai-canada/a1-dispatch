"""SMS reminder endpoints + manual send. Twilio under the hood."""
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from deps import db, now_iso, get_current_user, log_activity, APP_NAME
import sms_service

router = APIRouter()


class SmsSendIn(BaseModel):
    to: str
    body: str
    job_id: Optional[str] = None
    customer_id: Optional[str] = None


class JobReminderIn(BaseModel):
    job_id: str
    template: Optional[str] = None  # override default reminder copy


def _format_reminder(job: dict, company_name: str) -> str:
    when = job.get("scheduled_at") or ""
    try:
        dt = datetime.fromisoformat(when.replace("Z", "+00:00"))
        when_human = dt.strftime("%a %b %d at %I:%M %p")
    except Exception:
        when_human = when
    title = job.get("title") or "your appointment"
    return (
        f"{company_name}: Reminder — {title} on {when_human}. "
        f"Reply STOP to unsubscribe."
    )


@router.get("/sms/status")
async def sms_status(user: dict = Depends(get_current_user)):
    return {
        "enabled": sms_service.is_enabled(),
        "from_number": sms_service.FROM_NUMBER if sms_service.is_enabled() else None,
    }


@router.post("/sms/send")
async def sms_send(body: SmsSendIn, user: dict = Depends(get_current_user)):
    if user.get("role") not in ("owner", "dispatcher", "office_manager", "super_admin", "csr"):
        raise HTTPException(status_code=403, detail="Forbidden")
    if not sms_service.is_enabled():
        raise HTTPException(status_code=503, detail="SMS is not configured. Add Twilio credentials in backend/.env")
    result = await asyncio.to_thread(sms_service.send_sms, body.to, body.body)
    await db.sms_log.insert_one({
        "company_id": user.get("company_id"),
        "sent_by": user["id"],
        "to": body.to,
        "body": body.body[:500],
        "job_id": body.job_id,
        "customer_id": body.customer_id,
        "ok": result.get("ok", False),
        "sid": result.get("sid"),
        "error": result.get("error"),
        "created_at": now_iso(),
    })
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error") or "SMS failed")
    await log_activity(user.get("company_id"), user["id"], "sms.sent",
                       {"to": body.to, "job_id": body.job_id})
    return result


@router.post("/sms/job-reminder")
async def sms_job_reminder(body: JobReminderIn, user: dict = Depends(get_current_user)):
    """Send an SMS reminder to the customer attached to a job."""
    if user.get("role") not in ("owner", "dispatcher", "office_manager", "super_admin", "csr"):
        raise HTTPException(status_code=403, detail="Forbidden")
    if not sms_service.is_enabled():
        raise HTTPException(status_code=503, detail="SMS is not configured. Add Twilio credentials in backend/.env")
    job = await db.jobs.find_one(
        {"id": body.job_id, "company_id": user["company_id"]}, {"_id": 0},
    )
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    phone = job.get("customer_phone")
    if not phone:
        raise HTTPException(status_code=400, detail="Job has no customer phone")
    company = await db.companies.find_one(
        {"id": user["company_id"]}, {"_id": 0, "name": 1},
    )
    text = body.template or _format_reminder(job, (company or {}).get("name") or APP_NAME)
    result = await asyncio.to_thread(sms_service.send_sms, phone, text)
    await db.sms_log.insert_one({
        "company_id": user["company_id"],
        "sent_by": user["id"],
        "to": phone,
        "body": text[:500],
        "job_id": job["id"],
        "customer_id": job.get("customer_id"),
        "ok": result.get("ok", False),
        "sid": result.get("sid"),
        "error": result.get("error"),
        "created_at": now_iso(),
    })
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error") or "SMS failed")
    # Tag job so we don't double-send via cron
    await db.jobs.update_one(
        {"id": job["id"]}, {"$set": {"reminder_sms_sent_at": now_iso()}},
    )
    await log_activity(user["company_id"], user["id"], "sms.reminder_sent",
                       {"job_id": job["id"], "to": phone})
    return result


@router.post("/sms/send-due-reminders")
async def sms_send_due_reminders(
    window_hours: int = 24,
    user: dict = Depends(get_current_user),
):
    """Send SMS reminders for all jobs scheduled within the next `window_hours` hours
    that haven't already received a reminder. Owner/dispatcher only."""
    if user.get("role") not in ("owner", "dispatcher", "office_manager", "super_admin"):
        raise HTTPException(status_code=403, detail="Forbidden")
    if not sms_service.is_enabled():
        raise HTTPException(status_code=503, detail="SMS is not configured. Add Twilio credentials in backend/.env")
    now = datetime.now(timezone.utc)
    until = (now + timedelta(hours=window_hours)).isoformat()
    cur = db.jobs.find({
        "company_id": user["company_id"],
        "status": {"$in": ["scheduled_installation", "in_progress"]},
        "scheduled_at": {"$gte": now.isoformat(), "$lte": until},
        "reminder_sms_sent_at": {"$in": [None, ""]},
        "customer_phone": {"$nin": [None, ""]},
    }, {"_id": 0})
    company = await db.companies.find_one(
        {"id": user["company_id"]}, {"_id": 0, "name": 1},
    )
    company_name = (company or {}).get("name") or APP_NAME
    sent, failed = 0, 0
    async for job in cur:
        text = _format_reminder(job, company_name)
        result = await asyncio.to_thread(sms_service.send_sms, job["customer_phone"], text)
        await db.sms_log.insert_one({
            "company_id": user["company_id"],
            "sent_by": user["id"],
            "to": job["customer_phone"],
            "body": text[:500],
            "job_id": job["id"],
            "customer_id": job.get("customer_id"),
            "ok": result.get("ok", False),
            "sid": result.get("sid"),
            "error": result.get("error"),
            "created_at": now_iso(),
        })
        if result.get("ok"):
            sent += 1
            await db.jobs.update_one(
                {"id": job["id"]}, {"$set": {"reminder_sms_sent_at": now_iso()}},
            )
        else:
            failed += 1
    await log_activity(user["company_id"], user["id"], "sms.batch_reminders",
                       {"sent": sent, "failed": failed, "window_hours": window_hours})
    return {"sent": sent, "failed": failed}


@router.get("/sms/log")
async def sms_log(user: dict = Depends(get_current_user), limit: int = 50):
    if user.get("role") not in ("owner", "dispatcher", "office_manager", "super_admin", "csr"):
        raise HTTPException(status_code=403, detail="Forbidden")
    items = await db.sms_log.find(
        {"company_id": user["company_id"]}, {"_id": 0},
    ).sort("created_at", -1).to_list(min(limit, 200))
    return items
