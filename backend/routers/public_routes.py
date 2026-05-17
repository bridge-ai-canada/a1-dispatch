"""Public booking widget + tenant-scoped file proxy."""
import asyncio
import uuid
from typing import Optional
import jwt
from fastapi import APIRouter, HTTPException, Request, Response, Query
from pydantic import BaseModel

from deps import (
    db, now_iso, APP_NAME, JWT_SECRET, JWT_ALGORITHM,
    get_object, send_email, email_layout, FRONTEND_URL,
)

router = APIRouter()


class BookingIn(BaseModel):
    name: str
    phone: str
    email: Optional[str] = ""
    address: str
    job_type: str = "HVAC"
    description: str = ""
    preferred_date: Optional[str] = None


@router.get("/public/companies/{company_id}")
async def public_company(company_id: str):
    company = await db.companies.find_one({"id": company_id}, {"_id": 0, "owner_id": 0})
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    return company


@router.post("/public/companies/{company_id}/bookings")
async def public_booking(company_id: str, body: BookingIn):
    company = await db.companies.find_one({"id": company_id}, {"_id": 0})
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    cust = await db.customers.find_one({"company_id": company_id, "phone": body.phone}, {"_id": 0})
    if not cust:
        cust = {
            "id": str(uuid.uuid4()),
            "company_id": company_id,
            "name": body.name, "phone": body.phone, "email": body.email,
            "address": body.address, "created_at": now_iso(),
        }
        await db.customers.insert_one(dict(cust))
    job = {
        "id": str(uuid.uuid4()),
        "company_id": company_id,
        "title": f"{body.job_type} — {body.name}",
        "description": body.description,
        "customer_id": cust["id"],
        "customer_name": body.name,
        "customer_phone": body.phone,
        "customer_email": body.email,
        "address": body.address,
        "job_type": body.job_type,
        "assigned_to": None,
        "scheduled_at": body.preferred_date,
        "duration_min": 60,
        "price": 0.0,
        "status": "unscheduled",
        "paid": False,
        "source": "booking_widget",
        "created_at": now_iso(),
    }
    await db.jobs.insert_one(dict(job))

    # Send confirmation emails: one to the customer, one to the company owner.
    pretty_when = "Soon — we'll call to confirm a time"
    if body.preferred_date:
        try:
            from datetime import datetime as _dt
            pretty_when = _dt.fromisoformat(body.preferred_date).strftime("%A, %b %d at %I:%M %p")
        except Exception:
            pretty_when = body.preferred_date

    customer_html = email_layout(
        f"Thanks for booking with {company['name']}",
        f"<p>Hi {body.name}, we've received your <strong>{body.job_type}</strong> request.</p>"
        f"<p><strong>When:</strong> {pretty_when}<br/>"
        f"<strong>Where:</strong> {body.address}<br/>"
        f"<strong>What:</strong> {body.description or 'On-site assessment'}</p>"
        f"<p>A dispatcher will reach out shortly to confirm. Reply to this email if you need to change anything.</p>",
        "Track this request", f"{FRONTEND_URL}/portal",
    )

    owner_html = email_layout(
        f"New booking — {body.name}",
        f"<p><strong>{body.name}</strong> ({body.phone}) just requested a <strong>{body.job_type}</strong> visit.</p>"
        f"<p><strong>Address:</strong> {body.address}<br/>"
        f"<strong>Preferred time:</strong> {pretty_when}<br/>"
        f"<strong>Notes:</strong> {body.description or '—'}</p>",
        "Open dispatch board", f"{FRONTEND_URL}/app/dispatch",
    )

    async def _send_async():
        if body.email:
            await send_email(body.email, f"Your booking with {company['name']}",
                             customer_html, purpose="booking.customer_confirmation")
        owner = await db.users.find_one({"id": company.get("owner_id")}, {"email": 1, "_id": 0})
        if owner and owner.get("email"):
            await send_email(owner["email"], f"New booking — {body.name}", owner_html,
                             purpose="booking.owner_alert")

    try:
        asyncio.create_task(_send_async())
    except RuntimeError:
        pass

    return {"ok": True, "job_id": job["id"], "company_name": company["name"], "job": job}


@router.get("/files/{path:path}")
async def get_file(path: str, request: Request, auth: Optional[str] = Query(None)):
    token = request.cookies.get("access_token") or auth
    if not token:
        ah = request.headers.get("Authorization", "")
        if ah.startswith("Bearer "):
            token = ah[7:]
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        company_id = payload.get("company_id")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
    expected_prefix = f"{APP_NAME}/{company_id}/"
    if not path.startswith(expected_prefix):
        raise HTTPException(status_code=403, detail="Forbidden")
    data, ctype = get_object(path)
    return Response(content=data, media_type=ctype)
