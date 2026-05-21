"""Stripe payments + webhook."""
import uuid
from fastapi import APIRouter, HTTPException, Request, Depends
from emergentintegrations.payments.stripe.checkout import (
    StripeCheckout, CheckoutSessionRequest,
)

from deps import (
    db, logger, now_iso, STRIPE_API_KEY,
    get_current_user, log_activity,
    CheckoutIn,
)

router = APIRouter()


@router.post("/payments/checkout")
async def create_checkout(body: CheckoutIn, request: Request, user: dict = Depends(get_current_user)):
    if not user.get("email_verified"):
        raise HTTPException(status_code=403,
            detail="Verify your email before sending payment links. Check inbox or resend verification from your profile.")
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


@router.get("/payments/status/{session_id}")
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
        if tx.get("type") == "invoice":
            from routers.invoices import handle_invoice_payment
            await handle_invoice_payment(tx)
            await db.payment_transactions.update_one(
                {"session_id": session_id}, {"$set": {"processed": True}}
            )
            return await db.payment_transactions.find_one({"session_id": session_id}, {"_id": 0})
        await db.jobs.update_one(
            {"id": tx["job_id"], "company_id": user["company_id"]},
            {"$set": {"paid": True, "status": "completed", "paid_at": now_iso()}},
        )
        await db.payment_transactions.update_one(
            {"session_id": session_id}, {"$set": {"processed": True}}
        )
        await log_activity(user, "payment.received", "job", tx["job_id"],
                           {"amount": tx.get("amount"), "currency": tx.get("currency", "usd")})
        # Push to job owner (creator) — could be dispatcher/owner who sent the link
        try:
            from push_service import send_push_to_user
            job_doc = await db.jobs.find_one({"id": tx["job_id"]}, {"title": 1, "created_by": 1, "assigned_to": 1})
            recipient = (job_doc or {}).get("created_by") or (job_doc or {}).get("assigned_to")
            if recipient:
                await send_push_to_user(recipient, {
                    "title": "Payment received",
                    "body": f'${tx.get("amount", 0):.2f} for {(job_doc or {}).get("title","job")}',
                    "url": f'/app/jobs/{tx["job_id"]}',
                    "tag": f'pay-{tx["job_id"]}',
                })
        except Exception:
            pass
    tx = await db.payment_transactions.find_one({"session_id": session_id}, {"_id": 0})
    return tx


@router.post("/webhook/stripe")
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
                # New: invoice payments
                if tx.get("type") == "invoice":
                    from routers.invoices import handle_invoice_payment
                    await handle_invoice_payment(tx)
                    await db.payment_transactions.update_one(
                        {"session_id": evt.session_id}, {"$set": {"processed": True}}
                    )
                    return {"received": True}
                if tx.get("type") == "tip":
                    await db.jobs.update_one(
                        {"id": tx["job_id"]},
                        {"$inc": {"tip": float(tx["amount"])},
                         "$set": {"last_tip_at": now_iso()}},
                    )
                    action = "tip.received"
                else:
                    await db.jobs.update_one(
                        {"id": tx["job_id"]},
                        {"$set": {"paid": True, "status": "completed", "paid_at": now_iso()}},
                    )
                    action = "payment.received"
                await db.payment_transactions.update_one(
                    {"session_id": evt.session_id}, {"$set": {"processed": True}}
                )
                await db.activity.insert_one({
                    "id": str(uuid.uuid4()),
                    "company_id": tx.get("company_id"),
                    "actor_id": "stripe_webhook",
                    "actor_name": "Stripe",
                    "actor_role": "system",
                    "action": action,
                    "target_type": "job",
                    "target_id": tx["job_id"],
                    "meta": {"amount": tx.get("amount"), "currency": tx.get("currency", "usd"), "session_id": evt.session_id},
                    "created_at": now_iso(),
                })
                # Push to job creator/assignee on payment or tip
                try:
                    from push_service import send_push_to_user
                    job_doc = await db.jobs.find_one({"id": tx["job_id"]}, {"title": 1, "created_by": 1, "assigned_to": 1})
                    recipient = (job_doc or {}).get("created_by") or (job_doc or {}).get("assigned_to")
                    if recipient:
                        label = "Tip received" if action == "tip.received" else "Payment received"
                        await send_push_to_user(recipient, {
                            "title": label,
                            "body": f'${tx.get("amount", 0):.2f} for {(job_doc or {}).get("title","job")}',
                            "url": f'/app/jobs/{tx["job_id"]}',
                            "tag": f'pay-{tx["job_id"]}',
                        })
                except Exception:
                    pass
    return {"received": True}
