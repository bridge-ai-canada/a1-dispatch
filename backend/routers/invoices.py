"""Invoices: line items, deposits, partial payments, public payment links."""
import uuid
import secrets
from datetime import datetime, timezone, timedelta
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, Request, Response
from pydantic import BaseModel
from emergentintegrations.payments.stripe.checkout import (
    StripeCheckout, CheckoutSessionRequest,
)

from deps import (
    db, now_iso, FRONTEND_URL, STRIPE_API_KEY,
    get_current_user, log_activity,
    send_email, email_layout,
)
from billing import (
    InvoiceIn, InvoiceUpdate, compute_totals,
)
from pdf_service import invoice_pdf

router = APIRouter()


# -------------------- helpers --------------------
async def _next_number(company_id: str) -> str:
    res = await db.counters.find_one_and_update(
        {"company_id": company_id, "kind": "invoice"},
        {"$inc": {"seq": 1}},
        upsert=True,
        return_document=True,
    )
    seq = (res or {}).get("seq", 1)
    return f"I-{seq:04d}"


def _new_token() -> str:
    return secrets.token_urlsafe(24)


def _paid_sum(inv: dict) -> float:
    return round(sum(float(p.get("amount", 0)) for p in (inv.get("payments") or [])
                     if p.get("status") == "paid"), 2)


def _expand(inv: dict) -> dict:
    totals = compute_totals(
        inv.get("line_items") or [],
        tax_rate=inv.get("tax_rate", 0),
        discount=inv.get("discount") or {},
        deposit=inv.get("deposit") or {},
    )
    paid = _paid_sum(inv)
    inv["totals"] = totals
    inv["paid_amount"] = paid
    inv["balance_due"] = round(max(totals["total"] - paid, 0), 2)
    return inv


def _refresh_status(inv: dict) -> str:
    totals = compute_totals(inv.get("line_items") or [], tax_rate=inv.get("tax_rate", 0),
                            discount=inv.get("discount") or {}, deposit=inv.get("deposit") or {})
    paid = _paid_sum(inv)
    if paid <= 0:
        if inv.get("status") in ("draft", None):
            return "draft"
        # past due?
        try:
            if inv.get("due_at") and datetime.fromisoformat(inv["due_at"].replace("Z", "+00:00")) < datetime.now(timezone.utc):
                return "overdue"
        except Exception:
            pass
        return inv.get("status") or "sent"
    if paid + 0.01 < totals["total"]:
        return "partial"
    return "paid"


# -------------------- CRUD --------------------
@router.post("/invoices")
async def create_invoice(body: InvoiceIn, user: dict = Depends(get_current_user)):
    iid = str(uuid.uuid4())
    number = await _next_number(user["company_id"])
    issued = datetime.now(timezone.utc)
    line_items = []
    for li in body.line_items:
        d = li.dict()
        d["id"] = d.get("id") or str(uuid.uuid4())
        line_items.append(d)
    doc = {
        "id": iid,
        "number": number,
        "public_token": _new_token(),
        "company_id": user["company_id"],
        "customer_id": body.customer_id,
        "customer_name": body.customer_name,
        "customer_email": (body.customer_email or "").lower() or None,
        "customer_phone": body.customer_phone,
        "address": body.address,
        "job_id": body.job_id,
        "estimate_id": body.estimate_id,
        "title": body.title or "Services rendered",
        "line_items": line_items,
        "tax_rate": body.tax_rate,
        "discount": body.discount.dict(),
        "deposit": body.deposit.dict(),
        "due_at": (issued + timedelta(days=body.due_in_days)).isoformat(),
        "issued_at": issued.isoformat(),
        "terms": body.terms,
        "notes": body.notes,
        "status": "draft",
        "payments": [],
        "sent_at": None,
        "viewed_at": None,
        "paid_at": None,
        "created_by": user["id"],
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    await db.invoices.insert_one(doc)
    await log_activity(user, "invoice.created", "invoice", iid, {"number": number})
    return _expand({k: v for k, v in doc.items() if k != "_id"})


@router.get("/invoices")
async def list_invoices(
    user: dict = Depends(get_current_user),
    status: Optional[str] = None,
    customer_id: Optional[str] = None,
):
    q = {"company_id": user["company_id"]}
    if status:
        q["status"] = status
    if customer_id:
        q["customer_id"] = customer_id
    items = await db.invoices.find(q, {"_id": 0, "public_token": 0}) \
        .sort("created_at", -1).to_list(500)
    return [_expand(it) for it in items]


@router.get("/invoices/{iid}")
async def get_invoice(iid: str, user: dict = Depends(get_current_user)):
    doc = await db.invoices.find_one({"id": iid, "company_id": user["company_id"]}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return _expand(doc)


@router.put("/invoices/{iid}")
async def update_invoice(iid: str, body: InvoiceUpdate, user: dict = Depends(get_current_user)):
    doc = await db.invoices.find_one({"id": iid, "company_id": user["company_id"]}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Invoice not found")
    if doc.get("status") == "paid":
        raise HTTPException(status_code=400, detail="Cannot edit a paid invoice")
    updates = body.dict(exclude_none=True)
    if "line_items" in updates:
        updates["line_items"] = [
            {**(li if isinstance(li, dict) else li.dict()),
             "id": (li.get("id") if isinstance(li, dict) else li.dict().get("id")) or str(uuid.uuid4())}
            for li in updates["line_items"]
        ]
    if "discount" in updates and hasattr(updates["discount"], "dict"):
        updates["discount"] = updates["discount"].dict()
    if "deposit" in updates and hasattr(updates["deposit"], "dict"):
        updates["deposit"] = updates["deposit"].dict()
    if "due_in_days" in updates:
        issued = datetime.fromisoformat(doc["issued_at"].replace("Z", "+00:00")) \
            if doc.get("issued_at") else datetime.now(timezone.utc)
        updates["due_at"] = (issued + timedelta(days=updates.pop("due_in_days"))).isoformat()
    updates["updated_at"] = now_iso()
    await db.invoices.update_one({"id": iid}, {"$set": updates})
    await log_activity(user, "invoice.updated", "invoice", iid, {})
    doc = await db.invoices.find_one({"id": iid}, {"_id": 0})
    return _expand(doc)


@router.delete("/invoices/{iid}")
async def delete_invoice(iid: str, user: dict = Depends(get_current_user)):
    doc = await db.invoices.find_one({"id": iid, "company_id": user["company_id"]}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Invoice not found")
    if (doc.get("payments") or []) and any(p.get("status") == "paid" for p in doc["payments"]):
        raise HTTPException(status_code=400, detail="Cannot delete invoice with payments")
    await db.invoices.delete_one({"id": iid})
    await log_activity(user, "invoice.deleted", "invoice", iid, {})
    return {"ok": True}


# -------------------- Send / PDF --------------------
@router.post("/invoices/{iid}/send")
async def send_invoice(iid: str, user: dict = Depends(get_current_user)):
    doc = await db.invoices.find_one({"id": iid, "company_id": user["company_id"]}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Invoice not found")
    if not doc.get("customer_email"):
        raise HTTPException(status_code=400, detail="Customer email required to send")
    token = doc.get("public_token") or _new_token()
    base = (FRONTEND_URL or "").rstrip("/")
    link = f"{base}/pay/{token}"
    await db.invoices.update_one(
        {"id": iid},
        {"$set": {
            "public_token": token,
            "status": "sent" if doc.get("status") == "draft" else doc.get("status"),
            "sent_at": now_iso(),
            "updated_at": now_iso(),
        }},
    )
    company = await db.companies.find_one({"id": user["company_id"]}, {"_id": 0}) or {}
    company_name = company.get("name", "A1 Field Pro")
    totals = compute_totals(doc.get("line_items") or [], tax_rate=doc.get("tax_rate", 0),
                            discount=doc.get("discount") or {}, deposit=doc.get("deposit") or {})
    body_html = f"""
        <p>Hi {doc.get('customer_name') or 'there'},</p>
        <p>Your invoice <b>{doc.get('number')}</b> for <b>${totals['total']:.2f}</b> from <b>{company_name}</b> is ready.</p>
        <p>Pay online securely — it only takes a moment.</p>
    """
    html = email_layout(
        title="Your invoice is ready",
        body_html=body_html,
        cta_label="View & Pay",
        cta_url=link,
    )
    await send_email(doc["customer_email"], f"Invoice {doc.get('number')} from {company_name}",
                     html, actor=user, purpose="invoice.send")
    await log_activity(user, "invoice.sent", "invoice", iid, {"to": doc["customer_email"]})
    return {"ok": True, "link": link}


@router.get("/invoices/{iid}/pdf")
async def invoice_pdf_route(iid: str, user: dict = Depends(get_current_user)):
    doc = await db.invoices.find_one({"id": iid, "company_id": user["company_id"]}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Invoice not found")
    company = await db.companies.find_one({"id": user["company_id"]}, {"_id": 0}) or {}
    totals = compute_totals(doc.get("line_items") or [], tax_rate=doc.get("tax_rate", 0),
                            discount=doc.get("discount") or {}, deposit=doc.get("deposit") or {})
    paid = _paid_sum(doc)
    pdf = invoice_pdf(doc, company, totals, paid)
    return Response(content=pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="{doc.get("number","invoice")}.pdf"'})


# -------------------- Internal checkout (owner-side) --------------------
class CheckoutIn(BaseModel):
    origin_url: str
    pay_type: str = "full"  # full | deposit | balance
    amount: Optional[float] = None


async def _create_checkout(inv: dict, request: Request, *, amount: float, pay_type: str, origin_url: str, user_id: Optional[str] = None) -> dict:
    host_url = str(request.base_url)
    webhook_url = f"{host_url}api/webhook/stripe"
    stripe_checkout = StripeCheckout(api_key=STRIPE_API_KEY, webhook_url=webhook_url)
    success_url = f"{origin_url}/payment/result?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{origin_url}/pay/{inv.get('public_token')}"
    req = CheckoutSessionRequest(
        amount=amount, currency="usd",
        success_url=success_url, cancel_url=cancel_url,
        metadata={
            "invoice_id": inv["id"],
            "company_id": inv["company_id"],
            "pay_type": pay_type,
            "type": "invoice",
        },
    )
    session = await stripe_checkout.create_checkout_session(req)
    await db.payment_transactions.insert_one({
        "id": str(uuid.uuid4()),
        "session_id": session.session_id,
        "invoice_id": inv["id"],
        "company_id": inv["company_id"],
        "user_id": user_id,
        "amount": amount,
        "currency": "usd",
        "payment_status": "initiated",
        "status": "open",
        "type": "invoice",
        "pay_type": pay_type,
        "metadata": {"invoice_id": inv["id"], "pay_type": pay_type},
        "created_at": now_iso(),
    })
    return {"url": session.url, "session_id": session.session_id, "amount": amount}


@router.post("/invoices/{iid}/checkout")
async def invoice_checkout(iid: str, body: CheckoutIn, request: Request, user: dict = Depends(get_current_user)):
    doc = await db.invoices.find_one({"id": iid, "company_id": user["company_id"]}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Invoice not found")
    totals = compute_totals(doc.get("line_items") or [], tax_rate=doc.get("tax_rate", 0),
                            discount=doc.get("discount") or {}, deposit=doc.get("deposit") or {})
    paid = _paid_sum(doc)
    if body.pay_type == "deposit":
        amount = float(totals.get("deposit_amount") or 0)
        if amount <= 0:
            raise HTTPException(status_code=400, detail="No deposit configured")
    elif body.pay_type == "balance":
        amount = round(max(totals["total"] - paid, 0), 2)
    else:
        amount = float(body.amount or totals["total"])
    if amount <= 0:
        raise HTTPException(status_code=400, detail="Nothing to charge")
    return await _create_checkout(doc, request, amount=amount, pay_type=body.pay_type,
                                  origin_url=body.origin_url, user_id=user["id"])


# -------------------- Public (customer) --------------------
@router.get("/public/invoices/{token}")
async def public_get_invoice(token: str):
    doc = await db.invoices.find_one({"public_token": token}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Invoice not found")
    if not doc.get("viewed_at"):
        await db.invoices.update_one({"public_token": token},
            {"$set": {"viewed_at": now_iso(),
                      "status": "sent" if doc.get("status") in ("draft", None) else doc.get("status")}})
        doc["viewed_at"] = now_iso()
    company = await db.companies.find_one({"id": doc["company_id"]}, {"_id": 0, "owner_id": 0}) or {}
    return {"invoice": _expand(doc), "company": company}


@router.post("/public/invoices/{token}/checkout")
async def public_invoice_checkout(token: str, body: CheckoutIn, request: Request):
    doc = await db.invoices.find_one({"public_token": token}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Invoice not found")
    totals = compute_totals(doc.get("line_items") or [], tax_rate=doc.get("tax_rate", 0),
                            discount=doc.get("discount") or {}, deposit=doc.get("deposit") or {})
    paid = _paid_sum(doc)
    if body.pay_type == "deposit":
        amount = float(totals.get("deposit_amount") or 0)
        if amount <= 0:
            raise HTTPException(status_code=400, detail="No deposit configured")
    else:
        # full or balance
        amount = round(max(totals["total"] - paid, 0), 2)
    if amount <= 0:
        raise HTTPException(status_code=400, detail="Invoice already paid")
    return await _create_checkout(doc, request, amount=amount, pay_type=body.pay_type,
                                  origin_url=body.origin_url)


# -------------------- Webhook handler hook --------------------
async def handle_invoice_payment(tx: dict):
    """Called from /api/webhook/stripe when an invoice transaction is paid."""
    iid = tx.get("invoice_id")
    if not iid:
        return
    inv = await db.invoices.find_one({"id": iid}, {"_id": 0})
    if not inv:
        return
    payment = {
        "id": str(uuid.uuid4()),
        "amount": float(tx.get("amount") or 0),
        "currency": tx.get("currency", "usd"),
        "method": "stripe",
        "session_id": tx.get("session_id"),
        "pay_type": tx.get("pay_type") or "full",
        "status": "paid",
        "paid_at": now_iso(),
    }
    inv_payments = (inv.get("payments") or []) + [payment]
    inv["payments"] = inv_payments
    new_status = _refresh_status(inv)
    updates = {"payments": inv_payments, "status": new_status, "updated_at": now_iso()}
    if new_status == "paid":
        updates["paid_at"] = now_iso()
    await db.invoices.update_one({"id": iid}, {"$set": updates})
    # log
    await db.activity.insert_one({
        "id": str(uuid.uuid4()),
        "company_id": inv["company_id"],
        "actor_id": "stripe_webhook",
        "actor_name": "Stripe",
        "actor_role": "system",
        "action": "invoice.payment_received",
        "target_type": "invoice",
        "target_id": iid,
        "meta": {"amount": payment["amount"], "pay_type": payment["pay_type"], "number": inv.get("number")},
        "created_at": now_iso(),
    })
    # push to creator
    try:
        from push_service import send_push_to_user
        if inv.get("created_by"):
            await send_push_to_user(inv["created_by"], {
                "title": "Payment received",
                "body": f'${payment["amount"]:.2f} on {inv.get("number","invoice")} ({payment["pay_type"]})',
                "url": f'/app/invoices/{iid}',
                "tag": f'inv-pay-{iid}',
            })
    except Exception:
        pass
