"""Iteration 8 regression + new behavior tests.

Covers:
- Password strength enforcement on register/reset
- BrandingIn hex color pattern
- Checkout email_verified gate (403)
- Activity events on job create/update
- Public booking response now contains full job object
- Smoke regression for core flows
"""
import os
import uuid
import time
import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"

DEMO_EMAIL = "demo@a1fieldpro.com"
DEMO_PASSWORD = "Demo1234!"


# ---------------- fixtures ----------------
@pytest.fixture(scope="session")
def demo_token():
    r = requests.post(f"{API}/auth/login",
                      json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD},
                      timeout=30)
    assert r.status_code == 200, f"demo login failed: {r.status_code} {r.text}"
    return r.json()["token"]


@pytest.fixture(scope="session")
def demo_headers(demo_token):
    return {"Authorization": f"Bearer {demo_token}"}


@pytest.fixture(scope="session")
def demo_me(demo_headers):
    r = requests.get(f"{API}/auth/me", headers=demo_headers, timeout=30)
    assert r.status_code == 200
    return r.json()


@pytest.fixture(scope="session")
def company_id(demo_me):
    return demo_me.get("company", {}).get("id") or demo_me.get("user", {}).get("company_id")


# ---------------- NEW: password strength ----------------
class TestPasswordStrength:
    def _register_payload(self, pw: str) -> dict:
        uniq = uuid.uuid4().hex[:8]
        return {
            "company_name": f"TEST_PW_{uniq}",
            "industry": "HVAC",
            "name": f"PW Tester {uniq}",
            "email": f"TEST_pw_{uniq}@example.com",
            "password": pw,
        }

    def test_register_short_password_422(self):
        r = requests.post(f"{API}/auth/register",
                          json=self._register_payload("Ab1"), timeout=30)
        assert r.status_code == 422, r.text

    def test_register_no_letter_password_422(self):
        r = requests.post(f"{API}/auth/register",
                          json=self._register_payload("12345678"), timeout=30)
        assert r.status_code == 422, r.text

    def test_register_no_digit_password_422(self):
        r = requests.post(f"{API}/auth/register",
                          json=self._register_payload("abcdefgh"), timeout=30)
        assert r.status_code == 422, r.text

    def test_register_valid_password_200(self):
        r = requests.post(f"{API}/auth/register",
                          json=self._register_payload("Demo1234!"), timeout=60)
        assert r.status_code in (200, 201), r.text
        body = r.json()
        assert "token" in body and "user" in body

    def test_reset_invalid_password_422(self):
        # token can be anything — Pydantic validates before token lookup
        r = requests.post(f"{API}/auth/reset",
                          json={"token": "deadbeef", "new_password": "short"},
                          timeout=30)
        assert r.status_code == 422, r.text


# ---------------- NEW: BrandingIn hex pattern ----------------
class TestBrandingHexPattern:
    def test_patch_branding_invalid_word(self, demo_headers):
        r = requests.patch(f"{API}/companies/me",
                           json={"primary_color": "red"},
                           headers=demo_headers, timeout=30)
        assert r.status_code == 422, r.text

    def test_patch_branding_short_hex(self, demo_headers):
        r = requests.patch(f"{API}/companies/me",
                           json={"primary_color": "#abc"},
                           headers=demo_headers, timeout=30)
        assert r.status_code == 422, r.text

    def test_patch_branding_invalid_chars(self, demo_headers):
        r = requests.patch(f"{API}/companies/me",
                           json={"accent_color": "#GGGGGG"},
                           headers=demo_headers, timeout=30)
        assert r.status_code == 422, r.text

    def test_patch_branding_valid_hex(self, demo_headers):
        r = requests.patch(f"{API}/companies/me",
                           json={"primary_color": "#1D4ED8",
                                 "accent_color": "#DC2626"},
                           headers=demo_headers, timeout=30)
        assert r.status_code == 200, r.text
        body = r.json()
        branding = body.get("branding") or {}
        assert branding.get("primary_color", "").lower() == "#1d4ed8"


# ---------------- NEW: Checkout email_verified gate ----------------
class TestCheckoutEmailGate:
    def test_checkout_unverified_user_403(self):
        """Register a fresh user (email_verified=False by default) and try checkout."""
        uniq = uuid.uuid4().hex[:8]
        reg = requests.post(f"{API}/auth/register", json={
            "company_name": f"TEST_UNV_{uniq}",
            "industry": "HVAC",
            "name": f"Unverified {uniq}",
            "email": f"TEST_unv_{uniq}@example.com",
            "password": "Demo1234!",
        }, timeout=60)
        assert reg.status_code in (200, 201), reg.text
        body = reg.json()
        tok = body.get("token")
        assert tok, f"no token in register response: {body}"
        h = {"Authorization": f"Bearer {tok}"}

        # Create a priced job first (so we hit the email_verified check, not 'no price')
        jr = requests.post(f"{API}/jobs", json={
            "title": "TEST_UNV checkout job", "price": 100.0,
        }, headers=h, timeout=30)
        assert jr.status_code == 200, jr.text
        job_id = jr.json()["id"]

        # Attempt checkout
        cr = requests.post(f"{API}/payments/checkout", json={
            "job_id": job_id, "origin_url": BASE_URL,
        }, headers=h, timeout=30)
        assert cr.status_code == 403, f"expected 403 got {cr.status_code}: {cr.text}"
        detail = cr.json().get("detail", "")
        assert "Verify your email" in detail, detail

    def test_checkout_verified_owner_returns_url(self, demo_headers, demo_me):
        # Demo owner is email_verified=True
        # Create job with price
        jr = requests.post(f"{API}/jobs", json={
            "title": "TEST_VER checkout job", "price": 50.0,
        }, headers=demo_headers, timeout=30)
        assert jr.status_code == 200
        job_id = jr.json()["id"]

        cr = requests.post(f"{API}/payments/checkout", json={
            "job_id": job_id, "origin_url": BASE_URL,
        }, headers=demo_headers, timeout=60)
        # Should succeed (200) with a Stripe URL OR fail with 500 if Stripe key bad — but per spec demo is verified
        assert cr.status_code == 200, f"checkout failed for verified user: {cr.status_code} {cr.text}"
        data = cr.json()
        assert "url" in data and data["url"].startswith("http")
        assert "session_id" in data


# ---------------- NEW: Activity events on job create/update ----------------
class TestJobActivityEvents:
    def test_jobs_created_activity_logged(self, demo_headers):
        title = f"TEST_ACT_CREATE_{uuid.uuid4().hex[:6]}"
        r = requests.post(f"{API}/jobs",
                          json={"title": title, "status": "unscheduled"},
                          headers=demo_headers, timeout=30)
        assert r.status_code == 200
        job_id = r.json()["id"]

        time.sleep(0.5)
        a = requests.get(f"{API}/activity",
                         params={"action": "jobs.created", "limit": 50},
                         headers=demo_headers, timeout=30)
        assert a.status_code == 200
        items = a.json() if isinstance(a.json(), list) else a.json().get("items", [])
        # find our event
        match = next((x for x in items if x.get("target_id") == job_id), None)
        assert match, f"no jobs.created activity for {job_id}; sample={items[:2]}"
        assert match["action"] == "jobs.created"
        meta = match.get("meta") or {}
        assert meta.get("title") == title
        assert "status" in meta

    @pytest.mark.parametrize("new_status", ["scheduled", "in_progress", "completed", "cancelled"])
    def test_jobs_status_change_activity_logged(self, demo_headers, new_status):
        title = f"TEST_ACT_{new_status}_{uuid.uuid4().hex[:6]}"
        r = requests.post(f"{API}/jobs",
                          json={"title": title, "status": "unscheduled"},
                          headers=demo_headers, timeout=30)
        assert r.status_code == 200
        job_id = r.json()["id"]

        u = requests.patch(f"{API}/jobs/{job_id}",
                           json={"status": new_status},
                           headers=demo_headers, timeout=30)
        assert u.status_code == 200, u.text

        time.sleep(0.5)
        a = requests.get(f"{API}/activity",
                         params={"action": f"jobs.{new_status}", "limit": 50},
                         headers=demo_headers, timeout=30)
        assert a.status_code == 200
        items = a.json() if isinstance(a.json(), list) else a.json().get("items", [])
        match = next((x for x in items if x.get("target_id") == job_id), None)
        assert match, f"no jobs.{new_status} activity for {job_id}"
        assert match.get("meta", {}).get("title") == title


# ---------------- NEW: Public booking returns full job ----------------
class TestPublicBookingFullJob:
    def test_public_booking_returns_job_object(self, company_id):
        uniq = uuid.uuid4().hex[:6]
        r = requests.post(f"{API}/public/companies/{company_id}/bookings", json={
            "name": f"TEST_BK_{uniq}",
            "phone": f"+155500{uniq}",
            "email": f"TEST_bk_{uniq}@example.com",
            "address": "123 Test St",
            "job_type": "HVAC",
            "description": "Booking widget test",
        }, timeout=30)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("ok") is True
        assert "job_id" in body
        assert "company_name" in body
        assert "job" in body, f"missing 'job' key: {body}"
        job = body["job"]
        assert job.get("status") == "unscheduled"
        assert job.get("source") == "booking_widget"
        assert job.get("customer_email") == f"TEST_bk_{uniq}@example.com"
        assert job.get("id") == body["job_id"]


# ---------------- REGRESSION smoke ----------------
class TestRegressionSmoke:
    def test_login_demo(self, demo_token):
        assert demo_token

    def test_auth_me(self, demo_headers):
        r = requests.get(f"{API}/auth/me", headers=demo_headers, timeout=30)
        assert r.status_code == 200
        body = r.json()
        assert body.get("user", {}).get("email") == DEMO_EMAIL

    def test_list_jobs(self, demo_headers):
        r = requests.get(f"{API}/jobs", headers=demo_headers, timeout=30)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_list_customers_paginated(self, demo_headers):
        r = requests.get(f"{API}/customers", headers=demo_headers, timeout=30)
        assert r.status_code == 200
        body = r.json()
        # paginated shape per iteration_7
        assert "items" in body
        assert "total" in body

    def test_dashboard_stats(self, demo_headers):
        r = requests.get(f"{API}/dashboard/stats", headers=demo_headers, timeout=30)
        assert r.status_code == 200
        body = r.json()
        assert "totals" in body

    def test_activity_feed(self, demo_headers):
        r = requests.get(f"{API}/activity", params={"limit": 5},
                         headers=demo_headers, timeout=30)
        assert r.status_code == 200

    def test_sessions_list(self, demo_headers):
        r = requests.get(f"{API}/sessions", headers=demo_headers, timeout=30)
        assert r.status_code == 200

    def test_users_list(self, demo_headers):
        r = requests.get(f"{API}/users", headers=demo_headers, timeout=30)
        assert r.status_code == 200

    def test_invoice_pdf(self, demo_headers):
        # create a job then get its invoice
        r = requests.post(f"{API}/jobs",
                          json={"title": "TEST_INV_pdf", "price": 25.0},
                          headers=demo_headers, timeout=30)
        assert r.status_code == 200
        jid = r.json()["id"]
        p = requests.get(f"{API}/jobs/{jid}/invoice.pdf", headers=demo_headers, timeout=30)
        assert p.status_code == 200
        assert p.headers.get("content-type", "").startswith("application/pdf")
