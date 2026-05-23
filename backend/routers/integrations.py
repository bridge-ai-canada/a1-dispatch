"""Unified integrations router.

Endpoints:
- GET    /api/integrations                          → list catalog + connection status
- GET    /api/integrations/{provider}               → connection detail (secrets redacted)
- POST   /api/integrations/{provider}               → save api-key/api-token style config
- DELETE /api/integrations/{provider}               → disconnect (purge stored creds)
- POST   /api/integrations/{provider}/test          → live test the connection
- POST   /api/integrations/{provider}/sync          → trigger sync now
- GET    /api/integrations/{provider}/start         → begin OAuth2 (302 redirect)
- GET    /api/integrations/{provider}/callback      → OAuth2 callback handler
- GET    /api/integrations/sync-events              → recent sync log
"""
import os
import time
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from deps import db, get_current_user, logger, now_iso, log_activity
from integrations import store as integ_store
from integrations.registry import PROVIDERS, public_catalog, get as get_provider
from integrations.oauth import (
    build_authorize_url, exchange_code, new_state, expires_at_from, zoom_s2s_token,
)
from services import sync_engine

router = APIRouter()

ALLOWED_ROLES = {"owner", "office_manager", "super_admin"}


def _require_admin(user: dict) -> None:
    if user.get("role") not in ALLOWED_ROLES:
        raise HTTPException(status_code=403, detail="Owner / office_manager only")


def _redirect_uri(provider: str) -> str:
    base = os.environ.get("FRONTEND_URL") or os.environ.get("BACKEND_BASE_URL") or ""
    # If FRONTEND_URL is set we still want the backend's /api callback host.
    backend = os.environ.get("BACKEND_BASE_URL") or base
    return f"{backend.rstrip('/')}/api/integrations/{provider}/callback"


def _frontend_redirect(success: bool, provider: str) -> str:
    base = os.environ.get("FRONTEND_URL", "").rstrip("/")
    flag = "connected" if success else "error"
    return f"{base}/app/integrations?provider={provider}&result={flag}"


# -------------------- Catalog --------------------
@router.get("/integrations")
async def list_integrations(user: dict = Depends(get_current_user)):
    """Return catalog + per-tenant connection status (secrets redacted)."""
    _require_admin(user)
    connections = await integ_store.list_for_company(user["company_id"])
    by_provider = {c["provider"]: c for c in connections}
    catalog = public_catalog()
    out = []
    for prov in catalog:
        conn = by_provider.get(prov["key"])
        out.append({
            **prov,
            "connected": bool(conn and conn.get("status") == "connected"),
            "status": (conn or {}).get("status", "disconnected"),
            "connected_at": (conn or {}).get("connected_at"),
            "last_sync_at": (conn or {}).get("last_sync_at"),
            "last_sync_status": (conn or {}).get("last_sync_status"),
            "last_error": (conn or {}).get("last_error"),
            "data": (conn or {}).get("data", {}),  # already redacted
        })
    return {"integrations": out}


@router.get("/integrations/sync-events")
async def list_sync_events(user: dict = Depends(get_current_user), limit: int = 50):
    _require_admin(user)
    rows = await db.integration_sync_events.find(
        {"company_id": user["company_id"]}, {"_id": 0},
    ).sort("created_at", -1).limit(limit).to_list(limit)
    return {"events": rows}


# -------------------- Per-provider detail / save / disconnect --------------------
class IntegrationSaveIn(BaseModel):
    data: dict


@router.get("/integrations/{provider}")
async def get_integration(provider: str, user: dict = Depends(get_current_user)):
    _require_admin(user)
    if provider not in PROVIDERS:
        raise HTTPException(status_code=404, detail="Unknown provider")
    conn = await integ_store.list_for_company(user["company_id"])
    match = next((c for c in conn if c["provider"] == provider), None)
    return match or {"provider": provider, "status": "disconnected", "data": {}}


@router.post("/integrations/{provider}")
async def save_integration(
    provider: str,
    payload: IntegrationSaveIn,
    user: dict = Depends(get_current_user),
):
    """Save API key / token style configuration (non-OAuth providers)."""
    _require_admin(user)
    p = get_provider(provider) if provider in PROVIDERS else None
    if not p:
        raise HTTPException(status_code=404, detail="Unknown provider")
    if p["auth_mode"] not in ("api_key", "api_token", "server_key", "server_to_server"):
        raise HTTPException(
            status_code=400,
            detail="OAuth providers must connect via /integrations/{provider}/start",
        )
    doc = await integ_store.upsert(
        user["company_id"], provider,
        data=payload.data or {}, user_id=user["id"],
    )
    await log_activity(user, "integration.connected", "integration", provider, {})
    return {"ok": True, "provider": provider, "status": doc["status"]}


@router.delete("/integrations/{provider}")
async def disconnect_integration(provider: str, user: dict = Depends(get_current_user)):
    _require_admin(user)
    ok = await integ_store.delete(user["company_id"], provider)
    if ok:
        await log_activity(user, "integration.disconnected", "integration", provider, {})
    return {"ok": ok}


@router.post("/integrations/{provider}/test")
async def test_integration(provider: str, user: dict = Depends(get_current_user)):
    """Live ping per provider. Returns ok=True or descriptive error."""
    _require_admin(user)
    integ = await integ_store.get(user["company_id"], provider)
    if not integ:
        raise HTTPException(status_code=400, detail="Not connected")
    try:
        result = await _test_provider(provider, integ)
        return {"ok": True, **result}
    except httpx.HTTPStatusError as e:
        return {"ok": False, "error": f"HTTP {e.response.status_code}: {e.response.text[:200]}"}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


async def _test_provider(provider: str, integ: dict) -> dict:
    data = integ.get("data") or {}
    if provider == "quickbooks":
        token = data.get("access_token")
        realm = data.get("realmId")
        if not token or not realm:
            return {"detail": "OAuth not completed"}
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.get(
                f"https://quickbooks.api.intuit.com/v3/company/{realm}/companyinfo/{realm}",
                headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
            )
        r.raise_for_status()
        return {"detail": "QuickBooks responded OK"}
    if provider == "helcim":
        api_key = data.get("api_token") or os.environ.get("HELCIM_API_KEY", "")
        if not api_key:
            return {"detail": "API token missing"}
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.get(
                "https://api.helcim.com/v2/connect-test",
                headers={"api-token": api_key, "Accept": "application/json"},
            )
        return {"detail": f"Helcim returned {r.status_code}"}
    if provider == "stripe":
        sk = data.get("secret_key") or os.environ.get("STRIPE_API_KEY", "")
        if not sk:
            return {"detail": "Secret key missing"}
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.get(
                "https://api.stripe.com/v1/balance",
                headers={"Authorization": f"Bearer {sk}"},
            )
        r.raise_for_status()
        return {"detail": "Stripe responded OK"}
    if provider == "twilio":
        sid = data.get("account_sid", "")
        token = data.get("auth_token", "")
        if not (sid and token):
            return {"detail": "Credentials missing"}
        async with httpx.AsyncClient(timeout=15, auth=(sid, token)) as c:
            r = await c.get(f"https://api.twilio.com/2010-04-01/Accounts/{sid}.json")
        r.raise_for_status()
        return {"detail": "Twilio account active"}
    if provider == "zoom":
        try:
            t = await zoom_s2s_token(
                data.get("account_id", ""), data.get("client_id", ""), data.get("client_secret", ""),
            )
            return {"detail": "Zoom S2S token issued",
                    "scopes": t.get("scope", "")[:200]}
        except Exception as e:
            return {"detail": f"Zoom token failed: {e}"}
    if provider in ("google_calendar", "gmail"):
        token = data.get("access_token")
        if not token:
            return {"detail": "OAuth not completed"}
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.get(
                "https://www.googleapis.com/oauth2/v3/userinfo",
                headers={"Authorization": f"Bearer {token}"},
            )
        r.raise_for_status()
        return {"detail": f"Connected as {r.json().get('email', 'unknown')}"}
    if provider == "outlook_calendar":
        token = data.get("access_token")
        if not token:
            return {"detail": "OAuth not completed"}
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.get(
                "https://graph.microsoft.com/v1.0/me",
                headers={"Authorization": f"Bearer {token}"},
            )
        r.raise_for_status()
        return {"detail": f"Connected as {r.json().get('userPrincipalName', 'unknown')}"}
    if provider == "google_maps":
        key = data.get("server_key", "")
        if not key:
            return {"detail": "Server API key missing"}
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.get(
                "https://maps.googleapis.com/maps/api/distancematrix/json",
                params={"origins": "40.7128,-74.0060", "destinations": "40.7580,-73.9855", "key": key},
            )
        data_j = r.json()
        return {"detail": f"Google Maps responded: {data_j.get('status', '?')}"}
    return {"detail": "No test handler"}


# -------------------- Sync --------------------
@router.post("/integrations/{provider}/sync")
async def sync_now(provider: str, user: dict = Depends(get_current_user)):
    _require_admin(user)
    if provider not in PROVIDERS:
        raise HTTPException(status_code=404, detail="Unknown provider")
    return await sync_engine.sync_one(user["company_id"], provider)


# -------------------- OAuth flow --------------------
@router.get("/integrations/{provider}/start")
async def oauth_start(provider: str, user: dict = Depends(get_current_user)):
    _require_admin(user)
    if provider not in PROVIDERS:
        raise HTTPException(status_code=404, detail="Unknown provider")
    p = get_provider(provider)
    if p["auth_mode"] != "oauth2":
        raise HTTPException(status_code=400, detail="Not an OAuth provider")
    if not os.environ.get(p["env_client_id"]) or not os.environ.get(p["env_client_secret"]):
        raise HTTPException(
            status_code=400,
            detail=f"Platform OAuth client not configured "
                   f"(set {p['env_client_id']} + {p['env_client_secret']} in backend .env)",
        )
    state = new_state()
    await integ_store.save_oauth_state(state, user["company_id"], provider, user["id"])
    url = build_authorize_url(provider,
                              redirect_uri=_redirect_uri(provider), state=state)
    return RedirectResponse(url, status_code=302)


@router.get("/integrations/{provider}/callback")
async def oauth_callback(
    provider: str, request: Request,
    code: Optional[str] = None, state: Optional[str] = None,
    realmId: Optional[str] = Query(default=None),
    error: Optional[str] = None,
):
    if error or not code or not state:
        return RedirectResponse(_frontend_redirect(False, provider), status_code=302)
    st = await integ_store.consume_oauth_state(state)
    if not st or st.get("provider") != provider:
        return RedirectResponse(_frontend_redirect(False, provider), status_code=302)

    try:
        tokens = await exchange_code(
            provider, code=code, redirect_uri=_redirect_uri(provider),
        )
    except Exception as e:
        logger.error(f"OAuth exchange failed for {provider}: {e}")
        return RedirectResponse(_frontend_redirect(False, provider), status_code=302)

    data = {
        "access_token": tokens.get("access_token"),
        "refresh_token": tokens.get("refresh_token"),
        "scope": tokens.get("scope"),
        "token_type": tokens.get("token_type"),
        "expires_at": expires_at_from(tokens),
    }
    if realmId:
        data["realmId"] = realmId  # QBO returns it as a query param
    if tokens.get("id_token"):
        data["id_token"] = tokens["id_token"]

    await integ_store.upsert(
        st["company_id"], provider,
        data=data, user_id=st["user_id"],
    )
    # Fire-and-forget activity log (no actor object since we have no user obj here).
    await db.activity.insert_one({
        "id": "act_" + state[:10],
        "company_id": st["company_id"], "actor_id": st["user_id"],
        "action": "integration.connected", "target_type": "integration",
        "target_id": provider, "meta": {}, "created_at": now_iso(),
    })
    return RedirectResponse(_frontend_redirect(True, provider), status_code=302)
