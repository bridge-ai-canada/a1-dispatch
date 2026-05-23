"""Per-tenant API keys for programmatic access.

Issued by owner; gated by plan (api_access feature). Keys are hashed at rest.
Use `Authorization: Bearer afp_live_...` header for external automations.
"""
import hashlib
import secrets
import uuid
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel

from deps import db, now_iso, get_current_user, require_role, log_activity
from whitelabel_service import has_feature

router = APIRouter()

PREFIX = "afp_live_"


class ApiKeyIn(BaseModel):
    name: str
    scopes: Optional[list] = None  # e.g. ["jobs:read","customers:read"]; None = full company access


def _hash_key(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


async def _require_api_access(user: dict):
    company = await db.companies.find_one(
        {"id": user["company_id"]}, {"_id": 0, "subscription": 1},
    ) or {}
    plan_key = (company.get("subscription") or {}).get("plan")
    if not has_feature(plan_key, "api_access"):
        raise HTTPException(status_code=402, detail="API access requires the Pro or Enterprise plan.")


@router.get("/api-keys")
async def list_api_keys(user: dict = Depends(require_role("owner", "super_admin"))):
    items = await db.api_keys.find(
        {"company_id": user["company_id"]},
        {"_id": 0, "hash": 0},
    ).sort("created_at", -1).to_list(200)
    return items


@router.post("/api-keys")
async def create_api_key(body: ApiKeyIn, user: dict = Depends(require_role("owner", "super_admin"))):
    await _require_api_access(user)
    raw = PREFIX + secrets.token_urlsafe(28)
    kid = str(uuid.uuid4())
    doc = {
        "id": kid,
        "company_id": user["company_id"],
        "name": body.name,
        "scopes": body.scopes,
        "hash": _hash_key(raw),
        "prefix_visible": raw[: len(PREFIX) + 6],
        "created_by": user["id"],
        "created_at": now_iso(),
        "last_used_at": None,
        "active": True,
    }
    await db.api_keys.insert_one(doc)
    await log_activity(user, "api_key.created", meta={"id": kid, "name": body.name})
    # Return the raw key ONCE
    return {
        "id": kid, "name": body.name,
        "key": raw,
        "prefix_visible": doc["prefix_visible"],
        "scopes": body.scopes,
        "created_at": doc["created_at"],
        "warning": "This is the only time the full key will be shown. Store it securely.",
    }


@router.delete("/api-keys/{key_id}")
async def revoke_api_key(key_id: str, user: dict = Depends(require_role("owner", "super_admin"))):
    res = await db.api_keys.update_one(
        {"id": key_id, "company_id": user["company_id"]},
        {"$set": {"active": False, "revoked_at": now_iso()}},
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Key not found")
    await log_activity(user, "api_key.revoked", meta={"id": key_id})
    return {"ok": True}


async def authenticate_api_key(authorization: Optional[str]) -> Optional[dict]:
    """Helper: returns {company_id, key_id, scopes} if a valid Bearer key, else None.
    Other modules can use this when they want to allow API-key auth in addition to JWT."""
    if not authorization or not authorization.startswith("Bearer "):
        return None
    raw = authorization.split(" ", 1)[1].strip()
    if not raw.startswith(PREFIX):
        return None
    key = await db.api_keys.find_one(
        {"hash": _hash_key(raw), "active": True}, {"_id": 0},
    )
    if not key:
        return None
    await db.api_keys.update_one(
        {"id": key["id"]}, {"$set": {"last_used_at": now_iso()}},
    )
    return {
        "company_id": key["company_id"],
        "key_id": key["id"],
        "scopes": key.get("scopes"),
    }
