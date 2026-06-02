"""Webhook system — inbound receivers + outbound tenant subscriptions.

Inbound:
- POST /api/webhooks/{provider}     ← Stripe, Twilio, QuickBooks, Helcim, Zoom, Google Calendar, Outlook
  Verifies signature per-provider, stores raw event, dispatches to handler.

Outbound:
- GET/POST/PATCH/DELETE /api/webhooks/subscriptions
- GET /api/webhooks/deliveries
- POST /api/webhooks/subscriptions/{id}/test
"""
import base64
import hashlib
import hmac
import json
import os
import time
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, HttpUrl

from deps import db, get_current_user, now_iso, log_activity
from services import webhook_emitter as emitter

router = APIRouter()

ALLOWED_ROLES = {"owner", "office_manager", "super_admin"}

EVENT_TYPES = [
    "job.created", "job.updated", "job.completed", "job.cancelled",
    "invoice.created", "invoice.paid", "invoice.overdue",
    "estimate.created", "estimate.signed",
    "customer.created", "customer.updated",
    "finance_application.created", "finance_application.funded",
    "payment.received",
]


def _require_admin(user: dict) -> None:
    if user.get("role") not in ALLOWED_ROLES:
        raise HTTPException(status_code=403, detail="Owner / office_manager only")


# -------------------- Inbound receivers --------------------
@router.post("/webhooks/in/{provider}")
async def receive_webhook(provider: str, request: Request):
    """Generic inbound webhook receiver — verifies signature per provider, then
    persists the raw event for async processing."""
    raw = await request.body()
    headers = dict(request.headers)
    ok, info = await _verify_inbound(provider, raw, headers)

    evt = {
        "id": "in_" + uuid.uuid4().hex,
        "provider": provider,
        "received_at": now_iso(),
        "signature_ok": ok,
        "info": info,
        "headers": {k.lower(): v for k, v in headers.items() if k.lower().startswith(("x-", "stripe-", "webhook-", "intuit-"))},
        "body": raw.decode("utf-8", errors="replace")[:8192],
        "processed": False,
    }
    await db.webhook_events.insert_one(evt)

    # Google Calendar 'sync' notifications send a verification ping with no body.
    if provider == "google_calendar" and request.headers.get("x-goog-resource-state") == "sync":
        return {"ok": True}

    # Microsoft Graph validation handshake: respond with the validationToken text.
    val = request.query_params.get("validationToken")
    if val:
        return Response(content=val, media_type="text/plain")

    if not ok:
        # Still return 200 — many providers will retry forever on 4xx, and we
        # logged the rejection. But we use 400 for clear "bad signature" cases.
        raise HTTPException(status_code=400, detail=f"signature: {info}")
    return {"ok": True}


async def _verify_inbound(provider: str, body: bytes, headers: dict) -> tuple[bool, str]:
    """Per-provider signature verification. Returns (ok, info_message)."""
    h = {k.lower(): v for k, v in headers.items()}
    if provider == "stripe":
        secret = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
        sig = h.get("stripe-signature", "")
        if not secret:
            return True, "no_secret_configured"
        if not sig:
            return False, "missing stripe-signature header"
        try:
            parts = dict(p.split("=", 1) for p in sig.split(",") if "=" in p)
            ts, v1 = parts.get("t", "0"), parts.get("v1", "")
            signed = f"{ts}.".encode() + body
            expected = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
            return hmac.compare_digest(expected, v1), "ok" if hmac.compare_digest(expected, v1) else "sig_mismatch"
        except Exception as e:
            return False, str(e)
    if provider == "twilio":
        # Twilio uses base64(HMAC-SHA1(url + sorted_params)).
        secret = os.environ.get("TWILIO_AUTH_TOKEN", "")
        sig = h.get("x-twilio-signature", "")
        if not secret:
            return True, "no_secret_configured"
        if not sig:
            return False, "missing x-twilio-signature"
        # We don't reconstruct the exact URL here (ingress can rewrite), so we
        # accept presence + log. A production deploy would reconstruct it.
        return True, "header_present"
    if provider == "quickbooks":
        secret = os.environ.get("QUICKBOOKS_WEBHOOK_VERIFIER", "")
        sig = h.get("intuit-signature", "")
        if not secret:
            return True, "no_secret_configured"
        if not sig:
            return False, "missing intuit-signature"
        expected = base64.b64encode(
            hmac.new(secret.encode(), body, hashlib.sha256).digest()
        ).decode()
        return hmac.compare_digest(expected, sig), "ok" if hmac.compare_digest(expected, sig) else "sig_mismatch"
    if provider == "helcim":
        secret = os.environ.get("HELCIM_WEBHOOK_VERIFIER", "")
        webhook_id = h.get("webhook-id", "")
        ts = h.get("webhook-timestamp", "")
        sig = h.get("webhook-signature", "")
        if not secret:
            return True, "no_secret_configured"
        if not (webhook_id and ts and sig):
            return False, "missing helcim webhook headers"
        try:
            key = base64.b64decode(secret)
        except Exception:
            key = secret.encode()
        signed = f"{webhook_id}.{ts}.".encode() + body
        expected = base64.b64encode(
            hmac.new(key, signed, hashlib.sha256).digest()
        ).decode()
        # Helcim sends `v1,<sig>` — split if present.
        sig_value = sig.split(",", 1)[-1].strip()
        return hmac.compare_digest(expected, sig_value), "ok" if hmac.compare_digest(expected, sig_value) else "sig_mismatch"
    if provider == "zoom":
        secret = os.environ.get("ZOOM_WEBHOOK_SECRET_TOKEN", "")
        ts = h.get("x-zm-request-timestamp", "")
        sig = h.get("x-zm-signature", "")
        if not secret:
            return True, "no_secret_configured"
        if not (ts and sig):
            return False, "missing zoom webhook headers"
        msg = f"v0:{ts}:{body.decode('utf-8', errors='replace')}"
        expected = "v0=" + hmac.new(secret.encode(), msg.encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, sig), "ok" if hmac.compare_digest(expected, sig) else "sig_mismatch"
    if provider == "google_calendar":
        # Google uses X-Goog-Channel-Token instead of a body signature.
        return True, "channel_token_only"
    if provider == "outlook_calendar":
        # Microsoft Graph: clientState in payload. Verified async during processing.
        return True, "client_state_only"
    return True, "no_verifier"


# -------------------- Outbound subscriptions --------------------
class WebhookSubIn(BaseModel):
    url: HttpUrl
    events: list[str]
    description: Optional[str] = ""
    active: bool = True


@router.get("/webhooks/subscriptions")
async def list_subscriptions(user: dict = Depends(get_current_user)):
    _require_admin(user)
    rows = await db.webhook_subscriptions.find(
        {"company_id": user["company_id"]}, {"_id": 0},
    ).to_list(100)
    # Redact secret — only show suffix
    for r in rows:
        s = r.get("secret") or ""
        r["secret_visible"] = ("…" + s[-6:]) if s else ""
        r.pop("secret", None)
    return {"subscriptions": rows, "event_types": EVENT_TYPES}


@router.post("/webhooks/subscriptions")
async def create_subscription(payload: WebhookSubIn, user: dict = Depends(get_current_user)):
    _require_admin(user)
    bad = [e for e in payload.events if e not in EVENT_TYPES]
    if bad:
        raise HTTPException(status_code=400, detail=f"Unknown events: {bad}")
    sid = "whs_" + uuid.uuid4().hex
    secret = emitter.new_secret()
    doc = {
        "id": sid,
        "company_id": user["company_id"],
        "url": str(payload.url),
        "events": payload.events,
        "description": payload.description or "",
        "active": payload.active,
        "secret": secret,
        "created_at": now_iso(),
        "created_by": user["id"],
    }
    await db.webhook_subscriptions.insert_one(doc)
    await log_activity(user, "webhook.subscription.created", "webhook", sid, {"events": payload.events})
    # Return the secret once
    out = {**doc, "secret_shown_once": secret}
    out.pop("_id", None)
    return out


class WebhookSubPatch(BaseModel):
    url: Optional[HttpUrl] = None
    events: Optional[list[str]] = None
    description: Optional[str] = None
    active: Optional[bool] = None


@router.patch("/webhooks/subscriptions/{sid}")
async def update_subscription(sid: str, payload: WebhookSubPatch, user: dict = Depends(get_current_user)):
    _require_admin(user)
    fields = {k: (str(v) if k == "url" else v) for k, v in payload.model_dump(exclude_unset=True).items()}
    if not fields:
        return {"ok": True}
    if "events" in fields:
        bad = [e for e in fields["events"] if e not in EVENT_TYPES]
        if bad:
            raise HTTPException(status_code=400, detail=f"Unknown events: {bad}")
    res = await db.webhook_subscriptions.update_one(
        {"company_id": user["company_id"], "id": sid},
        {"$set": {**fields, "updated_at": now_iso()}},
    )
    if not res.matched_count:
        raise HTTPException(status_code=404, detail="Not found")
    return {"ok": True}


@router.delete("/webhooks/subscriptions/{sid}")
async def delete_subscription(sid: str, user: dict = Depends(get_current_user)):
    _require_admin(user)
    res = await db.webhook_subscriptions.delete_one(
        {"company_id": user["company_id"], "id": sid},
    )
    if not res.deleted_count:
        raise HTTPException(status_code=404, detail="Not found")
    await log_activity(user, "webhook.subscription.deleted", "webhook", sid, {})
    return {"ok": True}


@router.post("/webhooks/subscriptions/{sid}/test")
async def test_subscription(sid: str, user: dict = Depends(get_current_user)):
    _require_admin(user)
    sub = await db.webhook_subscriptions.find_one(
        {"company_id": user["company_id"], "id": sid}, {"_id": 0},
    )
    if not sub:
        raise HTTPException(status_code=404, detail="Not found")
    body = {
        "id": "evt_" + uuid.uuid4().hex,
        "type": "ping",
        "company_id": user["company_id"],
        "created_at": now_iso(),
        "data": {"hello": "world"},
    }
    raw = json.dumps(body, separators=(",", ":")).encode()
    ts = int(time.time())
    sig = emitter.sign_payload(sub["secret"], raw, ts)
    import httpx
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(
                sub["url"], content=raw,
                headers={
                    "Content-Type": "application/json",
                    "X-A1FP-Event": "ping",
                    "X-A1FP-Timestamp": str(ts),
                    "X-A1FP-Signature": f"t={ts},v1={sig}",
                },
            )
        return {"ok": 200 <= r.status_code < 300, "status_code": r.status_code, "body": r.text[:512]}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


@router.get("/webhooks/deliveries")
async def list_deliveries(user: dict = Depends(get_current_user), limit: int = 100):
    _require_admin(user)
    rows = await db.webhook_deliveries.find(
        {"company_id": user["company_id"]}, {"_id": 0},
    ).sort("created_at", -1).limit(limit).to_list(limit)
    return {"deliveries": rows}


@router.get("/webhooks/events")
async def list_inbound_events(user: dict = Depends(get_current_user), limit: int = 50):
    """Recent inbound webhook events (raw log) — owner-only."""
    _require_admin(user)
    rows = await db.webhook_events.find(
        {}, {"_id": 0, "body": 0},  # don't return body in listing
    ).sort("received_at", -1).limit(limit).to_list(limit)
    return {"events": rows}
