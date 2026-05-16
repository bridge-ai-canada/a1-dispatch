from dotenv import load_dotenv
from pathlib import Path
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

import os
import uuid
import logging
import bcrypt
import jwt
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Literal

from fastapi import FastAPI, APIRouter, HTTPException, Request, Response, Depends
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field, EmailStr
from emergentintegrations.payments.stripe.checkout import (
    StripeCheckout, CheckoutSessionRequest,
)

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

# -------------------- Health --------------------
@api.get("/")
async def root():
    return {"service": "A1 Field Pro API", "status": "ok"}

# -------------------- Startup --------------------
@app.on_event("startup")
async def startup():
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
