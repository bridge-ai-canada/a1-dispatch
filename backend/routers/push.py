"""Web Push subscription + public-key endpoints + manual test send."""
import uuid
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from deps import db, now_iso, VAPID_PUBLIC_KEY, get_current_user
from push_service import send_push_to_user

router = APIRouter()


class SubscriptionKeys(BaseModel):
    p256dh: str
    auth: str


class PushSubscribeIn(BaseModel):
    endpoint: str
    keys: SubscriptionKeys
    user_agent: Optional[str] = ""


class PushTestIn(BaseModel):
    user_id: Optional[str] = None  # default: self
    title: Optional[str] = "A1 Field Pro"
    body: Optional[str] = "Test push from dispatch"


@router.get("/push/public-key")
async def push_public_key():
    return {"public_key": VAPID_PUBLIC_KEY}


@router.post("/push/subscribe")
async def push_subscribe(body: PushSubscribeIn, user: dict = Depends(get_current_user)):
    if not VAPID_PUBLIC_KEY:
        raise HTTPException(status_code=503, detail="Push not configured on server")
    existing = await db.push_subscriptions.find_one({"endpoint": body.endpoint}, {"_id": 0})
    if existing:
        await db.push_subscriptions.update_one(
            {"endpoint": body.endpoint},
            {"$set": {"user_id": user["id"], "active": True,
                      "keys": body.keys.model_dump(),
                      "user_agent": body.user_agent, "updated_at": now_iso()}},
        )
        return {"ok": True, "id": existing["id"]}
    sub_id = str(uuid.uuid4())
    await db.push_subscriptions.insert_one({
        "id": sub_id,
        "user_id": user["id"],
        "company_id": user.get("company_id"),
        "endpoint": body.endpoint,
        "keys": body.keys.model_dump(),
        "user_agent": body.user_agent,
        "active": True,
        "created_at": now_iso(),
    })
    return {"ok": True, "id": sub_id}


@router.delete("/push/subscribe")
async def push_unsubscribe(endpoint: str, user: dict = Depends(get_current_user)):
    res = await db.push_subscriptions.delete_one(
        {"endpoint": endpoint, "user_id": user["id"]}
    )
    return {"ok": True, "removed": res.deleted_count}


@router.get("/push/subscriptions/me")
async def my_push_subscriptions(user: dict = Depends(get_current_user)):
    items = await db.push_subscriptions.find(
        {"user_id": user["id"]}, {"_id": 0, "keys": 0}
    ).sort("created_at", -1).to_list(20)
    return items


@router.post("/push/test")
async def push_test(body: PushTestIn, user: dict = Depends(get_current_user)):
    """Send a test push to self (or any user in company if owner/dispatcher)."""
    target = body.user_id or user["id"]
    if target != user["id"] and user["role"] not in ("owner", "dispatcher", "office_manager", "super_admin"):
        raise HTTPException(status_code=403, detail="Forbidden")
    if target != user["id"] and user["role"] != "super_admin":
        # cross-tenant guard
        tgt = await db.users.find_one({"id": target}, {"_id": 0, "company_id": 1})
        if not tgt or tgt.get("company_id") != user.get("company_id"):
            raise HTTPException(status_code=404, detail="User not in your company")
    result = await send_push_to_user(target, {
        "title": body.title or "A1 Field Pro",
        "body": body.body or "Test push from dispatch",
        "url": "/app/my-jobs",
        "tag": "a1-test",
    })
    return {"ok": True, **result}
