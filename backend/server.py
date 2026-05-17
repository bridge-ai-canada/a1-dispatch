"""A1 Field Pro — main FastAPI app. Routes live in routers/*; shared infra in deps.py."""
import os
import uuid
from datetime import datetime, timezone, timedelta

from fastapi import FastAPI, APIRouter
from starlette.middleware.cors import CORSMiddleware

from deps import (
    db, client, logger, now_iso,
    SUPERADMIN_EMAIL, SUPERADMIN_PASSWORD,
    init_storage,
    hash_password, verify_password,
)
from routers import auth, admin, companies, customers, jobs, payments, public_routes, portal, recurring, exports, routes_opt, push, dispatch, dashboard

app = FastAPI(title="A1 Field Pro API")
api = APIRouter(prefix="/api")

api.include_router(auth.router)
api.include_router(admin.router)
api.include_router(companies.router)
api.include_router(customers.router)
api.include_router(jobs.router)
api.include_router(payments.router)
api.include_router(public_routes.router)
api.include_router(portal.router)
api.include_router(recurring.router)
api.include_router(exports.router)
api.include_router(routes_opt.router)
api.include_router(push.router)
api.include_router(dispatch.router)
api.include_router(dashboard.router)


@api.get("/")
async def root():
    return {"service": "A1 Field Pro API", "status": "ok"}


@app.on_event("startup")
async def startup():
    init_storage()
    await db.users.create_index("email", unique=True)
    await db.users.create_index("company_id")
    await db.jobs.create_index([("company_id", 1), ("status", 1)])
    await db.jobs.create_index([("company_id", 1), ("assigned_to", 1)])
    await db.jobs.create_index("customer_email")
    await db.customers.create_index("company_id")
    await db.payment_transactions.create_index("session_id", unique=True)
    await db.activity.create_index([("company_id", 1), ("created_at", -1)])
    await db.sessions.create_index("user_id")
    await db.properties.create_index([("company_id", 1), ("customer_id", 1)])
    await db.equipment.create_index([("company_id", 1), ("customer_id", 1)])
    await db.communications.create_index([("company_id", 1), ("customer_id", 1), ("created_at", -1)])
    await db.customer_files.create_index([("company_id", 1), ("customer_id", 1)])
    await db.recurring_jobs.create_index([("company_id", 1), ("active", 1), ("next_run_at", 1)])
    await db.push_subscriptions.create_index("user_id")
    await db.push_subscriptions.create_index("endpoint", unique=True)
    await db.geocode_cache.create_index("address", unique=True)
    await seed_demo()


async def seed_demo():
    """Seed super_admin + demo company + sample data."""
    if SUPERADMIN_EMAIL and SUPERADMIN_PASSWORD:
        sa = await db.users.find_one({"email": SUPERADMIN_EMAIL.lower()})
        if not sa:
            await db.users.insert_one({
                "id": str(uuid.uuid4()),
                "company_id": None,
                "name": "Platform Super Admin",
                "email": SUPERADMIN_EMAIL.lower(),
                "password_hash": hash_password(SUPERADMIN_PASSWORD),
                "role": "super_admin",
                "active": True,
                "mfa_enabled": False,
                "mfa_secret": None,
                "email_verified": True,
                "created_at": now_iso(),
            })
        elif not verify_password(SUPERADMIN_PASSWORD, sa["password_hash"]):
            await db.users.update_one(
                {"email": SUPERADMIN_EMAIL.lower()},
                {"$set": {"password_hash": hash_password(SUPERADMIN_PASSWORD)}},
            )

    demo_email = os.environ.get("ADMIN_EMAIL", "demo@a1fieldpro.com")
    demo_password = os.environ.get("ADMIN_PASSWORD", "Demo1234!")
    existing = await db.users.find_one({"email": demo_email})
    if existing:
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
         "role": "owner", "active": True, "mfa_enabled": False, "mfa_secret": None,
         "email_verified": True, "created_at": now},
        {"id": disp_id, "company_id": company_id, "name": "Dana Dispatcher",
         "email": "dispatcher@a1fieldpro.com", "password_hash": hash_password("Demo1234!"),
         "role": "dispatcher", "active": True, "mfa_enabled": False, "mfa_secret": None,
         "email_verified": True, "created_at": now},
        {"id": tech_id, "company_id": company_id, "name": "Tom Technician",
         "email": "tech@a1fieldpro.com", "password_hash": hash_password("Demo1234!"),
         "role": "technician", "active": True, "mfa_enabled": False, "mfa_secret": None,
         "email_verified": True, "created_at": now},
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
