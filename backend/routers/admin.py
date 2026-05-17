"""Admin endpoints: activity feed, users, invites, roles config."""
import uuid
import secrets as pysecrets
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends

from deps import (
    db, now_iso, FRONTEND_URL,
    hash_password, create_invite_token, create_pw_reset_token,
    get_current_user, require_perm,
    send_email, email_layout,
    log_activity,
    InviteIn, UserUpdateIn,
)
from roles import ROLES, ROLE_LABELS, PERMISSIONS, INVITE_ALLOWED

router = APIRouter()


@router.get("/activity")
async def activity_feed(
    user: dict = Depends(require_perm("activity.read")),
    limit: int = 50, skip: int = 0, action: Optional[str] = None,
):
    q = {}
    if user["role"] != "super_admin":
        q["company_id"] = user["company_id"]
    if action:
        q["action"] = action
    items = await db.activity.find(q, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    return items


@router.get("/users")
async def list_users(user: dict = Depends(get_current_user), all_tenants: bool = False):
    if user["role"] == "super_admin" and all_tenants:
        q = {}
    else:
        q = {"company_id": user["company_id"]}
    items = await db.users.find(q, {"_id": 0, "password_hash": 0, "mfa_secret": 0}).to_list(500)
    return items


@router.patch("/users/{user_id}")
async def update_user(user_id: str, body: UserUpdateIn, actor: dict = Depends(get_current_user)):
    if actor["role"] not in ("super_admin", "owner"):
        raise HTTPException(status_code=403, detail="Forbidden")
    target = await db.users.find_one({"id": user_id}, {"_id": 0, "password_hash": 0, "mfa_secret": 0})
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    if actor["role"] != "super_admin" and target.get("company_id") != actor["company_id"]:
        raise HTTPException(status_code=403, detail="Cross-tenant edit forbidden")
    if target.get("role") == "owner" and actor["id"] != target["id"]:
        raise HTTPException(status_code=400, detail="Cannot modify the company owner")
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if "role" in updates:
        if updates["role"] not in ROLES:
            raise HTTPException(status_code=400, detail="Invalid role")
        if updates["role"] == "super_admin" and actor["role"] != "super_admin":
            raise HTTPException(status_code=403, detail="Cannot grant super_admin")
        if updates["role"] == "owner" and actor["role"] != "super_admin":
            raise HTTPException(status_code=403, detail="Cannot grant owner role")
    if updates:
        await db.users.update_one({"id": user_id}, {"$set": updates})
        await log_activity(actor, "user.updated", "user", user_id, updates)
    return await db.users.find_one({"id": user_id}, {"_id": 0, "password_hash": 0, "mfa_secret": 0})


@router.post("/users/invite")
async def invite_user(body: InviteIn, actor: dict = Depends(get_current_user)):
    if not actor.get("email_verified"):
        raise HTTPException(status_code=403,
            detail="Verify your email before inviting teammates. Check inbox or resend verification from your profile.")
    allowed = INVITE_ALLOWED.get(actor["role"], set())
    if body.role not in allowed:
        raise HTTPException(status_code=403, detail=f"Cannot invite role '{body.role}'")
    email = body.email.lower().strip()
    if await db.users.find_one({"email": email}):
        raise HTTPException(status_code=400, detail="Email already registered")
    temp_password = pysecrets.token_urlsafe(10)
    uid = str(uuid.uuid4())
    user = {
        "id": uid,
        "company_id": actor["company_id"],
        "name": body.name,
        "email": email,
        "password_hash": hash_password(temp_password),
        "role": body.role,
        "active": True,
        "mfa_enabled": False,
        "mfa_secret": None,
        "email_verified": False,
        "invited_by": actor["id"],
        "created_at": now_iso(),
    }
    await db.users.insert_one(user)
    user.pop("_id", None)
    create_invite_token(uid)  # reserved (existing behavior)
    setup_url = f"{FRONTEND_URL}/reset?token={create_pw_reset_token(uid)}&invited=1"
    company = await db.companies.find_one({"id": actor["company_id"]}, {"_id": 0}) or {}
    email_id = await send_email(
        email,
        f"You're invited to {company.get('name','A1 Field Pro')}",
        email_layout(
            f"You're invited to {company.get('name','A1 Field Pro')}",
            f"<p>{actor['name']} invited you as a <strong>{ROLE_LABELS.get(body.role, body.role)}</strong>. Click the button to set your password and sign in.</p>",
            "Set my password", setup_url,
        ),
        actor=actor, purpose="user.invite",
    )
    await log_activity(actor, "user.invited", "user", uid, {"role": body.role, "email": email})
    out = {k: v for k, v in user.items() if k not in {"password_hash", "mfa_secret"}}
    out["setup_url"] = setup_url
    out["temp_password"] = temp_password
    out["email_sent"] = bool(email_id)
    return out


@router.get("/config/roles")
async def get_roles_config(user: dict = Depends(get_current_user)):
    return {"roles": ROLES, "labels": ROLE_LABELS, "permissions": PERMISSIONS,
            "invite_allowed": {k: list(v) for k, v in INVITE_ALLOWED.items()}}
