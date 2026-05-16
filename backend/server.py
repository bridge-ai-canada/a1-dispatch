from dotenv import load_dotenv
from pathlib import Path
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

import os
import uuid
import base64
import logging
import bcrypt
import jwt
import requests
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Literal

from fastapi import FastAPI, APIRouter, HTTPException, Request, Response, Depends, UploadFile, File, Query
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field, EmailStr
from emergentintegrations.payments.stripe.checkout import (
    StripeCheckout, CheckoutSessionRequest,
)

# -------------------- Storage --------------------
STORAGE_URL = "https://integrations.emergentagent.com/objstore/api/v1/storage"
EMERGENT_KEY = os.environ.get("EMERGENT_LLM_KEY", "")
APP_NAME = os.environ.get("APP_NAME", "a1fieldpro")
_storage_key: Optional[str] = None

def init_storage() -> Optional[str]:
    global _storage_key
    if _storage_key:
        return _storage_key
    if not EMERGENT_KEY:
        return None
    try:
        r = requests.post(f"{STORAGE_URL}/init", json={"emergent_key": EMERGENT_KEY}, timeout=30)
        r.raise_for_status()
        _storage_key = r.json()["storage_key"]
        return _storage_key
    except Exception as e:
        logging.error(f"Storage init failed: {e}")
        return None

def put_object(path: str, data: bytes, content_type: str) -> dict:
    key = init_storage()
    if not key:
        raise HTTPException(status_code=500, detail="Storage unavailable")
    r = requests.put(
        f"{STORAGE_URL}/objects/{path}",
        headers={"X-Storage-Key": key, "Content-Type": content_type},
        data=data, timeout=120,
    )
    r.raise_for_status()
    return r.json()

def get_object(path: str):
    key = init_storage()
    if not key:
        raise HTTPException(status_code=500, detail="Storage unavailable")
    r = requests.get(
        f"{STORAGE_URL}/objects/{path}",
        headers={"X-Storage-Key": key}, timeout=60,
    )
    r.raise_for_status()
    return r.content, r.headers.get("Content-Type", "application/octet-stream")

# -------------------- Config --------------------
mongo_url = os.environ["MONGO_URL"]
db_name = os.environ["DB_NAME"]
JWT_SECRET = os.environ["JWT_SECRET"]
STRIPE_API_KEY = os.environ.get("STRIPE_API_KEY", "sk_test_emergent")
JWT_ALGORITHM = "HS256"

client = AsyncIOMotorClient(mongo_url)
db = client[db_name]

app = FastAPI(title="A1 Field Pro API")
api = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("a1fieldpro")

# -------------------- Helpers --------------------
def hash_password(pw: str) -> str:
    return bcrypt.hashpw(pw.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

def verify_password(pw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False

def create_access_token(user_id: str, company_id: str, role: str) -> str:
    payload = {
        "sub": user_id,
        "company_id": company_id,
        "role": role,
        "type": "access",
        "exp": datetime.now(timezone.utc) + timedelta(days=7),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def set_auth_cookie(response: Response, token: str):
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=True,
        samesite="none",
        max_age=60 * 60 * 24 * 7,
        path="/",
    )

def clear_auth_cookie(response: Response):
    response.delete_cookie("access_token", path="/")

async def get_current_user(request: Request) -> dict:
    token = request.cookies.get("access_token")
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Invalid token type")
        user = await db.users.find_one({"id": payload["sub"]}, {"_id": 0, "password_hash": 0})
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

def require_role(*roles: str):
    async def checker(user: dict = Depends(get_current_user)):
        if user.get("role") not in roles:
            raise HTTPException(status_code=403, detail="Forbidden")
        return user
    return checker

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

# -------------------- Models --------------------
class RegisterIn(BaseModel):
    company_name: str
    industry: str = "HVAC"
    name: str
    email: EmailStr
    password: str

class LoginIn(BaseModel):
    email: EmailStr
    password: str

class UserOut(BaseModel):
    id: str
    company_id: str
    name: str
    email: EmailStr
    role: str
    created_at: str

class CompanyOut(BaseModel):
    id: str
    name: str
    industry: str
    created_at: str

class TeamCreateIn(BaseModel):
    name: str
    email: EmailStr
    password: str
    role: Literal["dispatcher", "technician"] = "technician"

class CustomerIn(BaseModel):
    name: str
    phone: Optional[str] = ""
    email: Optional[str] = ""
    address: Optional[str] = ""

class BrandingIn(BaseModel):
    primary_color: Optional[str] = None
    accent_color: Optional[str] = None
    logo_path: Optional[str] = None


class JobIn(BaseModel):
    title: str
    description: Optional[str] = ""
    customer_id: Optional[str] = None
    customer_name: Optional[str] = ""
    customer_phone: Optional[str] = ""
    address: Optional[str] = ""
    job_type: str = "HVAC"
    assigned_to: Optional[str] = None
    scheduled_at: Optional[str] = None  # ISO
    duration_min: int = 60
    price: float = 0.0
    status: Literal["unscheduled", "scheduled", "in_progress", "completed", "cancelled"] = "unscheduled"

class JobUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    assigned_to: Optional[str] = None
    scheduled_at: Optional[str] = None
    duration_min: Optional[int] = None
    price: Optional[float] = None
    status: Optional[str] = None
    address: Optional[str] = None
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None

class CheckoutIn(BaseModel):
    job_id: str
    origin_url: str

# -------------------- Auth Routes --------------------
@api.post("/auth/register")
async def register(body: RegisterIn, response: Response):
    email = body.email.lower().strip()
    existing = await db.users.find_one({"email": email})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    company_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    now = now_iso()
    await db.companies.insert_one({
        "id": company_id,
        "name": body.company_name,
        "industry": body.industry,
        "owner_id": user_id,
        "created_at": now,
    })
    await db.users.insert_one({
        "id": user_id,
        "company_id": company_id,
        "name": body.name,
        "email": email,
        "password_hash": hash_password(body.password),
        "role": "owner",
        "created_at": now,
    })
    token = create_access_token(user_id, company_id, "owner")
    set_auth_cookie(response, token)
    user = await db.users.find_one({"id": user_id}, {"_id": 0, "password_hash": 0})
    return {"user": user, "token": token}

@api.post("/auth/login")
async def login(body: LoginIn, response: Response):
    email = body.email.lower().strip()
    user = await db.users.find_one({"email": email})
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = create_access_token(user["id"], user["company_id"], user["role"])
    set_auth_cookie(response, token)
    user.pop("password_hash", None)
    user.pop("_id", None)
    return {"user": user, "token": token}

@api.post("/auth/logout")
async def logout(response: Response):
    clear_auth_cookie(response)
    return {"ok": True}

@api.get("/auth/me")
async def me(user: dict = Depends(get_current_user)):
    company = await db.companies.find_one({"id": user["company_id"]}, {"_id": 0})
    return {"user": user, "company": company}

# -------------------- Company / Team --------------------
@api.get("/companies/me")
async def my_company(user: dict = Depends(get_current_user)):
    company = await db.companies.find_one({"id": user["company_id"]}, {"_id": 0})
    return company

@api.patch("/companies/me")
async def update_company(body: BrandingIn, user: dict = Depends(require_role("owner"))):
    updates = {f"branding.{k}": v for k, v in body.model_dump().items() if v is not None}
    if updates:
        await db.companies.update_one({"id": user["company_id"]}, {"$set": updates})
    return await db.companies.find_one({"id": user["company_id"]}, {"_id": 0})

@api.post("/companies/me/logo")
async def upload_logo(file: UploadFile = File(...), user: dict = Depends(require_role("owner"))):
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Only images allowed")
    ext = (file.filename or "logo").rsplit(".", 1)[-1].lower() if "." in (file.filename or "") else "png"
    path = f"{APP_NAME}/{user['company_id']}/branding/logo-{uuid.uuid4()}.{ext}"
    data = await file.read()
    result = put_object(path, data, file.content_type)
    await db.companies.update_one(
        {"id": user["company_id"]}, {"$set": {"branding.logo_path": result["path"]}}
    )
    return {"path": result["path"]}

@api.get("/team")
async def list_team(user: dict = Depends(get_current_user)):
    members = await db.users.find(
        {"company_id": user["company_id"]},
        {"_id": 0, "password_hash": 0},
    ).to_list(500)
    return members

@api.post("/team")
async def create_team_member(body: TeamCreateIn, user: dict = Depends(require_role("owner", "dispatcher"))):
    email = body.email.lower().strip()
    if await db.users.find_one({"email": email}):
        raise HTTPException(status_code=400, detail="Email already in use")
    uid = str(uuid.uuid4())
    await db.users.insert_one({
        "id": uid,
        "company_id": user["company_id"],
        "name": body.name,
        "email": email,
        "password_hash": hash_password(body.password),
        "role": body.role,
        "created_at": now_iso(),
    })
    new_user = await db.users.find_one({"id": uid}, {"_id": 0, "password_hash": 0})
    return new_user

@api.delete("/team/{user_id}")
async def remove_team_member(user_id: str, user: dict = Depends(require_role("owner"))):
    if user_id == user["id"]:
        raise HTTPException(status_code=400, detail="Cannot remove yourself")
    result = await db.users.delete_one({"id": user_id, "company_id": user["company_id"]})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Member not found")
    return {"ok": True}

# -------------------- Customers --------------------
@api.get("/customers")
async def list_customers(user: dict = Depends(get_current_user)):
    items = await db.customers.find(
        {"company_id": user["company_id"]}, {"_id": 0}
    ).sort("created_at", -1).to_list(500)
    return items

@api.post("/customers")
async def create_customer(body: CustomerIn, user: dict = Depends(get_current_user)):
    doc = {
        "id": str(uuid.uuid4()),
        "company_id": user["company_id"],
        "created_at": now_iso(),
        **body.model_dump(),
    }
    await db.customers.insert_one(doc)
    doc.pop("_id", None)
    return doc

# -------------------- Jobs --------------------
@api.get("/jobs")
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

@api.post("/jobs")
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
    return doc

@api.get("/jobs/{job_id}")
async def get_job(job_id: str, user: dict = Depends(get_current_user)):
    job = await db.jobs.find_one({"id": job_id, "company_id": user["company_id"]}, {"_id": 0})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job

@api.patch("/jobs/{job_id}")
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
    return job

@api.delete("/jobs/{job_id}")
async def delete_job(job_id: str, user: dict = Depends(require_role("owner", "dispatcher"))):
    result = await db.jobs.delete_one({"id": job_id, "company_id": user["company_id"]})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"ok": True}

# -------------------- Dashboard --------------------
@api.get("/dashboard/stats")
async def dashboard_stats(user: dict = Depends(get_current_user)):
    company_id = user["company_id"]
    today = datetime.now(timezone.utc).date().isoformat()
    all_jobs = await db.jobs.find({"company_id": company_id}, {"_id": 0}).to_list(2000)
    technicians = await db.users.count_documents({"company_id": company_id, "role": "technician"})

    jobs_today = 0
    revenue_today = 0.0
    revenue_total = 0.0
    completed = 0
    in_progress = 0
    scheduled = 0
    unscheduled = 0
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
            "total": total,
            "completed": completed,
            "in_progress": in_progress,
            "scheduled": scheduled,
            "unscheduled": unscheduled,
        },
    }

# -------------------- Payments (Stripe) --------------------
@api.post("/payments/checkout")
async def create_checkout(body: CheckoutIn, request: Request, user: dict = Depends(get_current_user)):
    job = await db.jobs.find_one({"id": body.job_id, "company_id": user["company_id"]}, {"_id": 0})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    amount = float(job.get("price") or 0)
    if amount <= 0:
        raise HTTPException(status_code=400, detail="Job has no price to charge")
    if job.get("paid"):
        raise HTTPException(status_code=400, detail="Job already paid")

    host_url = str(request.base_url)
    webhook_url = f"{host_url}api/webhook/stripe"
    stripe_checkout = StripeCheckout(api_key=STRIPE_API_KEY, webhook_url=webhook_url)

    success_url = f"{body.origin_url}/payment/result?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{body.origin_url}/app/jobs"
    req = CheckoutSessionRequest(
        amount=amount,
        currency="usd",
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={
            "job_id": body.job_id,
            "company_id": user["company_id"],
            "user_id": user["id"],
        },
    )
    session = await stripe_checkout.create_checkout_session(req)
    await db.payment_transactions.insert_one({
        "id": str(uuid.uuid4()),
        "session_id": session.session_id,
        "job_id": body.job_id,
        "company_id": user["company_id"],
        "user_id": user["id"],
        "amount": amount,
        "currency": "usd",
        "payment_status": "initiated",
        "status": "open",
        "metadata": {"job_id": body.job_id},
        "created_at": now_iso(),
    })
    return {"url": session.url, "session_id": session.session_id}

@api.get("/payments/status/{session_id}")
async def payment_status(session_id: str, request: Request, user: dict = Depends(get_current_user)):
    tx = await db.payment_transactions.find_one(
        {"session_id": session_id, "company_id": user["company_id"]}, {"_id": 0}
    )
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")
    if tx.get("payment_status") == "paid":
        return tx

    host_url = str(request.base_url)
    webhook_url = f"{host_url}api/webhook/stripe"
    stripe_checkout = StripeCheckout(api_key=STRIPE_API_KEY, webhook_url=webhook_url)
    status = await stripe_checkout.get_checkout_status(session_id)
    updates = {
        "payment_status": status.payment_status,
        "status": status.status,
        "updated_at": now_iso(),
    }
    await db.payment_transactions.update_one({"session_id": session_id}, {"$set": updates})
    if status.payment_status == "paid" and not tx.get("processed"):
        await db.jobs.update_one(
            {"id": tx["job_id"], "company_id": user["company_id"]},
            {"$set": {"paid": True, "status": "completed", "paid_at": now_iso()}},
        )
        await db.payment_transactions.update_one(
            {"session_id": session_id}, {"$set": {"processed": True}}
        )
    tx = await db.payment_transactions.find_one({"session_id": session_id}, {"_id": 0})
    return tx

@api.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    body = await request.body()
    sig = request.headers.get("Stripe-Signature", "")
    host_url = str(request.base_url)
    webhook_url = f"{host_url}api/webhook/stripe"
    stripe_checkout = StripeCheckout(api_key=STRIPE_API_KEY, webhook_url=webhook_url)
    try:
        evt = await stripe_checkout.handle_webhook(body, sig)
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        raise HTTPException(status_code=400, detail="Webhook handling failed")
    if evt.session_id:
        await db.payment_transactions.update_one(
            {"session_id": evt.session_id},
            {"$set": {"payment_status": evt.payment_status, "updated_at": now_iso()}},
        )
        if evt.payment_status == "paid":
            tx = await db.payment_transactions.find_one({"session_id": evt.session_id})
            if tx and not tx.get("processed"):
                await db.jobs.update_one(
                    {"id": tx["job_id"]},
                    {"$set": {"paid": True, "status": "completed", "paid_at": now_iso()}},
                )
                await db.payment_transactions.update_one(
                    {"session_id": evt.session_id}, {"$set": {"processed": True}}
                )
    return {"received": True}

# -------------------- Files / Photos / Signatures --------------------
class SignatureIn(BaseModel):
    image_base64: str  # data URL or raw base64
    signer_name: Optional[str] = ""

@api.post("/jobs/{job_id}/photos")
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

@api.delete("/jobs/{job_id}/photos/{photo_id}")
async def delete_job_photo(job_id: str, photo_id: str, user: dict = Depends(get_current_user)):
    result = await db.jobs.update_one(
        {"id": job_id, "company_id": user["company_id"]},
        {"$pull": {"photos": {"id": photo_id}}},
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Photo not found")
    return {"ok": True}

@api.post("/jobs/{job_id}/signature")
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

@api.get("/files/{path:path}")
async def get_file(path: str, request: Request, auth: Optional[str] = Query(None)):
    # Accept token from cookie, Authorization header, or ?auth=
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

# -------------------- Public Booking Widget --------------------
class BookingIn(BaseModel):
    name: str
    phone: str
    email: Optional[str] = ""
    address: str
    job_type: str = "HVAC"
    description: str = ""
    preferred_date: Optional[str] = None  # ISO

@api.get("/public/companies/{company_id}")
async def public_company(company_id: str):
    company = await db.companies.find_one({"id": company_id}, {"_id": 0, "owner_id": 0})
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    return company

@api.post("/public/companies/{company_id}/bookings")
async def public_booking(company_id: str, body: BookingIn):
    company = await db.companies.find_one({"id": company_id}, {"_id": 0})
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    # Create or reuse customer
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
    return {"ok": True, "job_id": job["id"], "company_name": company["name"]}

@api.get("/jobs/{job_id}/invoice.pdf")
async def invoice_pdf(job_id: str, user: dict = Depends(get_current_user)):
    from io import BytesIO
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

    # Header bar
    c.setFillColor(HexColor(primary))
    c.rect(0, H - 0.9*inch, W, 0.9*inch, fill=1, stroke=0)
    c.setFillColor(HexColor("#FFFFFF"))
    c.setFont("Helvetica-Bold", 22)
    c.drawString(0.6*inch, H - 0.55*inch, company.get("name", "A1 Field Pro"))
    c.setFont("Helvetica", 10)
    c.drawString(0.6*inch, H - 0.75*inch, f"{company.get('industry','')} · INVOICE")

    # Invoice meta
    c.setFillColor(HexColor("#0F172A"))
    c.setFont("Helvetica-Bold", 14)
    c.drawString(0.6*inch, H - 1.4*inch, "INVOICE")
    c.setFont("Helvetica", 10)
    c.drawString(0.6*inch, H - 1.6*inch, f"Job #: {job['id'][:8].upper()}")
    c.drawString(0.6*inch, H - 1.75*inch, f"Date: {datetime.now(timezone.utc).strftime('%b %d, %Y')}")

    # Bill to
    c.setFont("Helvetica-Bold", 11)
    c.drawString(0.6*inch, H - 2.2*inch, "BILL TO")
    c.setFont("Helvetica", 10)
    c.drawString(0.6*inch, H - 2.4*inch, job.get("customer_name") or "Customer")
    if job.get("address"):  c.drawString(0.6*inch, H - 2.55*inch, job["address"])
    if job.get("customer_phone"): c.drawString(0.6*inch, H - 2.70*inch, job["customer_phone"])

    # Line item table header
    y = H - 3.4*inch
    c.setFillColor(HexColor("#F1F5F9"))
    c.rect(0.6*inch, y - 0.05*inch, W - 1.2*inch, 0.3*inch, fill=1, stroke=0)
    c.setFillColor(HexColor("#0F172A"))
    c.setFont("Helvetica-Bold", 10)
    c.drawString(0.7*inch, y + 0.05*inch, "DESCRIPTION")
    c.drawRightString(W - 0.7*inch, y + 0.05*inch, "AMOUNT")

    # Line item
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

    # Total
    y = 2.0*inch
    c.setStrokeColor(HexColor("#E2E8F0"))
    c.line(0.6*inch, y + 0.4*inch, W - 0.6*inch, y + 0.4*inch)
    c.setFont("Helvetica-Bold", 14)
    c.drawRightString(W - 1.8*inch, y, "TOTAL")
    c.setFillColor(HexColor(accent))
    c.drawRightString(W - 0.7*inch, y, f"${(job.get('price') or 0):.2f}")
    c.setFillColor(HexColor("#0F172A"))

    # Status stamp
    if job.get("paid"):
        c.setFillColor(HexColor("#16A34A"))
        c.setFont("Helvetica-Bold", 22)
        c.drawString(0.7*inch, y - 0.2*inch, "PAID")
        c.setFillColor(HexColor("#0F172A"))

    # Footer
    c.setFont("Helvetica", 8)
    c.setFillColor(HexColor("#94A3B8"))
    c.drawString(0.6*inch, 0.6*inch, f"Thank you for your business — {company.get('name','')}")
    c.drawRightString(W - 0.6*inch, 0.6*inch, "Powered by A1 Field Pro")

    c.showPage()
    c.save()
    pdf = buf.getvalue()
    return Response(content=pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="invoice-{job["id"][:8]}.pdf"'})

# -------------------- Health --------------------
@api.get("/")
async def root():
    return {"service": "A1 Field Pro API", "status": "ok"}

# -------------------- Startup --------------------
@app.on_event("startup")
async def startup():
    init_storage()
    await db.users.create_index("email", unique=True)
    await db.users.create_index("company_id")
    await db.jobs.create_index([("company_id", 1), ("status", 1)])
    await db.jobs.create_index([("company_id", 1), ("assigned_to", 1)])
    await db.customers.create_index("company_id")
    await db.payment_transactions.create_index("session_id", unique=True)
    await seed_demo()

async def seed_demo():
    """Seed a demo company + owner + technician + sample data for quick tour."""
    demo_email = os.environ.get("ADMIN_EMAIL", "demo@a1fieldpro.com")
    demo_password = os.environ.get("ADMIN_PASSWORD", "Demo1234!")
    existing = await db.users.find_one({"email": demo_email})
    if existing:
        # Update password to match env (idempotent)
        if not verify_password(demo_password, existing["password_hash"]):
            await db.users.update_one(
                {"email": demo_email}, {"$set": {"password_hash": hash_password(demo_password)}}
            )
        return

    company_id = str(uuid.uuid4())
    owner_id = str(uuid.uuid4())
    tech_id = str(uuid.uuid4())
    disp_id = str(uuid.uuid4())
    now = now_iso()
    await db.companies.insert_one({
        "id": company_id, "name": "A1 HVAC N DE-GO", "industry": "HVAC",
        "owner_id": owner_id, "created_at": now,
    })
    await db.users.insert_many([
        {"id": owner_id, "company_id": company_id, "name": "Demo Owner",
         "email": demo_email, "password_hash": hash_password(demo_password),
         "role": "owner", "created_at": now},
        {"id": disp_id, "company_id": company_id, "name": "Dana Dispatcher",
         "email": "dispatcher@a1fieldpro.com", "password_hash": hash_password("Demo1234!"),
         "role": "dispatcher", "created_at": now},
        {"id": tech_id, "company_id": company_id, "name": "Tom Technician",
         "email": "tech@a1fieldpro.com", "password_hash": hash_password("Demo1234!"),
         "role": "technician", "created_at": now},
    ])
    today = datetime.now(timezone.utc).replace(hour=14, minute=0, second=0, microsecond=0)
    sample_jobs = [
        {
            "id": str(uuid.uuid4()), "company_id": company_id, "created_by": owner_id,
            "title": "AC Unit Tune-up", "description": "Annual maintenance",
            "customer_name": "Sarah Johnson", "customer_phone": "(555) 234-1122",
            "address": "1421 Oak St, Austin TX", "job_type": "HVAC",
            "assigned_to": tech_id, "scheduled_at": today.isoformat(),
            "duration_min": 90, "price": 189.0, "status": "scheduled",
            "paid": False, "created_at": now,
        },
        {
            "id": str(uuid.uuid4()), "company_id": company_id, "created_by": owner_id,
            "title": "Garage Door Spring Replacement",
            "customer_name": "Mike Patel", "customer_phone": "(555) 902-7788",
            "address": "88 Maple Ave, Round Rock TX", "job_type": "Garage Doors",
            "assigned_to": tech_id, "scheduled_at": (today + timedelta(hours=3)).isoformat(),
            "duration_min": 120, "price": 320.0, "status": "scheduled",
            "paid": False, "created_at": now,
        },
        {
            "id": str(uuid.uuid4()), "company_id": company_id, "created_by": owner_id,
            "title": "Water Heater Install",
            "customer_name": "Linda Tran", "customer_phone": "(555) 311-4501",
            "address": "300 Cedar Ln, Austin TX", "job_type": "Plumbing",
            "assigned_to": None, "scheduled_at": None,
            "duration_min": 180, "price": 1450.0, "status": "unscheduled",
            "paid": False, "created_at": now,
        },
        {
            "id": str(uuid.uuid4()), "company_id": company_id, "created_by": owner_id,
            "title": "Panel Upgrade",
            "customer_name": "Greg Hopkins", "customer_phone": "(555) 711-9912",
            "address": "21 Birch Rd, Cedar Park TX", "job_type": "Electrical",
            "assigned_to": tech_id, "scheduled_at": (today - timedelta(days=1)).isoformat(),
            "duration_min": 240, "price": 2200.0, "status": "completed",
            "paid": True, "created_at": now,
        },
    ]
    await db.jobs.insert_many(sample_jobs)
    logger.info("Seeded demo company and sample jobs")

app.include_router(api)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in os.environ.get("CORS_ORIGINS", "*").split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
