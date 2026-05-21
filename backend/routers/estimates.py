"""Estimates: Good/Better/Best proposals, public approval + e-signature."""
import uuid
import secrets
from datetime import datetime, timezone, timedelta
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, Request, Response

from deps import (
    db, now_iso, FRONTEND_URL,
    get_current_user, log_activity,
    send_email, email_layout,
)
from billing import (
    EstimateIn, EstimateUpdate, ApproveIn, DeclineIn,
    tier_totals, monthly_payment,
)
from pdf_service import estimate_pdf
from financing_service import get_prequal_quote

router = APIRouter()


# -------------------- helpers --------------------
async def _next_number(company_id: str, kind: str = "estimate") -> str:
    res = await db.counters.find_one_and_update(
        {"company_id": company_id, "kind": kind},
        {"$inc": {"seq": 1}},
        upsert=True,
        return_document=True,
    )
    seq = (res or {}).get("seq", 1)
    prefix = "E" if kind == "estimate" else "I"
    return f"{prefix}-{seq:04d}"


def _new_token() -> str:
    return secrets.token_urlsafe(24)


def _compute_all_tier_totals(doc: dict) -> dict:
    tax = float(doc.get("tax_rate", 0) or 0)
    disc = doc.get("discount") or {}
    dep = doc.get("deposit") or {}
    out = {}
    for t in doc.get("tiers") or []:
        out[t.get("key")] = tier_totals(t, tax_rate=tax, discount=disc, deposit=dep)
    return out


def _expand(doc: dict) -> dict:
    """Attach computed totals + financing preview to response."""
    totals = _compute_all_tier_totals(doc)
    doc["totals_by_tier"] = totals
    fin = doc.get("financing") or {}
    if fin.get("enabled"):
        mp = {}
        for key, t in totals.items():
            mp[key] = monthly_payment(t["total"], fin.get("apr", 9.99),
                                      fin.get("term_months", 24))
        doc["monthly_payment_by_tier"] = mp
    return doc


# -------------------- CRUD --------------------
@router.post("/estimates")
async def create_estimate(body: EstimateIn, user: dict = Depends(get_current_user)):
    eid = str(uuid.uuid4())
    expires_at = (datetime.now(timezone.utc) + timedelta(days=body.expires_in_days)).isoformat()
    number = await _next_number(user["company_id"], "estimate")
    # ensure tier addon/line item ids
    tiers = []
    for t in body.tiers:
        td = t.dict()
        for li in td.get("line_items") or []:
            li["id"] = li.get("id") or str(uuid.uuid4())
        for a in td.get("addons") or []:
            a["id"] = a.get("id") or str(uuid.uuid4())
        tiers.append(td)
    doc = {
        "id": eid,
        "number": number,
        "public_token": _new_token(),
        "company_id": user["company_id"],
        "customer_id": body.customer_id,
        "customer_name": body.customer_name,
        "customer_email": (body.customer_email or "").lower() or None,
        "customer_phone": body.customer_phone,
        "address": body.address,
        "job_id": body.job_id,
        "title": body.title,
        "intro": body.intro,
        "tiers": tiers,
        "tax_rate": body.tax_rate,
        "discount": body.discount.dict(),
        "deposit": body.deposit.dict(),
        "financing": body.financing.dict(),
        "terms": body.terms,
        "expires_at": expires_at,
        "status": "draft",
        "selected_tier": None,
        "signature": None,
        "sent_at": None,
        "viewed_at": None,
        "approved_at": None,
        "declined_at": None,
        "created_by": user["id"],
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    await db.estimates.insert_one(doc)
    await log_activity(user, "estimate.created", "estimate", eid, {"title": body.title, "number": number})
    return _expand({k: v for k, v in doc.items() if k != "_id"})


@router.get("/estimates")
async def list_estimates(
    user: dict = Depends(get_current_user),
    status: Optional[str] = None,
    customer_id: Optional[str] = None,
):
    q = {"company_id": user["company_id"]}
    if status:
        q["status"] = status
    if customer_id:
        q["customer_id"] = customer_id
    items = await db.estimates.find(q, {"_id": 0, "public_token": 0, "signature": 0}) \
        .sort("created_at", -1).to_list(500)
    return [_expand(it) for it in items]


@router.get("/estimates/{eid}")
async def get_estimate(eid: str, user: dict = Depends(get_current_user)):
    doc = await db.estimates.find_one({"id": eid, "company_id": user["company_id"]}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Estimate not found")
    return _expand(doc)


@router.put("/estimates/{eid}")
async def update_estimate(eid: str, body: EstimateUpdate, user: dict = Depends(get_current_user)):
    doc = await db.estimates.find_one({"id": eid, "company_id": user["company_id"]}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Estimate not found")
    if doc.get("status") in ("approved", "declined", "converted"):
        raise HTTPException(status_code=400, detail=f"Cannot edit {doc['status']} estimate")
    updates = body.dict(exclude_none=True)
    if "tiers" in updates:
        tiers = []
        for t in updates["tiers"]:
            td = t if isinstance(t, dict) else t.dict()
            for li in td.get("line_items") or []:
                li["id"] = li.get("id") or str(uuid.uuid4())
            for a in td.get("addons") or []:
                a["id"] = a.get("id") or str(uuid.uuid4())
            tiers.append(td)
        updates["tiers"] = tiers
    if "discount" in updates and hasattr(updates["discount"], "dict"):
        updates["discount"] = updates["discount"].dict()
    if "deposit" in updates and hasattr(updates["deposit"], "dict"):
        updates["deposit"] = updates["deposit"].dict()
    if "financing" in updates and hasattr(updates["financing"], "dict"):
        updates["financing"] = updates["financing"].dict()
    if "expires_in_days" in updates:
        updates["expires_at"] = (datetime.now(timezone.utc) + timedelta(days=updates.pop("expires_in_days"))).isoformat()
    updates["updated_at"] = now_iso()
    await db.estimates.update_one({"id": eid}, {"$set": updates})
    await log_activity(user, "estimate.updated", "estimate", eid, {})
    doc = await db.estimates.find_one({"id": eid}, {"_id": 0})
    return _expand(doc)


@router.delete("/estimates/{eid}")
async def delete_estimate(eid: str, user: dict = Depends(get_current_user)):
    doc = await db.estimates.find_one({"id": eid, "company_id": user["company_id"]}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Estimate not found")
    if doc.get("status") in ("approved", "converted"):
        raise HTTPException(status_code=400, detail="Cannot delete approved/converted estimate")
    await db.estimates.delete_one({"id": eid})
    await log_activity(user, "estimate.deleted", "estimate", eid, {})
    return {"ok": True}


# -------------------- Send / PDF / Convert --------------------
@router.post("/estimates/{eid}/send")
async def send_estimate(eid: str, user: dict = Depends(get_current_user)):
    doc = await db.estimates.find_one({"id": eid, "company_id": user["company_id"]}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Estimate not found")
    if not doc.get("customer_email"):
        raise HTTPException(status_code=400, detail="Customer email required to send")
    token = doc.get("public_token") or _new_token()
    base = (FRONTEND_URL or "").rstrip("/")
    link = f"{base}/proposal/{token}"
    await db.estimates.update_one(
        {"id": eid},
        {"$set": {
            "public_token": token,
            "status": "sent" if doc.get("status") == "draft" else doc.get("status"),
            "sent_at": now_iso(),
            "updated_at": now_iso(),
        }},
    )
    company = await db.companies.find_one({"id": user["company_id"]}, {"_id": 0}) or {}
    company_name = company.get("name", "A1 Field Pro")
    body_html = f"""
        <p>Hi {doc.get('customer_name') or 'there'},</p>
        <p>Your proposal <b>{doc.get('title')}</b> from <b>{company_name}</b> is ready to review.</p>
        <p>Click below to view your options, choose the package that's right for you, and sign online.</p>
    """
    html = email_layout(
        title="Your proposal is ready",
        body_html=body_html,
        cta_label="Review & Approve",
        cta_url=link,
    )
    await send_email(doc["customer_email"], f"Your proposal from {company_name}",
                     html, actor=user, purpose="estimate.send")
    await log_activity(user, "estimate.sent", "estimate", eid, {"to": doc["customer_email"]})
    return {"ok": True, "link": link}


@router.get("/estimates/{eid}/pdf")
async def estimate_pdf_route(eid: str, user: dict = Depends(get_current_user)):
    doc = await db.estimates.find_one({"id": eid, "company_id": user["company_id"]}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Estimate not found")
    company = await db.companies.find_one({"id": user["company_id"]}, {"_id": 0}) or {}
    totals = _compute_all_tier_totals(doc)
    pdf = estimate_pdf(doc, company, totals)
    return Response(content=pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="{doc.get("number","estimate")}.pdf"'})


@router.post("/estimates/{eid}/convert")
async def convert_to_invoice(eid: str, user: dict = Depends(get_current_user)):
    doc = await db.estimates.find_one({"id": eid, "company_id": user["company_id"]}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Estimate not found")
    if doc.get("status") != "approved":
        raise HTTPException(status_code=400, detail="Only approved estimates can be converted")
    tier_key = doc.get("selected_tier")
    tier = next((t for t in (doc.get("tiers") or []) if t.get("key") == tier_key), None)
    if not tier:
        raise HTTPException(status_code=400, detail="Selected tier missing")
    items = list(tier.get("line_items") or []) + [a for a in (tier.get("addons") or []) if a.get("selected")]
    iid = str(uuid.uuid4())
    number = await _next_number(user["company_id"], "invoice")
    issued = datetime.now(timezone.utc)
    invoice = {
        "id": iid,
        "number": number,
        "public_token": _new_token(),
        "company_id": user["company_id"],
        "estimate_id": eid,
        "customer_id": doc.get("customer_id"),
        "customer_name": doc.get("customer_name"),
        "customer_email": doc.get("customer_email"),
        "customer_phone": doc.get("customer_phone"),
        "address": doc.get("address"),
        "job_id": doc.get("job_id"),
        "title": doc.get("title"),
        "line_items": items,
        "tax_rate": doc.get("tax_rate", 0),
        "discount": doc.get("discount") or {"type": "percent", "value": 0},
        "deposit": doc.get("deposit") or {"type": "none", "value": 0},
        "terms": doc.get("terms") or "",
        "notes": "",
        "status": "draft",
        "issued_at": issued.isoformat(),
        "due_at": (issued + timedelta(days=14)).isoformat(),
        "payments": [],
        "sent_at": None,
        "viewed_at": None,
        "paid_at": None,
        "created_by": user["id"],
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    await db.invoices.insert_one(invoice)
    await db.estimates.update_one({"id": eid}, {"$set": {"status": "converted", "converted_invoice_id": iid, "updated_at": now_iso()}})
    await log_activity(user, "estimate.converted", "estimate", eid, {"invoice_id": iid, "number": number})
    invoice.pop("_id", None)
    return invoice


# -------------------- Public (customer) --------------------
@router.get("/public/estimates/{token}")
async def public_get_estimate(token: str):
    doc = await db.estimates.find_one({"public_token": token}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Proposal not found")
    # auto-mark viewed once
    if not doc.get("viewed_at"):
        await db.estimates.update_one({"public_token": token},
            {"$set": {"viewed_at": now_iso(), "status": "viewed" if doc.get("status") == "sent" else doc.get("status")}})
        doc["viewed_at"] = now_iso()
    company = await db.companies.find_one({"id": doc["company_id"]}, {"_id": 0, "owner_id": 0}) or {}
    return {"estimate": _expand(doc), "company": company}


@router.post("/public/estimates/{token}/approve")
async def public_approve(token: str, body: ApproveIn, request: Request):
    doc = await db.estimates.find_one({"public_token": token}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Proposal not found")
    if doc.get("status") in ("approved", "converted", "declined"):
        raise HTTPException(status_code=400, detail=f"Already {doc['status']}")
    tier = next((t for t in (doc.get("tiers") or []) if t.get("key") == body.selected_tier), None)
    if not tier:
        raise HTTPException(status_code=400, detail="Selected tier not found")
    # mark selected addons
    addon_ids = set(body.selected_addons or [])
    for t in doc.get("tiers", []):
        if t.get("key") == body.selected_tier:
            for a in t.get("addons") or []:
                a["selected"] = a.get("id") in addon_ids
    sig = {
        "data_url": body.signature_base64,
        "signer_name": body.signer_name,
        "signed_at": now_iso(),
        "ip": request.client.host if request.client else "",
        "user_agent": request.headers.get("User-Agent", "")[:200],
    }
    await db.estimates.update_one(
        {"public_token": token},
        {"$set": {
            "status": "approved",
            "selected_tier": body.selected_tier,
            "tiers": doc["tiers"],
            "signature": sig,
            "approved_at": now_iso(),
            "updated_at": now_iso(),
        }},
    )
    # activity (system actor)
    await db.activity.insert_one({
        "id": str(uuid.uuid4()),
        "company_id": doc["company_id"],
        "actor_id": "customer",
        "actor_name": body.signer_name,
        "actor_role": "customer",
        "action": "estimate.approved",
        "target_type": "estimate",
        "target_id": doc["id"],
        "meta": {"tier": body.selected_tier, "number": doc.get("number")},
        "created_at": now_iso(),
    })
    # push to owner/creator
    try:
        from push_service import send_push_to_user
        recipient = doc.get("created_by")
        if recipient:
            await send_push_to_user(recipient, {
                "title": "Estimate approved",
                "body": f'{body.signer_name} chose {body.selected_tier.title()} on {doc.get("number")}',
                "url": f'/app/estimates/{doc["id"]}',
                "tag": f'est-approve-{doc["id"]}',
            })
    except Exception:
        pass
    updated = await db.estimates.find_one({"id": doc["id"]}, {"_id": 0})
    return _expand(updated)


@router.post("/public/estimates/{token}/decline")
async def public_decline(token: str, body: DeclineIn):
    doc = await db.estimates.find_one({"public_token": token}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Proposal not found")
    if doc.get("status") in ("approved", "converted", "declined"):
        raise HTTPException(status_code=400, detail=f"Already {doc['status']}")
    await db.estimates.update_one(
        {"public_token": token},
        {"$set": {"status": "declined", "decline_reason": (body.reason or "")[:500],
                  "declined_at": now_iso(), "updated_at": now_iso()}},
    )
    await db.activity.insert_one({
        "id": str(uuid.uuid4()),
        "company_id": doc["company_id"],
        "actor_id": "customer",
        "actor_name": doc.get("customer_name") or "Customer",
        "actor_role": "customer",
        "action": "estimate.declined",
        "target_type": "estimate",
        "target_id": doc["id"],
        "meta": {"reason": (body.reason or "")[:200]},
        "created_at": now_iso(),
    })
    return {"ok": True}


@router.get("/public/estimates/{token}/pdf")
async def public_estimate_pdf(token: str):
    doc = await db.estimates.find_one({"public_token": token}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Proposal not found")
    company = await db.companies.find_one({"id": doc["company_id"]}, {"_id": 0}) or {}
    totals = _compute_all_tier_totals(doc)
    pdf = estimate_pdf(doc, company, totals)
    return Response(content=pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="{doc.get("number","estimate")}.pdf"'})


@router.post("/public/estimates/{token}/financing-quote")
async def public_financing_quote(token: str, payload: dict):
    doc = await db.estimates.find_one({"public_token": token}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Proposal not found")
    amount = float(payload.get("amount", 0) or 0)
    fin = doc.get("financing") or {}
    apr = float(payload.get("apr", fin.get("apr", 9.99)))
    term = int(payload.get("term_months", fin.get("term_months", 24)))
    quote = await get_prequal_quote(amount, apr, term)
    return quote
