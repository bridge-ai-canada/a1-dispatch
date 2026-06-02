"""Web Push notification helper.

Uses pywebpush + self-signed VAPID. No 3rd-party account required.
On 404/410 from the push service, the subscription is auto-removed (the user
has uninstalled/blocked the app).

Invalid VAPID keys are detected on first use and the module enters a
"disabled" mode — we log ONCE and stop trying. Prevents log floods when the
deployer ships the app with malformed VAPID keys (which is harmless: web push
just won't work until they're regenerated).
"""
import asyncio
import json
import logging
from pywebpush import webpush, WebPushException

from deps import db, VAPID_PRIVATE_KEY, VAPID_PUBLIC_KEY, VAPID_SUBJECT

logger = logging.getLogger("a1fieldpro.push")

# Set to True after the FIRST failed deserialize so we don't log on every call.
_VAPID_BROKEN = False


def _send_one(subscription: dict, payload: dict) -> tuple[bool, int]:
    global _VAPID_BROKEN
    if _VAPID_BROKEN or not VAPID_PRIVATE_KEY or not VAPID_PUBLIC_KEY:
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
        msg = str(e)
        # Detect bad VAPID format and stop spamming the log.
        if "deserialize" in msg or "ASN.1" in msg or "unsupported key type" in msg:
            if not _VAPID_BROKEN:
                _VAPID_BROKEN = True
                logger.error(
                    "VAPID_PRIVATE_KEY appears malformed — disabling web push for this process. "
                    "Regenerate with `vapid --gen` (py-vapid) and update VAPID_PRIVATE_KEY in .env. "
                    "Underlying error: %s", msg,
                )
            return False, 0
        logger.warning(f"web-push send failed: {e}")
        return False, 0


async def send_push_to_user(user_id: str, payload: dict) -> dict:
    """Send a push to every active subscription for `user_id`.
    Honors per-user push_prefs (skipped event classes + quiet hours).
    Removes subscriptions that return 404/410 (gone)."""
    if not user_id:
        return {"sent": 0, "removed": 0, "skipped": False}

    # Check user prefs based on the push `tag` prefix
    user = await db.users.find_one({"id": user_id}, {"push_prefs": 1, "_id": 0})
    prefs = (user or {}).get("push_prefs") or {}
    tag = payload.get("tag", "")
    tag_prefix = tag.split("-")[0] if tag else ""
    pref_keys = {
        "job": "job_assigned",        # 'job-<id>' = new/reassigned
        "pay": "payment_received",
        "tip": "tip_received",
        "rate": "rating_created",
        "low": "rating_low_alert",    # 'low-rate-<id>'
    }
    pref_key = pref_keys.get(tag_prefix)
    if pref_key and prefs.get(pref_key) is False:
        return {"sent": 0, "removed": 0, "skipped": True}

    # Quiet hours (UTC hour for simplicity; refine to user timezone later)
    qs = prefs.get("quiet_hours_start")
    qe = prefs.get("quiet_hours_end")
    if isinstance(qs, int) and isinstance(qe, int):
        from datetime import datetime, timezone as _tz
        now_h = datetime.now(_tz.utc).hour
        in_quiet = (qs <= now_h < qe) if qs <= qe else (now_h >= qs or now_h < qe)
        if in_quiet:
            return {"sent": 0, "removed": 0, "skipped": True}

    # Web Push fanout (skipped if VAPID not configured)
    subs = []
    if VAPID_PRIVATE_KEY:
        subs = await db.push_subscriptions.find(
            {"user_id": user_id, "active": {"$ne": False}}, {"_id": 0}
        ).to_list(20)

    sent = 0
    removed = 0
    for sub in subs:
        ok, status = await asyncio.to_thread(_send_one, sub, payload)
        if ok:
            sent += 1
        elif status in (404, 410):
            await db.push_subscriptions.delete_one({"id": sub["id"]})
            removed += 1

    # Fan out to Expo push tokens (mobile app) — never block on failure
    try:
        from expo_push_service import send_expo_to_user
        expo = await send_expo_to_user(user_id, payload)
        sent += expo.get("sent", 0)
        removed += expo.get("removed", 0)
    except Exception as e:
        logger.warning(f"expo fanout failed: {e}")

    return {"sent": sent, "removed": removed, "skipped": False}
