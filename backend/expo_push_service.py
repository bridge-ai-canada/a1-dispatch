"""Expo Push (FCM/APNs) adapter — for the React Native mobile app.

When a tech installs the mobile app and grants notification permission, Expo
gives them a token like 'ExponentPushToken[xxxxxx]'. The mobile app POSTs that
token to /api/push/expo-token. From then on, send_push_to_user() will also
emit to their Expo endpoint(s) in parallel with VAPID Web Push.
"""
import asyncio
import logging
from typing import Optional
from exponent_server_sdk import PushClient, PushMessage, PushServerError, DeviceNotRegisteredError
from requests.exceptions import ConnectionError, HTTPError

from deps import db, now_iso

logger = logging.getLogger("a1fieldpro.expo_push")
_client: Optional[PushClient] = None


def _client_instance() -> PushClient:
    global _client
    if _client is None:
        _client = PushClient()
    return _client


def _send_one(token: str, payload: dict) -> tuple[bool, str]:
    try:
        msg = PushMessage(
            to=token,
            title=payload.get("title", "A1 Field Pro"),
            body=payload.get("body", ""),
            data={"url": payload.get("url"), "tag": payload.get("tag")},
            sound="default",
            channel_id="default",
        )
        ticket = _client_instance().publish(msg)
        ticket.validate_response()
        return True, ""
    except DeviceNotRegisteredError:
        return False, "DeviceNotRegistered"
    except (PushServerError, ConnectionError, HTTPError, ValueError) as e:
        return False, type(e).__name__
    except Exception as e:
        logger.warning(f"expo push failed: {e}")
        return False, type(e).__name__


async def send_expo_to_user(user_id: str, payload: dict) -> dict:
    if not user_id:
        return {"sent": 0, "removed": 0}
    tokens = await db.expo_push_tokens.find(
        {"user_id": user_id, "active": {"$ne": False}}, {"_id": 0}
    ).to_list(20)
    if not tokens:
        return {"sent": 0, "removed": 0}
    sent = 0
    removed = 0
    for t in tokens:
        ok, err = await asyncio.to_thread(_send_one, t["token"], payload)
        if ok:
            sent += 1
            await db.expo_push_tokens.update_one(
                {"id": t["id"]}, {"$set": {"last_used_at": now_iso()}},
            )
        elif err == "DeviceNotRegistered":
            await db.expo_push_tokens.delete_one({"id": t["id"]})
            removed += 1
    return {"sent": sent, "removed": removed}
