"""Outbound webhook delivery — HMAC-signed POST with retries.

Tenants subscribe to events (job.created, invoice.paid, etc.) and we POST the
event JSON to their URL signed with the subscription's secret.
"""
import asyncio
import hashlib
import hmac
import json
import secrets
import time
import uuid
from typing import Any

import httpx

from deps import db, logger, now_iso


# Backoff intervals for retry attempts (seconds).
RETRY_BACKOFF = [10, 60, 300, 1800]  # 10s, 1m, 5m, 30m


def new_secret() -> str:
    return "whk_" + secrets.token_urlsafe(32)


def sign_payload(secret: str, body: bytes, timestamp: int) -> str:
    """HMAC-SHA256 over `{timestamp}.{body}` — matches Stripe-style verification."""
    msg = f"{timestamp}.".encode() + body
    return hmac.new(secret.encode(), msg=msg, digestmod=hashlib.sha256).hexdigest()


async def emit(company_id: str, event: str, payload: dict) -> int:
    """Emit an event to all matching subscribers. Returns delivery count enqueued."""
    subs = await db.webhook_subscriptions.find(
        {"company_id": company_id, "active": True, "events": event},
        {"_id": 0},
    ).to_list(100)
    if not subs:
        return 0
    body = {
        "id": "evt_" + uuid.uuid4().hex,
        "type": event,
        "company_id": company_id,
        "created_at": now_iso(),
        "data": payload,
    }
    for sub in subs:
        await _deliver(sub, body, attempt=0)
    return len(subs)


async def _deliver(sub: dict, body: dict, *, attempt: int) -> None:
    raw = json.dumps(body, separators=(",", ":")).encode()
    ts = int(time.time())
    sig = sign_payload(sub["secret"], raw, ts)
    headers = {
        "Content-Type": "application/json",
        "X-A1FP-Event": body["type"],
        "X-A1FP-Delivery": body["id"],
        "X-A1FP-Timestamp": str(ts),
        "X-A1FP-Signature": f"t={ts},v1={sig}",
    }
    delivery = {
        "id": "del_" + uuid.uuid4().hex,
        "company_id": sub["company_id"],
        "subscription_id": sub["id"],
        "event": body["type"],
        "event_id": body["id"],
        "url": sub["url"],
        "attempt": attempt + 1,
        "status": "pending",
        "created_at": now_iso(),
    }
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(sub["url"], content=raw, headers=headers)
        delivery["status_code"] = resp.status_code
        delivery["response_body"] = resp.text[:1024]
        delivery["status"] = "delivered" if 200 <= resp.status_code < 300 else "failed"
        delivery["delivered_at"] = now_iso()
    except Exception as e:
        delivery["status"] = "error"
        delivery["error"] = f"{type(e).__name__}: {e}"[:512]

    await db.webhook_deliveries.insert_one(delivery)

    # Schedule a retry if not 2xx and we have budget left.
    if delivery["status"] != "delivered" and attempt < len(RETRY_BACKOFF):
        delay = RETRY_BACKOFF[attempt]
        asyncio.create_task(_retry_after(sub, body, attempt + 1, delay))


async def _retry_after(sub: dict, body: dict, attempt: int, delay: int) -> None:
    await asyncio.sleep(delay)
    # Refresh sub state — owner may have disabled in the meantime.
    fresh = await db.webhook_subscriptions.find_one(
        {"id": sub["id"], "active": True}, {"_id": 0},
    )
    if not fresh:
        return
    await _deliver(fresh, body, attempt=attempt)
