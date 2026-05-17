"""Web Push notification helper.

Uses pywebpush + self-signed VAPID. No 3rd-party account required.
On 404/410 from the push service, the subscription is auto-removed (the user
has uninstalled/blocked the app).
"""
import asyncio
import json
import logging
from typing import Optional
from pywebpush import webpush, WebPushException

from deps import db, VAPID_PRIVATE_KEY, VAPID_PUBLIC_KEY, VAPID_SUBJECT

logger = logging.getLogger("a1fieldpro.push")


def _send_one(subscription: dict, payload: dict) -> tuple[bool, int]:
    if not VAPID_PRIVATE_KEY or not VAPID_PUBLIC_KEY:
        return False, 0
    try:
        webpush(
            subscription_info={
                "endpoint": subscription["endpoint"],
                "keys": subscription["keys"],
            },
            data=json.dumps(payload),
            vapid_private_key=VAPID_PRIVATE_KEY,
            vapid_claims={"sub": VAPID_SUBJECT},
            timeout=10,
        )
        return True, 201
    except WebPushException as e:
        status = getattr(e.response, "status_code", 0) if e.response is not None else 0
        return False, status
    except Exception as e:
        logger.warning(f"web-push send failed: {e}")
        return False, 0


async def send_push_to_user(user_id: str, payload: dict) -> dict:
    """Send a push to every active subscription for `user_id`.
    Removes subscriptions that return 404/410 (gone)."""
    if not user_id or not VAPID_PRIVATE_KEY:
        return {"sent": 0, "removed": 0}
    subs = await db.push_subscriptions.find(
        {"user_id": user_id, "active": {"$ne": False}}, {"_id": 0}
    ).to_list(20)
    if not subs:
        return {"sent": 0, "removed": 0}

    sent = 0
    removed = 0
    for sub in subs:
        ok, status = await asyncio.to_thread(_send_one, sub, payload)
        if ok:
            sent += 1
        elif status in (404, 410):
            await db.push_subscriptions.delete_one({"id": sub["id"]})
            removed += 1
    return {"sent": sent, "removed": removed}
