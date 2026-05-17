"""Jobs, dashboard, photos, signature, invoice PDF."""
import uuid
import base64
from io import BytesIO
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Response
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
        data["status"] = "scheduled"
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
    if doc.get("customer_id"):
        await db.communications.insert_one({
            "id": str(uuid.uuid4()), "company_id": user["company_id"],
            "customer_id": doc["customer_id"], "actor_id": user["id"], "actor_name": user["name"],
            "channel": "system", "direction": "internal",
            "summary": f"Job created: {doc['title']}", "body": "",
            "created_at": now_iso(),
        })
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
            updates["status"] = "scheduled"
    updates["updated_at"] = now_iso()
    result = await db.jobs.update_one(
        {"id": job_id, "company_id": user["company_id"]}, {"$set": updates}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Job not found")
    job = await db.jobs.find_one({"id": job_id}, {"_id": 0})
    new_status = updates.get("status")
    if new_status in ("scheduled", "in_progress", "completed", "cancelled"):
        await log_activity(user, f"jobs.{new_status}", "job", job_id,
                           {"title": job.get("title")})
    if new_status in ("scheduled", "in_progress", "completed", "cancelled") and job.get("customer_id"):
        verb = {"scheduled": "scheduled", "in_progress": "started", "completed": "completed", "cancelled": "cancelled"}[new_status]
        await db.communications.insert_one({
            "id": str(uuid.uuid4()), "company_id": user["company_id"],
            "customer_id": job["customer_id"], "actor_id": user["id"], "actor_name": user["name"],
            "channel": "system", "direction": "internal",
            "summary": f"Job {verb}: {job['title']}", "body": "",
            "created_at": now_iso(),
        })
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
    for j in all_jobs:
        s = j.get("scheduled_at") or ""
        if s.startswith(today):
            jobs_today += 1
        if j.get("status") == "completed":
            completed += 1
            revenue_total += float(j.get("price") or 0)
            if s.startswith(today):
                revenue_today += float(j.get("price") or 0)
        elif j.get("status") == "in_progress":
            in_progress += 1
        elif j.get("status") == "scheduled":
            scheduled += 1
        elif j.get("status") == "unscheduled":
            unscheduled += 1

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
        },
    }


@router.post("/jobs/{job_id}/photos")
async def upload_job_photo(job_id: str, file: UploadFile = File(...), user: dict = Depends(get_current_user)):
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
    }
    await db.jobs.update_one(
        {"id": job_id, "company_id": user["company_id"]},
        {"$push": {"photos": photo}},
    )
    return photo


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
