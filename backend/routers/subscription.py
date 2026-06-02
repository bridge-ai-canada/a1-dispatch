"""Subscription / plan management.

The Stripe Checkout path is wired but requires Stripe Price IDs to be configured
in env (STRIPE_PRICE_STARTER, STRIPE_PRICE_LITE, STRIPE_PRICE_PRO, STRIPE_PRICE_ENTERPRISE).
Without those, the endpoint falls back to dev-mode (immediate plan switch + log).
Super-admin can override plan and trial status manually.
"""
import os
from datetime import datetime, timezone, timedelta
from typing import Optional, Literal
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from deps import db, now_iso, get_current_user, require_role, log_activity, FRONTEND_URL
from whitelabel_service import PLANS, plan as get_plan, seat_limit

router = APIRouter()

PLAN_KEYS = Literal["basic", "team", "business", "pro", "enterprise"]


class ChangePlanIn(BaseModel):
    plan: PLAN_KEYS


class CheckoutIn(BaseModel):
    plan: PLAN_KEYS
    origin_url: str  # success/cancel base


class AdminSetIn(BaseModel):
    plan: Optional[PLAN_KEYS] = None
    status: Optional[Literal["trialing", "active", "past_due", "canceled", "suspended"]] = None
    seats_override: Optional[int] = None  # 0 = unlimited
    trial_days: Optional[int] = None


@router.get("/subscription/plans")
async def list_plans():
    """Public plan catalog (no auth — used by pricing/landing pages)."""
    return list(PLANS.values())


@router.get("/subscription")
async def my_subscription(user: dict = Depends(get_current_user)):
    company = await db.companies.find_one(
        {"id": user["company_id"]}, {"_id": 0, "subscription": 1, "name": 1},
    ) or {}
    sub = company.get("subscription") or {}
    plan_key = sub.get("plan") or "basic"
    p = get_plan(plan_key)
    seats_used = await db.users.count_documents({"company_id": user["company_id"], "active": True})
    limit = sub.get("seats_override") or seat_limit(plan_key)
    return {
        "plan": p,
        "status": sub.get("status") or "trialing",
        "current_period_end": sub.get("current_period_end"),
        "trial_ends_at": sub.get("trial_ends_at"),
        "stripe_customer_id": sub.get("stripe_customer_id"),
        "stripe_subscription_id": sub.get("stripe_subscription_id"),
        "seats_used": seats_used,
        "seats_limit": limit,  # 0 = unlimited
        "seats_remaining": (limit - seats_used) if limit else None,
    }


@router.post("/subscription/change-plan")
async def change_plan(
    body: ChangePlanIn,
    user: dict = Depends(require_role("owner", "super_admin")),
):
    """Dev/no-Stripe path — directly flip plan. In production, Stripe webhook fires this."""
    p = get_plan(body.plan)
    await db.companies.update_one(
        {"id": user["company_id"]},
        {"$set": {
            "subscription.plan": body.plan,
            "subscription.status": "active",
            "subscription.updated_at": now_iso(),
        }},
    )
    await log_activity(user, "subscription.changed", meta={"plan": body.plan})
    return {"plan": p, "status": "active"}


@router.post("/subscription/checkout")
async def subscription_checkout(
    body: CheckoutIn,
    user: dict = Depends(require_role("owner", "super_admin")),
):
    """Create a Stripe Checkout session for a subscription.
    Falls back to dev-mode (immediate switch) when STRIPE_PRICE_* not configured."""
    price_id = os.environ.get(f"STRIPE_PRICE_{body.plan.upper()}", "").strip()
    if not price_id:
        # Dev mode — flip plan immediately (would be Stripe webhook in prod)
        await db.companies.update_one(
            {"id": user["company_id"]},
            {"$set": {
                "subscription.plan": body.plan,
                "subscription.status": "active",
                "subscription.dev_mode": True,
                "subscription.updated_at": now_iso(),
            }},
        )
        return {
            "checkout_url": None,
            "dev_mode": True,
            "message": f"Plan switched to {body.plan} (Stripe price not configured — set STRIPE_PRICE_{body.plan.upper()} to enable real billing).",
        }

    try:
        from emergentintegrations.payments.stripe.checkout import StripeCheckout, CheckoutSessionRequest
    except Exception:
        raise HTTPException(status_code=503, detail="Payments SDK unavailable")

    stripe_api_key = os.environ.get("STRIPE_API_KEY", "")
    if not stripe_api_key:
        raise HTTPException(status_code=503, detail="Stripe not configured")

    checkout = StripeCheckout(api_key=stripe_api_key, webhook_url=f"{FRONTEND_URL}/api/subscription/webhook")
    success_url = f"{body.origin_url.rstrip('/')}/app/settings/subscription?status=ok&session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{body.origin_url.rstrip('/')}/app/settings/subscription?status=cancelled"

    # Subscription mode via price ID
    session_req = CheckoutSessionRequest(
        amount=float(get_plan(body.plan)["price_usd"]),
        currency="usd",
        success_url=success_url, cancel_url=cancel_url,
        metadata={
            "company_id": user["company_id"],
            "plan": body.plan,
            "user_id": user["id"],
            "kind": "subscription",
            "price_id": price_id,
        },
    )
    try:
        session = await checkout.create_checkout_session(session_req)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Stripe error: {e}")

    await db.subscription_checkouts.insert_one({
        "session_id": session.session_id,
        "company_id": user["company_id"],
        "plan": body.plan,
        "created_at": now_iso(),
        "status": "pending",
    })
    return {"checkout_url": session.url, "session_id": session.session_id, "dev_mode": False}


@router.get("/subscription/checkout/{session_id}")
async def poll_checkout(session_id: str, user: dict = Depends(get_current_user)):
    """Poll Stripe + update local state."""
    rec = await db.subscription_checkouts.find_one(
        {"session_id": session_id, "company_id": user["company_id"]}, {"_id": 0},
    )
    if not rec:
        raise HTTPException(status_code=404, detail="Session not found")
    if rec.get("status") == "paid":
        return rec
    try:
        from emergentintegrations.payments.stripe.checkout import StripeCheckout
        checkout = StripeCheckout(api_key=os.environ.get("STRIPE_API_KEY", ""), webhook_url="")
        status = await checkout.get_checkout_status(session_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    paid = status.payment_status == "paid"
    if paid:
        await db.subscription_checkouts.update_one(
            {"session_id": session_id}, {"$set": {"status": "paid", "paid_at": now_iso()}},
        )
        await db.companies.update_one(
            {"id": user["company_id"]},
            {"$set": {
                "subscription.plan": rec["plan"],
                "subscription.status": "active",
                "subscription.updated_at": now_iso(),
            }},
        )
    return {**rec, "payment_status": status.payment_status, "paid": paid}


# -------------------- Super-admin override --------------------
@router.patch("/subscription/admin/{company_id}")
async def admin_set_subscription(
    company_id: str, body: AdminSetIn,
    user: dict = Depends(require_role("super_admin")),
):
    company = await db.companies.find_one({"id": company_id}, {"_id": 0})
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    updates = {"subscription.updated_at": now_iso()}
    if body.plan:
        updates["subscription.plan"] = body.plan
    if body.status:
        updates["subscription.status"] = body.status
    if body.seats_override is not None:
        updates["subscription.seats_override"] = body.seats_override
    if body.trial_days is not None:
        ends = datetime.now(timezone.utc) + timedelta(days=body.trial_days)
        updates["subscription.trial_ends_at"] = ends.isoformat()
        if not body.status:
            updates["subscription.status"] = "trialing"
    await db.companies.update_one({"id": company_id}, {"$set": updates})
    return await db.companies.find_one({"id": company_id}, {"_id": 0, "subscription": 1, "name": 1, "id": 1})
