"""Phase 2 tests: White-label branding + Invoice PDF"""
import io
import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"

OWNER = {"email": "demo@a1fieldpro.com", "password": "Demo1234!"}
TECH = {"email": "tech@a1fieldpro.com", "password": "Demo1234!"}


def _login(creds):
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json=creds, timeout=15)
    assert r.status_code == 200, r.text
    return s


@pytest.fixture(scope="session")
def owner_session():
    return _login(OWNER)


@pytest.fixture(scope="session")
def tech_session():
    return _login(TECH)


# ---------- Companies / Branding ----------
def test_companies_me_returns_company(owner_session):
    r = owner_session.get(f"{API}/companies/me", timeout=10)
    assert r.status_code == 200
    body = r.json()
    assert body.get("name")
    assert "_id" not in body


def test_patch_branding_owner(owner_session):
    payload = {"primary_color": "#0EA5E9", "accent_color": "#F59E0B"}
    r = owner_session.patch(f"{API}/companies/me", json=payload, timeout=10)
    assert r.status_code == 200, r.text
    body = r.json()
    branding = body.get("branding") or {}
    assert branding.get("primary_color") == "#0EA5E9"
    assert branding.get("accent_color") == "#F59E0B"
    # Verify persistence via GET
    r2 = owner_session.get(f"{API}/companies/me", timeout=10)
    assert r2.status_code == 200
    b2 = (r2.json().get("branding") or {})
    assert b2.get("primary_color") == "#0EA5E9"
    assert b2.get("accent_color") == "#F59E0B"


def test_patch_branding_non_owner_forbidden(tech_session):
    r = tech_session.patch(f"{API}/companies/me", json={"primary_color": "#000000"}, timeout=10)
    assert r.status_code == 403


def test_patch_branding_unauthenticated():
    r = requests.patch(f"{API}/companies/me", json={"primary_color": "#000000"}, timeout=10)
    assert r.status_code == 401


def _make_png_bytes():
    # 1x1 PNG
    return bytes.fromhex(
        "89504E470D0A1A0A0000000D49484452000000010000000108060000001F15C489"
        "0000000A49444154789C6300010000000500010D0A2DB40000000049454E44AE426082"
    )


def test_upload_logo_owner(owner_session):
    files = {"file": ("logo.png", io.BytesIO(_make_png_bytes()), "image/png")}
    r = owner_session.post(f"{API}/companies/me/logo", files=files, timeout=20)
    assert r.status_code == 200, r.text
    body = r.json()
    # Endpoint returns {"path": "..."} per current implementation
    path = body.get("path") or (body.get("branding") or {}).get("logo_path")
    assert path, f"expected path in response, got {body}"
    assert "branding/" in path
    # Verify persistence via GET /companies/me
    me_co = owner_session.get(f"{API}/companies/me", timeout=10).json()
    assert (me_co.get("branding") or {}).get("logo_path") == path


def test_upload_logo_non_owner_forbidden(tech_session):
    files = {"file": ("logo.png", io.BytesIO(_make_png_bytes()), "image/png")}
    r = tech_session.post(f"{API}/companies/me/logo", files=files, timeout=20)
    assert r.status_code == 403


# ---------- Invoice PDF ----------
def test_invoice_pdf_unauthenticated():
    # Pick any job id (won't reach due to auth)
    r = requests.get(f"{API}/jobs/nonexistent/invoice.pdf", timeout=10)
    assert r.status_code == 401


def test_invoice_pdf_returns_pdf(owner_session):
    jobs = owner_session.get(f"{API}/jobs", timeout=10).json()
    assert jobs
    job_id = jobs[0]["id"]
    r = owner_session.get(f"{API}/jobs/{job_id}/invoice.pdf", timeout=30)
    assert r.status_code == 200, r.text[:300]
    ctype = r.headers.get("content-type", "")
    assert "application/pdf" in ctype, f"Expected pdf, got {ctype}"
    assert r.content[:4] == b"%PDF", "Body should start with %PDF magic bytes"
    assert len(r.content) > 500


def test_invoice_pdf_paid_stamp(owner_session):
    # Create a paid job and ensure PDF still generates
    r = owner_session.post(f"{API}/jobs", json={
        "title": "TEST_PaidInvoice", "price": 500.0, "paid": True,
        "customer_name": "TEST Customer", "address": "1 Test",
    }, timeout=10)
    assert r.status_code == 200, r.text
    jid = r.json()["id"]
    try:
        r = owner_session.get(f"{API}/jobs/{jid}/invoice.pdf", timeout=30)
        assert r.status_code == 200
        assert "application/pdf" in r.headers.get("content-type", "")
        assert r.content[:4] == b"%PDF"
    finally:
        owner_session.delete(f"{API}/jobs/{jid}", timeout=10)


def test_invoice_pdf_cross_tenant_404(owner_session):
    # Register a new tenant, create a job there, ensure owner can't fetch its PDF
    email = f"TEST_{uuid.uuid4().hex[:8]}@iso.com"
    s = requests.Session()
    rr = s.post(f"{API}/auth/register", json={
        "company_name": "TEST_IsoBrand", "industry": "HVAC",
        "name": "Iso", "email": email, "password": "Demo1234!",
    }, timeout=15)
    assert rr.status_code == 200
    r = s.post(f"{API}/jobs", json={"title": "TEST_IsoJob", "price": 10.0}, timeout=10)
    other_jid = r.json()["id"]
    # Owner from main tenant tries to access
    r = owner_session.get(f"{API}/jobs/{other_jid}/invoice.pdf", timeout=15)
    assert r.status_code == 404
