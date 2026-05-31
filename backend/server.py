"""A1 Field Pro — main FastAPI app. Routes live in routers/*; shared infra in deps.py."""
import os
import uuid
from datetime import datetime, timezone, timedelta

from fastapi import FastAPI, APIRouter
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZipMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from deps import (
    db, client, logger, now_iso,
    SUPERADMIN_EMAIL, SUPERADMIN_PASSWORD,
    init_storage,
    hash_password, verify_password,
)
from middleware import (
    RequestIDMiddleware, SecurityHeadersMiddleware,
    RateLimitMiddleware, MetricsMiddleware,
)
from routers import auth, admin, companies, customers, jobs, payments, public_routes, portal, recurring, exports, routes_opt, push, dispatch, dashboard, estimates, invoices, proposal_templates, timesheets, checklists, materials, ai, sms, branding, branches, msg_templates, subscription, tenants, api_keys, financing, analytics, integrations as integrations_router, webhooks as webhooks_router, health as health_router
from services import sync_engine
from migrations import runner as migration_runner

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
api.include_router(estimates.router)
api.include_router(invoices.router)
api.include_router(proposal_templates.router)
api.include_router(timesheets.router)
api.include_router(checklists.router)
api.include_router(materials.router)
api.include_router(ai.router)
api.include_router(sms.router)
api.include_router(branding.router)
api.include_router(branches.router)
api.include_router(msg_templates.router)
api.include_router(subscription.router)
api.include_router(tenants.router)
api.include_router(api_keys.router)
api.include_router(financing.router)
api.include_router(analytics.router)
api.include_router(integrations_router.router)
api.include_router(webhooks_router.router)
api.include_router(health_router.router)


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
    await db.estimates.create_index([("company_id", 1), ("status", 1)])
    await db.estimates.create_index("public_token", unique=True, sparse=True)
    await db.estimates.create_index([("company_id", 1), ("number", 1)])
    await db.invoices.create_index([("company_id", 1), ("status", 1)])
    await db.invoices.create_index("public_token", unique=True, sparse=True)
    await db.invoices.create_index([("company_id", 1), ("number", 1)])
    await db.proposal_templates.create_index([("company_id", 1), ("kind", 1)])
    await db.counters.create_index([("company_id", 1), ("kind", 1)], unique=True)
    await db.shifts.create_index([("user_id", 1), ("started_at", -1)])
    await db.shifts.create_index([("company_id", 1), ("started_at", -1)])
    await db.materials.create_index([("company_id", 1), ("name", 1)])
    await db.checklist_templates.create_index([("company_id", 1)])
    await db.ai_logs.create_index([("company_id", 1), ("created_at", -1)])
    await db.maintenance_suggestions.create_index([("company_id", 1), ("status", 1)])
    await db.chatbot_messages.create_index([("session_id", 1), ("created_at", 1)])
    await db.sms_log.create_index([("company_id", 1), ("created_at", -1)])
    await db.branches.create_index([("company_id", 1), ("active", 1)])
    await db.message_templates.create_index([("company_id", 1), ("key", 1)], unique=True)
    await db.message_templates.create_index([("company_id", 1), ("kind", 1)])
    await db.branding_audit.create_index([("company_id", 1), ("created_at", -1)])
    await db.companies.create_index("branding.custom_domain", unique=True, sparse=True)
    await db.companies.create_index("subscription.plan")
    await db.companies.create_index("parent_franchise_id")
    await db.franchises.create_index("name")
    await db.api_keys.create_index("hash", unique=True, sparse=True)
    await db.api_keys.create_index([("company_id", 1), ("active", 1)])
    await db.subscription_checkouts.create_index("session_id", unique=True)
    await db.finance_applications.create_index([("company_id", 1), ("status", 1)])
    await db.finance_applications.create_index("public_token", unique=True, sparse=True)
    await db.finance_applications.create_index([("company_id", 1), ("created_at", -1)])
    await db.finance_contracts.create_index([("company_id", 1), ("created_at", -1)])
    await db.finance_buydowns.create_index([("company_id", 1), ("created_at", -1)])
    await db.finance_funding_events.create_index([("company_id", 1), ("created_at", -1)])
    await db.finance_rentals.create_index([("company_id", 1), ("status", 1)])
    await db.finance_programs.create_index([("company_id", 1), ("key", 1)], unique=True)
    await db.finance_programs.create_index([("company_id", 1), ("active", 1), ("kind", 1)])
    # --- Integrations / Webhooks ---
    await db.integrations.create_index([("company_id", 1), ("provider", 1)], unique=True)
    await db.integrations.create_index("provider")
    await db.oauth_states.create_index("state", unique=True)
    await db.oauth_states.create_index("expires_at", expireAfterSeconds=0)
    await db.webhook_subscriptions.create_index([("company_id", 1), ("active", 1)])
    await db.webhook_subscriptions.create_index("id", unique=True)
    await db.webhook_deliveries.create_index([("company_id", 1), ("created_at", -1)])
    await db.webhook_events.create_index([("provider", 1), ("received_at", -1)])
    await db.integration_sync_events.create_index([("company_id", 1), ("created_at", -1)])
    # one-time migration: legacy "scheduled" status -> "scheduled_installation"
    await db.jobs.update_many(
        {"status": "scheduled"},
        {"$set": {"status": "scheduled_installation"}},
    )
    # Idempotent: ensure all existing companies have a subscription block + branding defaults.
    await db.companies.update_many(
        {"subscription": {"$exists": False}},
        {"$set": {"subscription": {"plan": "starter", "status": "active",
                                   "updated_at": now_iso()}}},
    )
    # Promote demo company to Pro so feature gates can be exercised.
    demo_email_seed = os.environ.get("ADMIN_EMAIL", "demo@a1fieldpro.com")
    demo_owner = await db.users.find_one({"email": demo_email_seed.lower()}, {"_id": 0, "company_id": 1})
    if demo_owner and demo_owner.get("company_id"):
        await db.companies.update_one(
            {"id": demo_owner["company_id"]},
            {"$set": {"subscription.plan": "pro", "subscription.status": "active"}},
        )
    await seed_demo()
    try:
        await migration_runner.run_pending()
    except Exception as e:
        logger.error(f"migrations failed: {e}")
    try:
        sync_engine.start()
    except Exception as e:
        logger.error(f"sync_engine start failed: {e}")


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
        "branding": {
            "primary_color": "#1D4ED8", "accent_color": "#DC2626",
            "secondary_color": "#0F172A",
            "app_name": "A1 Field Pro", "tagline": "Field service that just works.",
            "support_email": "support@a1fieldpro.com",
            "support_phone": "(555) 123-4567",
            "invoice_footer": "Thank you for your business — A1 HVAC N DE-GO.",
        },
        "subscription": {
            "plan": "pro", "status": "active",
            "updated_at": now,
        },
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
            "duration_min": 90, "price": 189.0, "status": "scheduled_installation",
            "paid": False, "created_at": now,
        },
        {
            "id": str(uuid.uuid4()), "company_id": company_id, "created_by": owner_id,
            "title": "Garage Door Spring Replacement",
            "customer_name": "Mike Patel", "customer_phone": "(555) 902-7788",
            "address": "88 Maple Ave, Round Rock TX", "job_type": "Garage Doors",
            "assigned_to": tech_id, "scheduled_at": (today + timedelta(hours=3)).isoformat(),
            "duration_min": 120, "price": 320.0, "status": "scheduled_installation",
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

# --- Production middleware (order matters: outermost first) ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in os.environ.get("CORS_ORIGINS", "*").split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Optional host allow-list (set ALLOWED_HOSTS="api.example.com,localhost" in prod)
_hosts = [h.strip() for h in os.environ.get("ALLOWED_HOSTS", "*").split(",") if h.strip()]
if _hosts and _hosts != ["*"]:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=_hosts)
app.add_middleware(GZipMiddleware, minimum_size=1024)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(MetricsMiddleware)
app.add_middleware(RequestIDMiddleware)


@app.on_event("shutdown")
async def shutdown_db_client():
    try:
        sync_engine.stop()
    except Exception:
        pass
    client.close()
