"""Jobs, dashboard, photos, signature, invoice PDF."""
import uuid
import base64
from io import BytesIO
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form, Response
from pydantic import BaseModel

from deps import (
    db, now_iso, APP_NAME,
    put_object, delete_object,
    get_current_user, require_role,
    log_activity,
    JobIn, JobUpdate,
)

router = APIRouter()


class SignatureIn(BaseModel):
    image_base64: str
    signer_name: Optional[str] = ""


@router.get("/jobs")
async def list_jobs(
    user: dict = Depends(get_current_user),
    status: Optional[str] = None,
    assigned_to: Optional[str] = None,
    mine: bool = False,
):
    # Lazily materialize any due recurring jobs so the list always reflects them
    try:
        from routers.recurring import _materialize_due
        await _materialize_due(user["company_id"])
    except Exception:
        pass
    q = {"company_id": user["company_id"]}
    if status:
        q["status"] = status
    if assigned_to:
        q["assigned_to"] = assigned_to
    if mine:
        q["assigned_to"] = user["id"]
    items = await db.jobs.find(q, {"_id": 0}).sort("created_at", -1).to_list(1000)
    return items


@router.post("/jobs")
async def create_job(body: JobIn, user: dict = Depends(get_current_user)):
    data = body.model_dump()
    if data.get("scheduled_at") and data["status"] == "unscheduled":
        data["status"] = "scheduled_installation"
    doc = {
        "id": str(uuid.uuid4()),
        "company_id": user["company_id"],
        "created_by": user["id"],
        "created_at": now_iso(),
        "paid": False,
        **data,
    }
    await db.jobs.insert_one(doc)
    doc.pop("_id", None)
    await log_activity(user, "jobs.created", "job", doc["id"],
                       {"title": doc["title"], "status": doc["status"]})
    try:
        from ws_hub import hub
        await hub.broadcast(user["company_id"], "job.created", doc)
    except Exception:
        pass
    # Async geocode if there's an address
    if doc.get("address"):
        from bg_tasks import schedule_geocode
        schedule_geocode(doc["id"], user["company_id"], doc["address"])
    if doc.get("customer_id"):
        await db.communications.insert_one({
            "id": str(uuid.uuid4()), "company_id": user["company_id"],
            "customer_id": doc["customer_id"], "actor_id": user["id"], "actor_name": user["name"],
            "channel": "system", "direction": "internal",
            "summary": f"Job created: {doc['title']}", "body": "",
            "created_at": now_iso(),
        })
    # Push notification to the assigned tech (if any)
    if doc.get("assigned_to") and doc["assigned_to"] != user["id"]:
        try:
            from push_service import send_push_to_user
            when = ""
            if doc.get("scheduled_at"):
                try:
                    when = " · " + datetime.fromisoformat(doc["scheduled_at"]).strftime("%a %I:%M %p")
                except Exception:
                    pass
            await send_push_to_user(doc["assigned_to"], {
                "title": "New job assigned",
                "body": f'{doc["title"]}{when}',
                "url": f'/app/jobs/{doc["id"]}',
                "tag": f'job-{doc["id"]}',
            })
        except Exception:
            pass
    return doc


@router.get("/jobs/{job_id}")
async def get_job(job_id: str, user: dict = Depends(get_current_user)):
    job = await db.jobs.find_one({"id": job_id, "company_id": user["company_id"]}, {"_id": 0})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.patch("/jobs/{job_id}")
async def update_job(job_id: str, body: JobUpdate, user: dict = Depends(get_current_user)):
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    if updates.get("scheduled_at") and updates.get("status") is None:
        existing = await db.jobs.find_one(
            {"id": job_id, "company_id": user["company_id"]}, {"status": 1, "_id": 0}
        )
        if existing and existing.get("status") == "unscheduled":
            updates["status"] = "scheduled_installation"
    # Capture prior assignee so we can notify on reassignment
    prior = await db.jobs.find_one(
        {"id": job_id, "company_id": user["company_id"]},
        {"assigned_to": 1, "scheduled_at": 1, "title": 1},
    )
    updates["updated_at"] = now_iso()
    result = await db.jobs.update_one(
        {"id": job_id, "company_id": user["company_id"]}, {"$set": updates}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Job not found")
    job = await db.jobs.find_one({"id": job_id}, {"_id": 0})
    try:
        from ws_hub import hub
        await hub.broadcast(user["company_id"], "job.updated", job)
    except Exception:
        pass
    # Re-geocode if address changed
    if "address" in updates and updates["address"]:
        from bg_tasks import schedule_geocode
        schedule_geocode(job_id, user["company_id"], updates["address"])
    new_status = updates.get("status")
    PIPELINE_STATUSES = ("won_bid", "lost_bid", "on_hold",
                         "scheduled_installation", "in_progress", "completed", "cancelled")
    if new_status in PIPELINE_STATUSES:
        await log_activity(user, f"jobs.{new_status}", "job", job_id,
                           {"title": job.get("title")})
    if new_status in PIPELINE_STATUSES and job.get("customer_id"):
        verb = {
            "won_bid": "bid won for",
            "lost_bid": "bid lost on",
            "on_hold": "placed on hold",
            "scheduled_installation": "scheduled for installation",
            "in_progress": "started",
            "completed": "completed",
            "cancelled": "cancelled",
        }[new_status]
        await db.communications.insert_one({
            "id": str(uuid.uuid4()), "company_id": user["company_id"],
            "customer_id": job["customer_id"], "actor_id": user["id"], "actor_name": user["name"],
            "channel": "system", "direction": "internal",
            "summary": f"Job {verb}: {job['title']}", "body": "",
            "created_at": now_iso(),
        })
    # Push to newly-assigned tech (or notify of reschedule to current tech)
    try:
        from push_service import send_push_to_user
        new_tech = updates.get("assigned_to")
        reschedule = "scheduled_at" in updates
        target_tech = new_tech if (new_tech and new_tech != (prior or {}).get("assigned_to")) else None
        notify_kind = None
        if target_tech and target_tech != user["id"]:
            notify_kind = ("New job assigned", target_tech)
        elif reschedule and job.get("assigned_to") and job["assigned_to"] != user["id"]:
            notify_kind = ("Job rescheduled", job["assigned_to"])
        if notify_kind:
            title, recipient = notify_kind
            when = ""
            if job.get("scheduled_at"):
                try:
                    when = " · " + datetime.fromisoformat(job["scheduled_at"]).strftime("%a %I:%M %p")
                except Exception:
                    pass
            await send_push_to_user(recipient, {
                "title": title,
                "body": f'{job.get("title","")}{when}',
                "url": f'/app/jobs/{job_id}',
                "tag": f'job-{job_id}',
            })
    except Exception:
        pass
    return job


@router.delete("/jobs/{job_id}")
async def delete_job(job_id: str, user: dict = Depends(require_role("owner", "dispatcher"))):
    result = await db.jobs.delete_one({"id": job_id, "company_id": user["company_id"]})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"ok": True}


@router.get("/dashboard/stats")
async def dashboard_stats(user: dict = Depends(get_current_user)):
    company_id = user["company_id"]
    today = datetime.now(timezone.utc).date().isoformat()
    all_jobs = await db.jobs.find({"company_id": company_id}, {"_id": 0}).to_list(2000)
    technicians = await db.users.count_documents({"company_id": company_id, "role": "technician"})

    jobs_today = 0; revenue_today = 0.0; revenue_total = 0.0
    completed = 0; in_progress = 0; scheduled = 0; unscheduled = 0
    won_bid = 0; lost_bid = 0; on_hold = 0
    for j in all_jobs:
        s = j.get("scheduled_at") or ""
        if s.startswith(today):
            jobs_today += 1
        status = j.get("status")
        if status == "completed":
            completed += 1
            revenue_total += float(j.get("price") or 0)
            if s.startswith(today):
                revenue_today += float(j.get("price") or 0)
        elif status == "in_progress":
            in_progress += 1
        elif status in ("scheduled_installation", "scheduled"):  # legacy fallback
            scheduled += 1
        elif status == "unscheduled":
            unscheduled += 1
        elif status == "won_bid":
            won_bid += 1
        elif status == "lost_bid":
            lost_bid += 1
        elif status == "on_hold":
            on_hold += 1

    total = len(all_jobs)
    completion_rate = round((completed / total) * 100, 1) if total else 0.0
    return {
        "jobs_today": jobs_today,
        "revenue_today": revenue_today,
        "revenue_total": revenue_total,
        "active_technicians": technicians,
        "completion_rate": completion_rate,
        "totals": {
            "total": total, "completed": completed, "in_progress": in_progress,
            "scheduled": scheduled, "unscheduled": unscheduled,
            "won_bid": won_bid, "lost_bid": lost_bid, "on_hold": on_hold,
        },
    }


@router.post("/jobs/{job_id}/photos")
async def upload_job_photo(
    job_id: str,
    file: UploadFile = File(...),
    taken_at: Optional[str] = Form(None),
    caption: Optional[str] = Form(None),
    user: dict = Depends(get_current_user),
):
    job = await db.jobs.find_one({"id": job_id, "company_id": user["company_id"]}, {"_id": 0})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Only images allowed")
    ext = (file.filename or "img").rsplit(".", 1)[-1].lower() if "." in (file.filename or "") else "jpg"
    if ext not in {"jpg", "jpeg", "png", "webp", "gif"}:
        ext = "jpg"
    path = f"{APP_NAME}/{user['company_id']}/jobs/{job_id}/{uuid.uuid4()}.{ext}"
    data = await file.read()
    result = put_object(path, data, file.content_type)
    photo = {
        "id": str(uuid.uuid4()),
        "path": result["path"],
        "content_type": file.content_type,
        "size": result.get("size", len(data)),
        "uploaded_by": user["id"],
        "uploaded_at": now_iso(),
        "taken_at": taken_at or now_iso(),
        "caption": (caption or "")[:200],
        "kind": "photo",
    }
    await db.jobs.update_one(
        {"id": job_id, "company_id": user["company_id"]},
        {"$push": {"photos": photo}},
    )
    return photo


@router.post("/jobs/{job_id}/videos")
async def upload_job_video(
    job_id: str,
    file: UploadFile = File(...),
    taken_at: Optional[str] = Form(None),
    caption: Optional[str] = Form(None),
    user: dict = Depends(get_current_user),
):
    job = await db.jobs.find_one({"id": job_id, "company_id": user["company_id"]}, {"_id": 0})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if not file.content_type or not file.content_type.startswith("video/"):
        raise HTTPException(status_code=400, detail="Only videos allowed")
    ext = (file.filename or "vid").rsplit(".", 1)[-1].lower() if "." in (file.filename or "") else "mp4"
    if ext not in {"mp4", "mov", "m4v", "webm"}:
        ext = "mp4"
    path = f"{APP_NAME}/{user['company_id']}/jobs/{job_id}/{uuid.uuid4()}.{ext}"
    data = await file.read()
    if len(data) > 100 * 1024 * 1024:  # 100MB cap
        raise HTTPException(status_code=400, detail="Video too large (max 100MB)")
    result = put_object(path, data, file.content_type)
    video = {
        "id": str(uuid.uuid4()),
        "path": result["path"],
        "content_type": file.content_type,
        "size": result.get("size", len(data)),
        "uploaded_by": user["id"],
        "uploaded_at": now_iso(),
        "taken_at": taken_at or now_iso(),
        "caption": (caption or "")[:200],
        "kind": "video",
    }
    await db.jobs.update_one(
        {"id": job_id, "company_id": user["company_id"]},
        {"$push": {"videos": video}},
    )
    return video


@router.delete("/jobs/{job_id}/videos/{video_id}")
async def delete_job_video(job_id: str, video_id: str, user: dict = Depends(get_current_user)):
    job = await db.jobs.find_one(
        {"id": job_id, "company_id": user["company_id"], "videos.id": video_id}, {"_id": 0}
    )
    if not job:
        raise HTTPException(status_code=404, detail="Video not found")
    video = next((v for v in (job.get("videos") or []) if v.get("id") == video_id), None)
    if video and video.get("path"):
        delete_object(video["path"])
    await db.jobs.update_one(
        {"id": job_id, "company_id": user["company_id"]},
        {"$pull": {"videos": {"id": video_id}}},
    )
    return {"ok": True}


class VoiceNoteIn(BaseModel):
    text: str


@router.post("/jobs/{job_id}/voice-notes")
async def add_voice_note(job_id: str, body: VoiceNoteIn, user: dict = Depends(get_current_user)):
    job = await db.jobs.find_one({"id": job_id, "company_id": user["company_id"]}, {"_id": 0})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if not body.text.strip():
        raise HTTPException(status_code=400, detail="Voice note text required")
    entry = {
        "id": str(uuid.uuid4()),
        "text": body.text.strip()[:2000],
        "author_id": user["id"],
        "author_name": user.get("name") or user.get("email"),
        "created_at": now_iso(),
    }
    await db.jobs.update_one(
        {"id": job_id, "company_id": user["company_id"]},
        {"$push": {"voice_notes": entry}},
    )
    return entry


@router.delete("/jobs/{job_id}/photos/{photo_id}")
async def delete_job_photo(job_id: str, photo_id: str, user: dict = Depends(get_current_user)):
    job = await db.jobs.find_one(
        {"id": job_id, "company_id": user["company_id"], "photos.id": photo_id}, {"_id": 0}
    )
    if not job:
        raise HTTPException(status_code=404, detail="Photo not found")
    photo = next((p for p in (job.get("photos") or []) if p.get("id") == photo_id), None)
    if photo and photo.get("path"):
        delete_object(photo["path"])
    await db.jobs.update_one(
        {"id": job_id, "company_id": user["company_id"]},
        {"$pull": {"photos": {"id": photo_id}}},
    )
    return {"ok": True}


@router.post("/jobs/{job_id}/signature")
async def save_signature(job_id: str, body: SignatureIn, user: dict = Depends(get_current_user)):
    job = await db.jobs.find_one({"id": job_id, "company_id": user["company_id"]}, {"_id": 0})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    raw = body.image_base64
    if "," in raw:
        raw = raw.split(",", 1)[1]
    try:
        data = base64.b64decode(raw)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid base64 image")
    path = f"{APP_NAME}/{user['company_id']}/jobs/{job_id}/sig-{uuid.uuid4()}.png"
    result = put_object(path, data, "image/png")
    sig = {
        "path": result["path"],
        "signer_name": body.signer_name or "",
        "signed_at": now_iso(),
    }
    await db.jobs.update_one(
        {"id": job_id, "company_id": user["company_id"]},
        {"$set": {"signature": sig}},
    )
    return sig


@router.get("/jobs/{job_id}/invoice.pdf")
async def invoice_pdf(job_id: str, user: dict = Depends(get_current_user)):
    from reportlab.lib.pagesizes import LETTER
    from reportlab.lib.units import inch
    from reportlab.pdfgen import canvas as pdfcanvas
    from reportlab.lib.colors import HexColor

    job = await db.jobs.find_one({"id": job_id, "company_id": user["company_id"]}, {"_id": 0})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    company = await db.companies.find_one({"id": user["company_id"]}, {"_id": 0}) or {}
    primary = (company.get("branding") or {}).get("primary_color") or "#1D4ED8"
    accent  = (company.get("branding") or {}).get("accent_color") or "#DC2626"

    buf = BytesIO()
    c = pdfcanvas.Canvas(buf, pagesize=LETTER)
    W, H = LETTER

    c.setFillColor(HexColor(primary))
    c.rect(0, H - 0.9*inch, W, 0.9*inch, fill=1, stroke=0)
    c.setFillColor(HexColor("#FFFFFF"))
    c.setFont("Helvetica-Bold", 22)
    c.drawString(0.6*inch, H - 0.55*inch, company.get("name", "A1 Field Pro"))
    c.setFont("Helvetica", 10)
    c.drawString(0.6*inch, H - 0.75*inch, f"{company.get('industry','')} · INVOICE")

    c.setFillColor(HexColor("#0F172A"))
    c.setFont("Helvetica-Bold", 14)
    c.drawString(0.6*inch, H - 1.4*inch, "INVOICE")
    c.setFont("Helvetica", 10)
    c.drawString(0.6*inch, H - 1.6*inch, f"Job #: {job['id'][:8].upper()}")
    c.drawString(0.6*inch, H - 1.75*inch, f"Date: {datetime.now(timezone.utc).strftime('%b %d, %Y')}")

    c.setFont("Helvetica-Bold", 11)
    c.drawString(0.6*inch, H - 2.2*inch, "BILL TO")
    c.setFont("Helvetica", 10)
    c.drawString(0.6*inch, H - 2.4*inch, job.get("customer_name") or "Customer")
    if job.get("address"):  c.drawString(0.6*inch, H - 2.55*inch, job["address"])
    if job.get("customer_phone"): c.drawString(0.6*inch, H - 2.70*inch, job["customer_phone"])

    y = H - 3.4*inch
    c.setFillColor(HexColor("#F1F5F9"))
    c.rect(0.6*inch, y - 0.05*inch, W - 1.2*inch, 0.3*inch, fill=1, stroke=0)
    c.setFillColor(HexColor("#0F172A"))
    c.setFont("Helvetica-Bold", 10)
    c.drawString(0.7*inch, y + 0.05*inch, "DESCRIPTION")
    c.drawRightString(W - 0.7*inch, y + 0.05*inch, "AMOUNT")

    y -= 0.45*inch
    c.setFont("Helvetica", 11)
    c.drawString(0.7*inch, y, job.get("title", "Service"))
    c.drawRightString(W - 0.7*inch, y, f"${(job.get('price') or 0):.2f}")
    if job.get("description"):
        y -= 0.2*inch
        c.setFont("Helvetica-Oblique", 9)
        c.setFillColor(HexColor("#475569"))
        for line in (job["description"] or "")[:400].split("\n")[:4]:
            c.drawString(0.7*inch, y, line[:90])
            y -= 0.15*inch
        c.setFillColor(HexColor("#0F172A"))

    y = 2.0*inch
    c.setStrokeColor(HexColor("#E2E8F0"))
    c.line(0.6*inch, y + 0.4*inch, W - 0.6*inch, y + 0.4*inch)
    c.setFont("Helvetica-Bold", 14)
    c.drawRightString(W - 1.8*inch, y, "TOTAL")
    c.setFillColor(HexColor(accent))
    c.drawRightString(W - 0.7*inch, y, f"${(job.get('price') or 0):.2f}")
    c.setFillColor(HexColor("#0F172A"))

    if job.get("paid"):
        c.setFillColor(HexColor("#16A34A"))
        c.setFont("Helvetica-Bold", 22)
        c.drawString(0.7*inch, y - 0.2*inch, "PAID")
        c.setFillColor(HexColor("#0F172A"))

    c.setFont("Helvetica", 8)
    c.setFillColor(HexColor("#94A3B8"))
    c.drawString(0.6*inch, 0.6*inch, f"Thank you for your business — {company.get('name','')}")
    c.drawRightString(W - 0.6*inch, 0.6*inch, "Powered by A1 Field Pro")

    c.showPage()
    c.save()
    pdf = buf.getvalue()
    return Response(content=pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="invoice-{job["id"][:8]}.pdf"'})
