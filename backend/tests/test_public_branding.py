"""Tests for new public branding endpoints (iteration 21)."""
import os
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://a1-dispatch.preview.emergentagent.com").rstrip("/")
DEMO_COMPANY_ID = "8036dcfb-682a-4142-8b91-9ee19529eb09"


def test_public_branding_includes_logo_and_favicon_url_fields():
    r = requests.get(f"{BASE_URL}/api/public/branding", params={"company_id": DEMO_COMPANY_ID}, timeout=15)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "logo_url" in data, "logo_url field missing"
    assert "favicon_url" in data, "favicon_url field missing"
    # value may be None if no logo is uploaded
    if data["logo_url"]:
        assert data["logo_url"].startswith(f"/api/public/branding/asset/{DEMO_COMPANY_ID}/logo"), data["logo_url"]
    if data["favicon_url"]:
        assert data["favicon_url"].startswith(f"/api/public/branding/asset/{DEMO_COMPANY_ID}/favicon")


def test_public_branding_unknown_company_returns_friendly_payload():
    r = requests.get(f"{BASE_URL}/api/public/branding", params={"company_id": "no-such-id"}, timeout=15)
    # endpoint should either 404 or return defaults
    assert r.status_code in (200, 404)


def test_public_asset_invalid_kind_returns_404():
    r = requests.get(f"{BASE_URL}/api/public/branding/asset/{DEMO_COMPANY_ID}/evil", timeout=15)
    assert r.status_code == 404


def test_public_asset_unknown_company_returns_404():
    r = requests.get(f"{BASE_URL}/api/public/branding/asset/unknown-company-id/logo", timeout=15)
    assert r.status_code == 404


def test_public_asset_logo_when_present():
    """If demo company has a logo, asset endpoint should return 200 with image bytes (no auth).
    If no logo uploaded, endpoint returns 404 (acceptable)."""
    branding = requests.get(f"{BASE_URL}/api/public/branding", params={"company_id": DEMO_COMPANY_ID}, timeout=15).json()
    logo_url = branding.get("logo_url")
    if not logo_url:
        pytest.skip("Demo company has no logo uploaded; skipping live asset fetch")
    r = requests.get(f"{BASE_URL}{logo_url}", timeout=15)
    assert r.status_code == 200, f"expected 200 got {r.status_code}: {r.text[:200]}"
    assert len(r.content) > 0
    ct = r.headers.get("content-type", "")
    assert ct.startswith("image/") or ct == "application/octet-stream", ct


def test_pricing_plans_returns_full_catalog():
    """5-tier catalog (basic / team / business / pro / enterprise)."""
    r = requests.get(f"{BASE_URL}/api/subscription/plans", timeout=15)
    assert r.status_code == 200
    plans = r.json()
    assert isinstance(plans, list)
    assert len(plans) == 5, f"expected 5 plans, got {len(plans)}"
    keys = {p["key"] for p in plans}
    assert keys == {"basic", "team", "business", "pro", "enterprise"}
