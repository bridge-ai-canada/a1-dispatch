"""Financing provider adapter (Wisetack-style). Pre-wired stub.

Until WISETACK_API_KEY is set in backend/.env, this returns a deterministic
local quote computed from APR/term. Once the key is set, swap _local_quote()
for the real provider call in `get_prequal_quote`.
"""
import os
import httpx
from typing import Optional

WISETACK_API_KEY = os.environ.get("WISETACK_API_KEY", "")
WISETACK_BASE_URL = os.environ.get("WISETACK_BASE_URL", "https://api.wisetack.com")
WISETACK_MERCHANT_ID = os.environ.get("WISETACK_MERCHANT_ID", "")


def _local_quote(amount: float, apr: float, term_months: int) -> dict:
    if amount <= 0 or term_months <= 0:
        return {"monthly_payment": 0.0, "apr": apr, "term_months": term_months, "provider": "local"}
    r = (apr / 100.0) / 12.0
    if r <= 0:
        pmt = amount / term_months
    else:
        pmt = amount * (r * (1 + r) ** term_months) / ((1 + r) ** term_months - 1)
    return {
        "monthly_payment": round(pmt, 2),
        "apr": apr,
        "term_months": term_months,
        "provider": "local",
        "prequal_url": None,
    }


async def get_prequal_quote(amount: float, apr: float = 9.99, term_months: int = 24) -> dict:
    """Return a financing quote. Uses Wisetack when configured, local fallback otherwise."""
    if not (WISETACK_API_KEY and WISETACK_MERCHANT_ID):
        return _local_quote(amount, apr, term_months)
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.post(
                f"{WISETACK_BASE_URL}/v1/prequalification/offers",
                headers={"Authorization": f"Bearer {WISETACK_API_KEY}"},
                json={
                    "merchantId": WISETACK_MERCHANT_ID,
                    "amount": round(amount, 2),
                },
            )
            r.raise_for_status()
            data = r.json()
            # Normalize provider response (best-effort)
            offer = (data.get("offers") or [{}])[0]
            return {
                "monthly_payment": float(offer.get("monthlyPayment", 0) or 0),
                "apr": float(offer.get("apr", apr) or apr),
                "term_months": int(offer.get("termMonths", term_months) or term_months),
                "provider": "wisetack",
                "prequal_url": offer.get("applyUrl"),
            }
    except Exception:
        return _local_quote(amount, apr, term_months)


async def create_application_link(amount: float, customer: Optional[dict] = None) -> Optional[str]:
    """Generate a Wisetack apply link. Returns None when not configured."""
    if not (WISETACK_API_KEY and WISETACK_MERCHANT_ID):
        return None
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.post(
                f"{WISETACK_BASE_URL}/v1/loans/applications",
                headers={"Authorization": f"Bearer {WISETACK_API_KEY}"},
                json={
                    "merchantId": WISETACK_MERCHANT_ID,
                    "amount": round(amount, 2),
                    "customer": customer or {},
                },
            )
            r.raise_for_status()
            return r.json().get("applyUrl")
    except Exception:
        return None
