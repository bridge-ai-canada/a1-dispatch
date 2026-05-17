"""Customer portal endpoints."""
import uuid
from typing import Optional
from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel, Field
from emergentintegrations.payments.stripe.checkout import (
    StripeCheckout, CheckoutSessionRequest,
)

from deps import db, now_iso, STRIPE_API_KEY, get_current_user

router = APIRouter()


class RateIn(BaseModel):
    rating: int = Field(ge=1, le=5)
    comment: Optional[str] = ""


class TipCheckoutIn(BaseModel):
    amount: float
    origin_url: str


def _customer_only(user: dict):
    if user.get("role") != "customer":
        raise HTTPException(status_code=403, detail="Customer-only")


@router.get("/portal/jobs")
async def portal_jobs(user: dict = Depends(get_current_user)):
    _customer_only(user)
    items = await db.jobs.find(
        {"customer_email": user["email"]}, {"_id": 0}
    ).sort("created_at", -1).to_list(200)
    return items


@router.get("/portal/companies")
async def portal_companies(user: dict = Depends(get_current_user)):
    _customer_only(user)
    company_ids = await db.jobs.distinct("company_id", {"customer_email": user["email"]})
    items = await db.companies.find({"id": {"$in": company_ids}}, {"_id": 0, "owner_id": 0}).to_list(50)
    return items


@router.post("/portal/jobs/{job_id}/rate")
async def rate_job(job_id: str, body: RateIn, user: dict = Depends(get_current_user)):
    _customer_only(user)
    job = await db.jobs.find_one({"id": job_id, "customer_email": user["email"]}, {"_id": 0})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.get("status") != "completed":
        raise HTTPException(status_code=400, detail="You can only rate completed visits")
    await db.jobs.update_one(
        {"id": job_id},
        {"$set": {
            "rating": body.rating,
            "rating_comment": (body.comment or "")[:500],
            "rated_at": now_iso(),
            "rated_by": user["email"],
        }},
    )
    await db.activity.insert_one({
        "id": str(uuid.uuid4()),
        "company_id": job.get("company_id"),
        "actor_id": user["id"],
        "actor_name": user.get("name") or user["email"],
        "actor_role": "customer",
        "action": "rating.created",
        "target_type": "job",
        "target_id": job_id,
        "meta": {"rating": body.rating, "tech_id": job.get("assigned_to")},
        "created_at": now_iso(),
    })
    return {"ok": True, "rating": body.rating}


@router.post("/portal/jobs/{job_id}/tip-checkout")
async def tip_checkout(
    job_id: str, body: TipCheckoutIn, request: Request,
    user: dict = Depends(get_current_user),
):
    _customer_only(user)
    job = await db.jobs.find_one({"id": job_id, "customer_email": user["email"]}, {"_id": 0})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.get("status") != "completed":
        raise HTTPException(status_code=400, detail="You can only tip on completed visits")
    if body.amount <= 0:
        raise HTTPException(status_code=400, detail="Tip amount must be positive")

    host_url = str(request.base_url)
    webhook_url = f"{host_url}api/webhook/stripe"
    stripe_checkout = StripeCheckout(api_key=STRIPE_API_KEY, webhook_url=webhook_url)
    success_url = f"{body.origin_url}/portal?tipped={job_id}"
    cancel_url = f"{body.origin_url}/portal"
    req = CheckoutSessionRequest(
        amount=body.amount,
        currency="usd",
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={
            "job_id": job_id,
            "company_id": job.get("company_id") or "",
            "user_id": user["id"],
            "type": "tip",
        },
    )
    session = await stripe_checkout.create_checkout_session(req)
    await db.payment_transactions.insert_one({
        "id": str(uuid.uuid4()),
        "session_id": session.session_id,
        "job_id": job_id,
        "company_id": job.get("company_id"),
        "user_id": user["id"],
        "amount": body.amount,
        "currency": "usd",
        "payment_status": "initiated",
        "status": "open",
        "type": "tip",
        "metadata": {"job_id": job_id, "type": "tip"},
        "created_at": now_iso(),
    })
    return {"url": session.url, "session_id": session.session_id}


@router.get("/portal/payments/status/{session_id}")
async def portal_payment_status(
    session_id: str, request: Request, user: dict = Depends(get_current_user),
):
    """Customer-side polling for tip checkouts. Falls back to Stripe if pending."""
    _customer_only(user)
    tx = await db.payment_transactions.find_one(
        {"session_id": session_id, "user_id": user["id"]}, {"_id": 0}
    )
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")
    if tx.get("payment_status") == "paid":
        return tx

    host_url = str(request.base_url)
    webhook_url = f"{host_url}api/webhook/stripe"
    stripe_checkout = StripeCheckout(api_key=STRIPE_API_KEY, webhook_url=webhook_url)
    status = await stripe_checkout.get_checkout_status(session_id)
    await db.payment_transactions.update_one(
        {"session_id": session_id},
        {"$set": {"payment_status": status.payment_status, "status": status.status, "updated_at": now_iso()}},
    )
    if status.payment_status == "paid" and not tx.get("processed") and tx.get("type") == "tip":
        await db.jobs.update_one(
            {"id": tx["job_id"]},
            {"$inc": {"tip": float(tx["amount"])},
             "$set": {"last_tip_at": now_iso()}},
        )
        await db.payment_transactions.update_one(
            {"session_id": session_id}, {"$set": {"processed": True}}
        )
        await db.activity.insert_one({
            "id": str(uuid.uuid4()),
            "company_id": tx.get("company_id"),
            "actor_id": user["id"],
            "actor_name": user.get("name") or user["email"],
            "actor_role": "customer",
            "action": "tip.received",
            "target_type": "job",
            "target_id": tx["job_id"],
            "meta": {"amount": tx["amount"], "currency": tx.get("currency", "usd")},
            "created_at": now_iso(),
        })
    return await db.payment_transactions.find_one({"session_id": session_id}, {"_id": 0})
