"""Twilio SMS service.

Gracefully no-ops when TWILIO_ACCOUNT_SID/AUTH_TOKEN/FROM_NUMBER are missing.
Use `is_enabled()` to gate UI / scheduling logic.
"""
import logging
import os
import re
from typing import Optional

logger = logging.getLogger("a1fieldpro.sms")

ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID", "").strip()
AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN", "").strip()
FROM_NUMBER = os.environ.get("TWILIO_FROM_NUMBER", "").strip()

_client = None


def is_enabled() -> bool:
    return bool(ACCOUNT_SID and AUTH_TOKEN and FROM_NUMBER)


def _get_client():
    global _client
    if _client is None and is_enabled():
        from twilio.rest import Client  # lazy import
        _client = Client(ACCOUNT_SID, AUTH_TOKEN)
    return _client


def normalize_phone(raw: str) -> Optional[str]:
    """Return E.164 phone or None. Accepts US-style or already-E.164."""
    if not raw:
        return None
    s = re.sub(r"[^\d+]", "", raw)
    if not s:
        return None
    if s.startswith("+"):
        return s if len(s) >= 8 else None
    digits = re.sub(r"\D", "", s)
    if len(digits) == 10:
        return "+1" + digits
    if len(digits) == 11 and digits.startswith("1"):
        return "+" + digits
    return None


def send_sms(to: str, body: str) -> dict:
    """Send an SMS. Returns {ok, sid|error, skipped?}.
    Synchronous (Twilio SDK uses urllib3 under the hood) — fine for our usage."""
    to_norm = normalize_phone(to)
    if not to_norm:
        return {"ok": False, "error": "invalid_phone", "to": to}
    if not is_enabled():
        logger.info(f"[sms.skipped] {to_norm}: {body[:80]}")
        return {"ok": False, "skipped": True, "error": "twilio_not_configured"}
    try:
        client = _get_client()
        msg = client.messages.create(body=body, from_=FROM_NUMBER, to=to_norm)
        return {"ok": True, "sid": msg.sid, "to": to_norm}
    except Exception as e:
        logger.error(f"Twilio send failed to {to_norm}: {e}")
        return {"ok": False, "error": str(e), "to": to_norm}
