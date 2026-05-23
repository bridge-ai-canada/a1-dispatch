"""Tenant-scoped store for integration connections + simple Fernet encryption.

The Fernet key is derived deterministically from JWT_SECRET so credentials at
rest in Mongo are not plaintext, and the same app instance can always decrypt
them. For production-grade key rotation, set INTEGRATION_FERNET_KEY directly.
"""
import base64
import hashlib
import os
import time
import uuid
from typing import Any, Optional

from cryptography.fernet import Fernet, InvalidToken

from deps import db, now_iso

_JWT_SECRET = os.environ["JWT_SECRET"]
_RAW_KEY = os.environ.get("INTEGRATION_FERNET_KEY") or _JWT_SECRET
# Fernet needs 32 url-safe base64 bytes
_FERNET = Fernet(base64.urlsafe_b64encode(hashlib.sha256(_RAW_KEY.encode()).digest()))


def encrypt(value: str | None) -> str | None:
    if value is None or value == "":
        return value
    return _FERNET.encrypt(value.encode("utf-8")).decode("ascii")


def decrypt(value: str | None) -> str | None:
    if not value:
        return value
    try:
        return _FERNET.decrypt(value.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError):
        return None


SECRET_KEYS = {
    "access_token", "refresh_token", "client_secret",
    "auth_token", "api_token", "secret_key", "server_key",
    "webhook_secret",
}


def _encrypt_secrets(data: dict) -> dict:
    out = {}
    for k, v in (data or {}).items():
        if k in SECRET_KEYS and isinstance(v, str):
            out[k] = encrypt(v)
        else:
            out[k] = v
    return out


def _decrypt_secrets(data: dict) -> dict:
    out = {}
    for k, v in (data or {}).items():
        if k in SECRET_KEYS and isinstance(v, str) and v.startswith("gAAAAA"):
            out[k] = decrypt(v)
        else:
            out[k] = v
    return out


def redact(data: dict) -> dict:
    """Mask secrets before returning to the UI."""
    out = {}
    for k, v in (data or {}).items():
        if k in SECRET_KEYS and isinstance(v, str) and v:
            plain = decrypt(v) if v.startswith("gAAAAA") else v
            if plain:
                out[k] = "•" * 6 + plain[-4:] if len(plain) > 4 else "••••"
            else:
                out[k] = ""
        else:
            out[k] = v
    return out


# -------------------- CRUD --------------------
async def get(company_id: str, provider: str) -> Optional[dict]:
    """Returns the integration document with secrets decrypted in place."""
    doc = await db.integrations.find_one(
        {"company_id": company_id, "provider": provider},
        {"_id": 0},
    )
    if not doc:
        return None
    doc["data"] = _decrypt_secrets(doc.get("data") or {})
    return doc


async def list_for_company(company_id: str) -> list[dict]:
    """List integrations for a tenant. Secrets are REDACTED (not decrypted)."""
    docs = await db.integrations.find(
        {"company_id": company_id}, {"_id": 0},
    ).to_list(50)
    for d in docs:
        d["data"] = redact(d.get("data") or {})
    return docs


async def upsert(
    company_id: str,
    provider: str,
    *,
    status: str = "connected",
    data: Optional[dict] = None,
    user_id: Optional[str] = None,
    merge_data: bool = True,
) -> dict:
    """Create or update an integration record."""
    existing = await db.integrations.find_one(
        {"company_id": company_id, "provider": provider}, {"_id": 0},
    )
    merged_data = (existing.get("data") if existing and merge_data else None) or {}
    merged_data.update(data or {})
    enc_data = _encrypt_secrets(merged_data)
    doc = {
        "id": existing["id"] if existing else str(uuid.uuid4()),
        "company_id": company_id,
        "provider": provider,
        "status": status,
        "data": enc_data,
        "connected_by": user_id or (existing or {}).get("connected_by"),
        "connected_at": (existing or {}).get("connected_at") or now_iso(),
        "updated_at": now_iso(),
        "last_sync_at": (existing or {}).get("last_sync_at"),
        "last_sync_status": (existing or {}).get("last_sync_status"),
        "last_error": None if status == "connected" else (existing or {}).get("last_error"),
    }
    await db.integrations.update_one(
        {"company_id": company_id, "provider": provider},
        {"$set": doc},
        upsert=True,
    )
    return doc


async def delete(company_id: str, provider: str) -> bool:
    res = await db.integrations.delete_one(
        {"company_id": company_id, "provider": provider},
    )
    return res.deleted_count > 0


async def mark_sync(
    company_id: str, provider: str, *, ok: bool, error: str = "", count: int = 0,
) -> None:
    await db.integrations.update_one(
        {"company_id": company_id, "provider": provider},
        {"$set": {
            "last_sync_at": now_iso(),
            "last_sync_status": "ok" if ok else "error",
            "last_sync_count": count,
            "last_error": error if not ok else None,
        }},
    )


# -------------------- OAuth state (CSRF) --------------------
async def save_oauth_state(state: str, company_id: str, provider: str, user_id: str) -> None:
    await db.oauth_states.insert_one({
        "state": state,
        "company_id": company_id,
        "provider": provider,
        "user_id": user_id,
        "created_at": now_iso(),
        "expires_at": int(time.time()) + 600,
    })


async def consume_oauth_state(state: str) -> Optional[dict]:
    doc = await db.oauth_states.find_one_and_delete({"state": state}, projection={"_id": 0})
    if not doc:
        return None
    if doc.get("expires_at", 0) < int(time.time()):
        return None
    return doc
