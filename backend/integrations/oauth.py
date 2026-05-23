"""Shared OAuth2 plumbing — auth URL builder, code exchange, token refresh."""
import os
import time
import secrets
import base64
from typing import Optional
from urllib.parse import urlencode

import httpx

from .registry import get as get_provider


def build_authorize_url(provider: str, *, redirect_uri: str, state: str,
                        extra_scopes: Optional[str] = None) -> str:
    p = get_provider(provider)
    client_id = os.environ.get(p["env_client_id"], "")
    scopes = extra_scopes or p.get("scopes", "")
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": scopes,
        "state": state,
    }
    params.update(p.get("extra_params", {}))
    return f"{p['auth_url']}?{urlencode(params)}"


async def exchange_code(provider: str, *, code: str, redirect_uri: str) -> dict:
    """POST to provider token endpoint with auth-code grant. Returns the token JSON."""
    p = get_provider(provider)
    client_id = os.environ[p["env_client_id"]]
    client_secret = os.environ[p["env_client_secret"]]
    payload = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
    }
    headers = {"Accept": "application/json"}
    auth = None
    # Intuit / Microsoft accept basic auth or body creds; Google takes body creds.
    if provider == "quickbooks":
        auth = (client_id, client_secret)
    else:
        payload["client_id"] = client_id
        payload["client_secret"] = client_secret

    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(p["token_url"], data=payload, headers=headers, auth=auth)
    resp.raise_for_status()
    return resp.json()


async def refresh_access_token(provider: str, refresh_token: str) -> dict:
    p = get_provider(provider)
    client_id = os.environ[p["env_client_id"]]
    client_secret = os.environ[p["env_client_secret"]]
    payload = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    }
    auth = None
    if provider == "quickbooks":
        auth = (client_id, client_secret)
    else:
        payload["client_id"] = client_id
        payload["client_secret"] = client_secret
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(p["token_url"], data=payload, auth=auth)
    resp.raise_for_status()
    return resp.json()


async def zoom_s2s_token(account_id: str, client_id: str, client_secret: str) -> dict:
    """Server-to-Server OAuth — `grant_type=account_credentials`."""
    basic = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(
            "https://zoom.us/oauth/token",
            params={"grant_type": "account_credentials", "account_id": account_id},
            headers={"Authorization": f"Basic {basic}"},
        )
    resp.raise_for_status()
    return resp.json()


def new_state() -> str:
    return secrets.token_urlsafe(24)


def expires_at_from(payload: dict) -> int:
    return int(time.time()) + int(payload.get("expires_in") or 3600)
