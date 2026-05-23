"""Fresh Cash Finance — application/offer/contract/rental endpoints.

Routes:
- Customer (public, token-gated): apply, view offer, e-sign, view amortization
- Contractor (auth): dashboard, list applications, apply buy-down, log funding event,
  rental equipment financing
- Admin (super_admin / owner): platform metrics, override decisions
- Estimate integration: linking financing offer → estimate
"""
import secrets
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, Literal, List
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field, EmailStr

from deps import db, now_iso, get_current_user, require_role, log_activity
import fresh_cash_service as fc

router = APIRouter()


# -------------------- Models --------------------
class CalcIn(BaseModel):
    amount: float = Field(gt=0)
    apr: float = Field(ge=0)
    term_months: int = Field(ge=1, le=120)


class ApplicationCreateIn(BaseModel):
    # Contractor or estimate-flow initiates an application for a customer
    customer_name: str
    customer_email: Optional[EmailStr] = None
    customer_phone: Optional[str] = None
    address: Optional[str] = ""
    amount: float = Field(gt=0)
    term_months: int = Field(ge=6, le=84, default=36)
    estimate_id: Optional[str] = None
    invoice_id: Optional[str] = None
    branch_id: Optional[str] = None
    notes: Optional[str] = ""


class ApplicantDetailsIn(BaseModel):
    # Customer fills these in via the public portal — drives the soft-pull
    first_name: str
    last_name: str
    email: EmailStr
    phone: str
    dob: str  # ISO date string
    ssn4: str  # last-4 only
    fico_bucket: Literal["excellent", "good", "fair", "poor", "subprime", "unknown"] = "unknown"
    monthly_income: float = Field(ge=0)
    monthly_obligations: float = Field(ge=0)
    employment_status: Literal["full_time", "part_time", "self_employed", "retired", "unemployed"] = "full_time"
    consent_soft_pull: bool


class SignIn(BaseModel):
    signer_name: str
    signature_base64: str


class BuydownIn(BaseModel):
    application_id: str
    fee_pct: float = Field(ge=0, le=8)


class FundingEventIn(BaseModel):
    application_id: str
    amount: float = Field(gt=0)
    kind: Literal["disbursement", "fee", "buydown_charge", "refund"] = "disbursement"
    memo: Optional[str] = ""


class RentalIn(BaseModel):
    customer_name: str
    customer_email: Optional[EmailStr] = None
    equipment_name: str
    equipment_value: float = Field(gt=0)
    weekly_payment: Optional[float] = None
    monthly_payment: Optional[float] = None
    term_weeks: int = Field(ge=4, le=520, default=52)
    deposit: float = Field(ge=0, default=0)
    branch_id: Optional[str] = None


class DecisionOverrideIn(BaseModel):
    decision: Literal["approved", "counter_offer", "manual_review", "declined"]
    apr: Optional[float] = None
    term_months: Optional[int] = None
    reason: Optional[str] = ""


def _public_token() -> str:
    return secrets.token_urlsafe(24)


async def _maybe_link_estimate(application: dict):
    """If application is tied to an estimate, write the application id back to it."""
    eid = application.get("estimate_id")
    if not eid:
        return
    await db.estimates.update_one(
        {"id": eid, "company_id": application["company_id"]},
        {"$set": {"financing_application_id": application["id"]}},
    )


# -------------------- Calculator (auth, used by builders) --------------------
@router.post("/financing/calculate")
async def financing_calculate(body: CalcIn, user: dict = Depends(get_current_user)):
    pmt = fc.monthly_payment(body.amount, body.apr, body.term_months)
    schedule = fc.amortization_schedule(body.amount, body.apr, body.term_months)
    return {
        "amount": body.amount,
        "apr": body.apr,
        "term_months": body.term_months,
        "monthly_payment": pmt,
        "total_finance_charge": fc.total_finance_charge(body.amount, body.apr, body.term_months),
        "schedule": schedule,
    }


@router.get("/financing/ladder")
async def financing_ladder(user: dict = Depends(get_current_user)):
    """Return APR ladder for UI presentation."""
    return [
        {"label": label, "score_min": lo, "score_max": hi, "base_apr": apr, "max_term": max_term}
        for lo, hi, apr, max_term, label in fc.APR_LADDER
    ]


# -------------------- Contractor: create application --------------------
@router.post("/financing/applications")
async def create_application(
    body: ApplicationCreateIn,
    user: dict = Depends(require_role("owner", "dispatcher", "office_manager", "sales_rep", "csr", "super_admin")),
):
    aid = str(uuid.uuid4())
    token = _public_token()
    doc = {
        "id": aid,
        "company_id": user["company_id"],
        "created_by": user["id"],
        "branch_id": body.branch_id,
        "customer_name": body.customer_name,
        "customer_email": body.customer_email,
        "customer_phone": body.customer_phone,
        "address": body.address,
        "amount": float(body.amount),
        "term_months": int(body.term_months),
        "estimate_id": body.estimate_id,
        "invoice_id": body.invoice_id,
        "status": "started",            # started → submitted → decisioned → signed → funded
        "decision": None,
        "score": None,
        "bureau": None,
        "tier": None,
        "offer": None,
        "applicant": None,
        "signed": None,
        "public_token": token,
        "notes": body.notes,
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    await db.finance_applications.insert_one(doc)
    await _maybe_link_estimate(doc)
    await log_activity(user, "finance.application_started",
                       meta={"application_id": aid, "amount": body.amount})
    return {k: v for k, v in doc.items() if k != "_id"}


@router.get("/financing/applications")
async def list_applications(
    user: dict = Depends(get_current_user),
    status: Optional[str] = None,
    limit: int = 100,
):
    q = {"company_id": user["company_id"]}
    if status:
        q["status"] = status
    items = await db.finance_applications.find(
        q, {"_id": 0, "public_token": 0, "applicant.ssn4": 0},
    ).sort("created_at", -1).to_list(min(limit, 500))
    return items


@router.get("/financing/applications/{app_id}")
async def get_application(app_id: str, user: dict = Depends(get_current_user)):
    app = await db.finance_applications.find_one(
        {"id": app_id, "company_id": user["company_id"]},
        {"_id": 0, "public_token": 0, "applicant.ssn4": 0},
    )
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    return app


class JobFinanceIn(BaseModel):
    job_id: str
    amount: Optional[float] = None  # defaults to job.price
    term_months: int = Field(ge=6, le=84, default=36)
    send_sms: bool = False
    origin_url: Optional[str] = None  # used to build the customer link in SMS


@router.post("/financing/from-job")
async def create_from_job(
    body: JobFinanceIn,
    user: dict = Depends(require_role("owner", "dispatcher", "office_manager", "sales_rep", "csr", "technician", "super_admin")),
):
    """Create a financing application from a Job. Designed for techs in the field —
    optionally text the link to the customer right away. Idempotent per job."""
    job = await db.jobs.find_one(
        {"id": body.job_id, "company_id": user["company_id"]}, {"_id": 0},
    )
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    amount = float(body.amount if body.amount is not None else (job.get("price") or 0))
    if amount < fc.MIN_AMOUNT:
        raise HTTPException(status_code=400, detail=f"Amount too small to finance (min ${fc.MIN_AMOUNT})")

    # Idempotent: if a finance app already exists for this job, reuse it
    existing = await db.finance_applications.find_one(
        {"company_id": user["company_id"], "job_id": body.job_id}, {"_id": 0},
    )
    if existing:
        doc = existing
    else:
        aid = str(uuid.uuid4())
        token = _public_token()
        doc = {
            "id": aid,
            "company_id": user["company_id"],
            "created_by": user["id"],
            "branch_id": job.get("branch_id"),
            "customer_name": job.get("customer_name", ""),
            "customer_email": job.get("customer_email"),
            "customer_phone": job.get("customer_phone"),
            "address": job.get("address", ""),
            "amount": amount,
            "term_months": int(body.term_months),
            "estimate_id": None,
            "invoice_id": None,
            "job_id": body.job_id,
            "status": "started", "decision": None, "score": None, "bureau": None,
            "tier": None, "offer": None, "applicant": None, "signed": None,
            "public_token": token,
            "notes": f"Created from job {job.get('title') or job['id'][:8]}",
            "created_at": now_iso(), "updated_at": now_iso(),
            "source": "job",
        }
        await db.finance_applications.insert_one(doc)
        # Link back to the job
        await db.jobs.update_one(
            {"id": body.job_id, "company_id": user["company_id"]},
            {"$set": {"financing_application_id": aid}},
        )
        await log_activity(user, "finance.from_job",
                           meta={"job_id": body.job_id, "application_id": aid, "amount": amount})

    # Send SMS if requested and we have a phone + Twilio configured
    sms_result = None
    if body.send_sms:
        import sms_service
        from urllib.parse import urlparse
        phone = doc.get("customer_phone")
        if not phone:
            sms_result = {"ok": False, "error": "no_customer_phone"}
        elif not sms_service.is_enabled():
            sms_result = {"ok": False, "error": "twilio_not_configured"}
        else:
            # Build the public link from origin_url (frontend) or FRONTEND_URL env fallback
            from deps import FRONTEND_URL
            base = (body.origin_url or FRONTEND_URL or "").rstrip("/")
            if not base:
                sms_result = {"ok": False, "error": "no_origin_url"}
            else:
                apply_url = f"{base}/finance/{doc['public_token']}"
                company = await db.companies.find_one(
                    {"id": user["company_id"]}, {"_id": 0, "name": 1, "branding": 1},
                ) or {}
                brand = company.get("branding") or {}
                app_name = brand.get("app_name") or company.get("name") or "We"
                text = (
                    f"{app_name}: Pay over time for your service "
                    f"(${int(amount)})! Apply in 60 seconds (soft credit check only): {apply_url}"
                )
                import asyncio
                sms_result = await asyncio.to_thread(sms_service.send_sms, phone, text)
                await db.sms_log.insert_one({
                    "company_id": user["company_id"],
                    "sent_by": user["id"],
                    "to": phone,
                    "body": text[:500],
                    "job_id": body.job_id,
                    "customer_id": job.get("customer_id"),
                    "ok": sms_result.get("ok", False),
                    "sid": sms_result.get("sid"),
                    "error": sms_result.get("error"),
                    "kind": "finance_offer",
                    "created_at": now_iso(),
                })

    return {
        "application_id": doc["id"],
        "public_token": doc["public_token"],
        "amount": doc["amount"],
        "term_months": doc["term_months"],
        "sms_result": sms_result,
    }


# -------------------- Public customer-portal endpoints --------------------
@router.post("/public/estimates/{estimate_token}/finance")
async def public_finance_from_estimate(estimate_token: str, payload: dict = None):
    """Customer-initiated: from a public estimate, create a financing application
    using the estimate's customer + selected tier total, then return the public finance token."""
    est = await db.estimates.find_one({"public_token": estimate_token}, {"_id": 0})
    if not est:
        raise HTTPException(status_code=404, detail="Estimate not found")
    selected_tier_key = (payload or {}).get("selected_tier") or "good"
    tiers = est.get("tiers") or []
    tier = next((t for t in tiers if t.get("key") == selected_tier_key), tiers[0] if tiers else None)
    if not tier:
        raise HTTPException(status_code=400, detail="Estimate has no tiers")
    items_total = sum(float(i.get("qty", 0)) * float(i.get("unit_price", 0)) for i in tier.get("line_items") or [])
    amount = max(0.0, round(items_total, 2))
    if amount < fc.MIN_AMOUNT:
        raise HTTPException(status_code=400, detail=f"Amount too small to finance (min ${fc.MIN_AMOUNT})")
    # Reuse the existing application if already created for this estimate
    existing = await db.finance_applications.find_one(
        {"estimate_id": est["id"]}, {"_id": 0},
    )
    if existing:
        return {"public_token": existing["public_token"], "application_id": existing["id"], "amount": existing["amount"]}
    aid = str(uuid.uuid4())
    token = _public_token()
    doc = {
        "id": aid,
        "company_id": est["company_id"],
        "created_by": None,                # customer-initiated
        "branch_id": None,
        "customer_name": est.get("customer_name") or "",
        "customer_email": est.get("customer_email") or "",
        "customer_phone": est.get("customer_phone") or "",
        "address": est.get("address") or "",
        "amount": amount,
        "term_months": int((est.get("financing") or {}).get("term_months") or 36),
        "estimate_id": est["id"],
        "invoice_id": None,
        "status": "started", "decision": None, "score": None, "bureau": None,
        "tier": None, "offer": None, "applicant": None, "signed": None,
        "public_token": token,
        "notes": f"Auto-created from estimate {est.get('number') or est.get('id')[:8]}",
        "created_at": now_iso(), "updated_at": now_iso(),
        "source": "public_estimate",
    }
    await db.finance_applications.insert_one(doc)
    await db.estimates.update_one(
        {"id": est["id"]},
        {"$set": {"financing_application_id": aid}},
    )
    return {"public_token": token, "application_id": aid, "amount": amount}


@router.get("/public/financing/{public_token}")
async def public_view_application(public_token: str):
    """Customer view via shared token — no auth. Strips sensitive fields."""
    app = await db.finance_applications.find_one(
        {"public_token": public_token},
        {"_id": 0, "applicant.ssn4": 0, "applicant.dob": 0,
         "score": 0, "bureau": 0, "notes": 0, "created_by": 0},
    )
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    company = await db.companies.find_one(
        {"id": app["company_id"]}, {"_id": 0, "name": 1, "branding": 1},
    ) or {}
    brand = company.get("branding") or {}
    return {
        "application": app,
        "company": {
            "id": app["company_id"],
            "name": (brand.get("app_name") or company.get("name") or ""),
            "primary_color": brand.get("primary_color") or "#1D4ED8",
            "accent_color": brand.get("accent_color") or "#DC2626",
            "logo_url": f"/api/public/branding/asset/{app['company_id']}/logo" if brand.get("logo_path") else None,
            "support_phone": brand.get("support_phone"),
            "support_email": brand.get("support_email"),
        },
    }


@router.post("/public/financing/{public_token}/submit")
async def public_submit_application(public_token: str, body: ApplicantDetailsIn):
    """Customer fills in applicant details and triggers a soft-pull + decision."""
    if not body.consent_soft_pull:
        raise HTTPException(status_code=400, detail="Soft-pull consent is required")
    app = await db.finance_applications.find_one({"public_token": public_token}, {"_id": 0})
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    if app["status"] in ("funded", "signed", "declined"):
        raise HTTPException(status_code=400, detail=f"Application already {app['status']}")

    applicant = body.model_dump()
    decision = await fc.decide({
        "amount": app["amount"],
        "term_months": app["term_months"],
        **applicant,
    })
    await db.finance_applications.update_one(
        {"id": app["id"]},
        {"$set": {
            "applicant": applicant,
            "status": "decisioned",
            "decision": decision["decision"],
            "decision_reason": decision.get("reason"),
            "score": decision.get("score"),
            "bureau": decision.get("bureau"),
            "tier": decision.get("tier"),
            "offer": decision.get("offer"),
            "decisioned_at": now_iso(),
            "updated_at": now_iso(),
        }},
    )
    # Return a sanitized response — no raw bureau internals to the customer
    return {
        "decision": decision["decision"],
        "reason": decision.get("reason"),
        "offer": decision.get("offer"),
        "tier_label": (decision.get("tier") or {}).get("label"),
    }


@router.post("/public/financing/{public_token}/sign")
async def public_sign_application(public_token: str, body: SignIn):
    app = await db.finance_applications.find_one({"public_token": public_token}, {"_id": 0})
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    if app.get("decision") not in ("approved", "counter_offer"):
        raise HTTPException(status_code=400, detail="No approved offer to sign")
    if app.get("status") in ("signed", "funded"):
        raise HTTPException(status_code=400, detail="Already signed")
    await db.finance_applications.update_one(
        {"id": app["id"]},
        {"$set": {
            "status": "signed",
            "signed": {
                "signer_name": body.signer_name,
                "signature_base64": body.signature_base64,
                "signed_at": now_iso(),
            },
            "updated_at": now_iso(),
        }},
    )
    # Create a contract record (immutable snapshot)
    contract_id = str(uuid.uuid4())
    await db.finance_contracts.insert_one({
        "id": contract_id,
        "application_id": app["id"],
        "company_id": app["company_id"],
        "customer_name": app["customer_name"],
        "amount": (app.get("offer") or {}).get("amount") or app["amount"],
        "apr": (app.get("offer") or {}).get("apr"),
        "term_months": (app.get("offer") or {}).get("term_months"),
        "monthly_payment": (app.get("offer") or {}).get("monthly_payment"),
        "signer_name": body.signer_name,
        "signed_at": now_iso(),
        "created_at": now_iso(),
        "status": "signed",
    })
    return {"ok": True, "status": "signed", "contract_id": contract_id}


# -------------------- Contractor: buy-down --------------------
@router.post("/financing/buydown/quote")
async def buydown_quote(body: BuydownIn, user: dict = Depends(get_current_user)):
    app = await db.finance_applications.find_one(
        {"id": body.application_id, "company_id": user["company_id"]}, {"_id": 0},
    )
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    offer = app.get("offer") or {}
    if not offer.get("apr"):
        raise HTTPException(status_code=400, detail="No offer to buy down")
    return fc.buydown_quote(offer["amount"], offer["apr"], offer["term_months"], body.fee_pct)


@router.post("/financing/buydown")
async def apply_buydown(
    body: BuydownIn,
    user: dict = Depends(require_role("owner", "office_manager", "sales_rep", "super_admin")),
):
    app = await db.finance_applications.find_one(
        {"id": body.application_id, "company_id": user["company_id"]}, {"_id": 0},
    )
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    if app.get("status") not in ("decisioned",):
        raise HTTPException(status_code=400, detail="Buy-down only on a decisioned application before sign")
    offer = app.get("offer") or {}
    if not offer.get("apr"):
        raise HTTPException(status_code=400, detail="No active offer")
    quote = fc.buydown_quote(offer["amount"], offer["apr"], offer["term_months"], body.fee_pct)
    new_offer = {
        **offer,
        "apr": quote["new_apr"],
        "monthly_payment": quote["new_monthly_payment"],
        "total_finance_charge": fc.total_finance_charge(offer["amount"], quote["new_apr"], offer["term_months"]),
        "buydown": quote,
    }
    bid = str(uuid.uuid4())
    await db.finance_buydowns.insert_one({
        "id": bid,
        "application_id": app["id"],
        "company_id": user["company_id"],
        "applied_by": user["id"],
        "fee_pct": body.fee_pct,
        "contractor_fee": quote["contractor_fee"],
        "apr_before": offer["apr"],
        "apr_after": quote["new_apr"],
        "customer_savings": quote["customer_lifetime_savings"],
        "created_at": now_iso(),
    })
    await db.finance_applications.update_one(
        {"id": app["id"]},
        {"$set": {"offer": new_offer, "updated_at": now_iso()}},
    )
    await log_activity(user, "finance.buydown_applied",
                       meta={"application_id": app["id"], "fee_pct": body.fee_pct})
    return {"ok": True, "buydown_id": bid, **quote}


# -------------------- Funding events (ledger-only) --------------------
@router.post("/financing/funding-events")
async def create_funding_event(
    body: FundingEventIn,
    user: dict = Depends(require_role("owner", "accountant", "office_manager", "super_admin")),
):
    app = await db.finance_applications.find_one(
        {"id": body.application_id, "company_id": user["company_id"]}, {"_id": 0, "id": 1, "status": 1},
    )
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    eid = str(uuid.uuid4())
    await db.finance_funding_events.insert_one({
        "id": eid,
        "application_id": app["id"],
        "company_id": user["company_id"],
        "amount": float(body.amount),
        "kind": body.kind,
        "memo": body.memo,
        "recorded_by": user["id"],
        "created_at": now_iso(),
    })
    # Auto-advance to "funded" when a disbursement lands
    if body.kind == "disbursement" and app.get("status") in ("signed",):
        await db.finance_applications.update_one(
            {"id": app["id"]},
            {"$set": {"status": "funded", "funded_at": now_iso()}},
        )
    return {"ok": True, "id": eid}


@router.get("/financing/funding-events")
async def list_funding_events(user: dict = Depends(get_current_user), limit: int = 200):
    items = await db.finance_funding_events.find(
        {"company_id": user["company_id"]}, {"_id": 0},
    ).sort("created_at", -1).to_list(min(limit, 500))
    return items


# -------------------- Rental equipment financing --------------------
@router.post("/financing/rentals")
async def create_rental(
    body: RentalIn,
    user: dict = Depends(require_role("owner", "office_manager", "sales_rep", "csr", "super_admin")),
):
    rid = str(uuid.uuid4())
    weekly = body.weekly_payment
    monthly = body.monthly_payment
    if not weekly and monthly:
        weekly = round(monthly * 12 / 52, 2)
    if not monthly and weekly:
        monthly = round(weekly * 52 / 12, 2)
    if not weekly and not monthly:
        # default: rent-to-own over term_weeks
        weekly = round(body.equipment_value / max(body.term_weeks, 4), 2)
        monthly = round(weekly * 52 / 12, 2)
    doc = {
        "id": rid,
        "company_id": user["company_id"],
        "created_by": user["id"],
        "branch_id": body.branch_id,
        "customer_name": body.customer_name,
        "customer_email": body.customer_email,
        "equipment_name": body.equipment_name,
        "equipment_value": float(body.equipment_value),
        "weekly_payment": weekly,
        "monthly_payment": monthly,
        "term_weeks": int(body.term_weeks),
        "deposit": float(body.deposit),
        "balance_remaining": round(float(body.equipment_value) - float(body.deposit), 2),
        "status": "active",
        "created_at": now_iso(),
    }
    await db.finance_rentals.insert_one(doc)
    await log_activity(user, "finance.rental_created", meta={"rental_id": rid})
    return {k: v for k, v in doc.items() if k != "_id"}


@router.get("/financing/rentals")
async def list_rentals(user: dict = Depends(get_current_user), limit: int = 200):
    items = await db.finance_rentals.find(
        {"company_id": user["company_id"]}, {"_id": 0},
    ).sort("created_at", -1).to_list(min(limit, 500))
    return items


# -------------------- Contractor dashboard rollup --------------------
@router.get("/financing/dashboard")
async def contractor_dashboard(user: dict = Depends(get_current_user)):
    cid = user["company_id"]
    # Pipeline by status
    pipeline = {s: 0 for s in ["started", "decisioned", "signed", "funded", "declined"]}
    async for a in db.finance_applications.find(
        {"company_id": cid}, {"_id": 0, "status": 1},
    ):
        pipeline[a.get("status", "started")] = pipeline.get(a.get("status", "started"), 0) + 1

    # Totals
    funded_agg = await db.finance_funding_events.aggregate([
        {"$match": {"company_id": cid, "kind": "disbursement"}},
        {"$group": {"_id": None, "total": {"$sum": "$amount"}}},
    ]).to_list(1)
    fees_agg = await db.finance_buydowns.aggregate([
        {"$match": {"company_id": cid}},
        {"$group": {"_id": None, "total": {"$sum": "$contractor_fee"}}},
    ]).to_list(1)
    pending_amount_agg = await db.finance_applications.aggregate([
        {"$match": {"company_id": cid, "status": {"$in": ["decisioned", "signed"]}}},
        {"$group": {"_id": None, "total": {"$sum": "$amount"}}},
    ]).to_list(1)

    rentals_active = await db.finance_rentals.count_documents({"company_id": cid, "status": "active"})

    return {
        "pipeline": pipeline,
        "total_funded": (funded_agg[0]["total"] if funded_agg else 0) or 0,
        "total_buydown_fees": (fees_agg[0]["total"] if fees_agg else 0) or 0,
        "pending_amount": (pending_amount_agg[0]["total"] if pending_amount_agg else 0) or 0,
        "rentals_active": rentals_active,
    }


# -------------------- Admin --------------------
@router.get("/financing/admin/applications")
async def admin_list_applications(
    user: dict = Depends(require_role("super_admin")),
    status: Optional[str] = None, decision: Optional[str] = None,
):
    q: dict = {}
    if status:
        q["status"] = status
    if decision:
        q["decision"] = decision
    items = await db.finance_applications.find(
        q, {"_id": 0, "applicant.ssn4": 0},
    ).sort("created_at", -1).to_list(500)
    return items


@router.patch("/financing/admin/applications/{app_id}/decision")
async def admin_override_decision(
    app_id: str, body: DecisionOverrideIn,
    user: dict = Depends(require_role("super_admin")),
):
    app = await db.finance_applications.find_one({"id": app_id}, {"_id": 0})
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    offer = app.get("offer") or {}
    if body.apr is not None:
        offer["apr"] = body.apr
    if body.term_months is not None:
        offer["term_months"] = body.term_months
    if offer.get("amount") and offer.get("apr") and offer.get("term_months"):
        offer["monthly_payment"] = fc.monthly_payment(offer["amount"], offer["apr"], offer["term_months"])
        offer["total_finance_charge"] = fc.total_finance_charge(offer["amount"], offer["apr"], offer["term_months"])

    update = {
        "decision": body.decision,
        "decision_reason": f"admin_override: {body.reason or ''}",
        "offer": offer if offer else None,
        "status": "decisioned" if body.decision in ("approved", "counter_offer") else
                  "declined" if body.decision == "declined" else "manual_review",
        "updated_at": now_iso(),
        "admin_override_by": user["id"],
    }
    await db.finance_applications.update_one({"id": app_id}, {"$set": update})
    await log_activity(user, "finance.admin_override",
                       meta={"application_id": app_id, "decision": body.decision})
    return await db.finance_applications.find_one({"id": app_id}, {"_id": 0})


@router.get("/financing/admin/metrics")
async def admin_metrics(user: dict = Depends(require_role("super_admin"))):
    """Platform-wide financing volume."""
    by_status = await db.finance_applications.aggregate([
        {"$group": {"_id": "$status", "count": {"$sum": 1}, "amount": {"$sum": "$amount"}}},
    ]).to_list(50)
    funded_agg = await db.finance_funding_events.aggregate([
        {"$match": {"kind": "disbursement"}},
        {"$group": {"_id": None, "total": {"$sum": "$amount"}, "count": {"$sum": 1}}},
    ]).to_list(1)
    by_tier = await db.finance_applications.aggregate([
        {"$match": {"tier": {"$ne": None}}},
        {"$group": {"_id": "$tier.label", "count": {"$sum": 1}}},
    ]).to_list(50)
    return {
        "by_status": {x["_id"]: {"count": x["count"], "amount": x["amount"]} for x in by_status if x["_id"]},
        "by_tier": {x["_id"]: x["count"] for x in by_tier if x["_id"]},
        "total_funded": (funded_agg[0]["total"] if funded_agg else 0) or 0,
        "funding_events": (funded_agg[0]["count"] if funded_agg else 0) or 0,
    }
