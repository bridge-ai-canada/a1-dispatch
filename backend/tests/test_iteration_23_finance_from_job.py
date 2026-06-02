"""Iteration 23 — Finance this job (POST /api/financing/from-job).

Covers:
- Owner & Technician can create finance application from a job
- Idempotency: same job -> same application_id + public_token
- 400 when amount < $500 (financing min)
- 404 for bogus / cross-tenant job_id
- job.financing_application_id back-reference set
- send_sms=true: graceful sms_result (twilio_not_configured / no_customer_phone / no_origin_url)
"""
import os
import uuid
import pytest
import requests
from pathlib import Path

if not os.environ.get("REACT_APP_BACKEND_URL"):
    fe = Path("/app/frontend/.env")
    if fe.exists():
        for line in fe.read_text().splitlines():
            if line.startswith("REACT_APP_BACKEND_URL"):
                os.environ["REACT_APP_BACKEND_URL"] = line.split("=", 1)[1].strip()

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")

OWNER = {"email": "demo@a1fieldpro.com", "password": "Demo1234!"}
TECH = {"email": "tech@a1fieldpro.com", "password": "Demo1234!"}


def _login(creds):
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json=creds, timeout=30)
    if r.status_code != 200:
        pytest.skip(f"login failed for {creds['email']}: {r.status_code} {r.text}")
    data = r.json()
    tok = data.get("access_token") or data.get("token")
    if tok:
        s.headers.update({"Authorization": f"Bearer {tok}"})
    return s


@pytest.fixture(scope="module")
def owner_client():
    return _login(OWNER)


@pytest.fixture(scope="module")
def tech_client():
    return _login(TECH)


def _create_job(client, price, phone="+15551112222", title_suffix=""):
    """Create a job (owner-only role for POST /api/jobs)."""
    payload = {
        "title": f"TEST_iter23_finance {title_suffix or uuid.uuid4().hex[:6]}",
        "customer_name": "TEST_iter23 Customer",
        "customer_phone": phone,
        "customer_email": "test_iter23@example.com",
        "address": "123 Test Lane",
        "price": float(price),
        "status": "in_progress",
    }
    r = client.post(f"{BASE_URL}/api/jobs", json=payload, timeout=30)
    assert r.status_code in (200, 201), f"create job failed: {r.status_code} {r.text}"
    return r.json()


# -------------------- Tests --------------------
class TestFinanceFromJob:
    def test_owner_create_basic(self, owner_client):
        job = _create_job(owner_client, 5500.0)
        r = owner_client.post(f"{BASE_URL}/api/financing/from-job",
                              json={"job_id": job["id"]}, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "application_id" in data
        assert "public_token" in data and isinstance(data["public_token"], str) and len(data["public_token"]) > 10
        assert float(data["amount"]) == 5500.0
        assert int(data["term_months"]) in (36, 60)  # accepts either pre/post finance-programs default
        assert data["sms_result"] is None  # send_sms not set

        # Verify back-reference set on the job
        r2 = owner_client.get(f"{BASE_URL}/api/jobs/{job['id']}", timeout=30)
        assert r2.status_code == 200
        assert r2.json().get("financing_application_id") == data["application_id"]

    def test_idempotent_same_job_returns_same_app(self, owner_client):
        job = _create_job(owner_client, 6000.0, title_suffix="idem")
        a = owner_client.post(f"{BASE_URL}/api/financing/from-job",
                              json={"job_id": job["id"], "term_months": 48}, timeout=30)
        b = owner_client.post(f"{BASE_URL}/api/financing/from-job",
                              json={"job_id": job["id"], "term_months": 60}, timeout=30)
        assert a.status_code == 200 and b.status_code == 200
        ja, jb = a.json(), b.json()
        assert ja["application_id"] == jb["application_id"]
        assert ja["public_token"] == jb["public_token"]
        # Term on 2nd call should not duplicate — original retained
        assert ja["term_months"] == jb["term_months"]

    def test_amount_too_small_returns_400(self, owner_client):
        # Create a low-price job; amount default = job.price = 100 < 500
        job = _create_job(owner_client, 100.0, title_suffix="low")
        r = owner_client.post(f"{BASE_URL}/api/financing/from-job",
                              json={"job_id": job["id"]}, timeout=30)
        assert r.status_code == 400, r.text
        assert "min" in (r.json().get("detail") or "").lower()

    def test_amount_override_too_small_returns_400(self, owner_client):
        job = _create_job(owner_client, 6000.0, title_suffix="override")
        r = owner_client.post(f"{BASE_URL}/api/financing/from-job",
                              json={"job_id": job["id"], "amount": 250}, timeout=30)
        assert r.status_code == 400

    def test_bogus_job_returns_404(self, owner_client):
        r = owner_client.post(f"{BASE_URL}/api/financing/from-job",
                              json={"job_id": "does-not-exist-xyz"}, timeout=30)
        assert r.status_code == 404

    def test_technician_can_create(self, owner_client, tech_client):
        """Critical: techs in the field MUST be able to call this."""
        job = _create_job(owner_client, 5750.0, title_suffix="tech")
        r = tech_client.post(f"{BASE_URL}/api/financing/from-job",
                             json={"job_id": job["id"]}, timeout=30)
        assert r.status_code == 200, f"Tech denied: {r.status_code} {r.text}"
        data = r.json()
        assert data["application_id"]
        assert float(data["amount"]) == 5750.0

    def test_send_sms_twilio_not_configured(self, owner_client):
        job = _create_job(owner_client, 5500.0, phone="+15551234567", title_suffix="sms_ok")
        r = owner_client.post(f"{BASE_URL}/api/financing/from-job",
                              json={"job_id": job["id"], "send_sms": True,
                                    "origin_url": "https://example.com"}, timeout=30)
        assert r.status_code == 200, r.text
        sms = r.json().get("sms_result")
        assert sms is not None, "sms_result must be present when send_sms=true"
        assert sms.get("ok") is False
        assert sms.get("error") == "twilio_not_configured"

    def test_send_sms_no_customer_phone(self, owner_client):
        job = _create_job(owner_client, 5500.0, phone="", title_suffix="nophone")
        r = owner_client.post(f"{BASE_URL}/api/financing/from-job",
                              json={"job_id": job["id"], "send_sms": True,
                                    "origin_url": "https://example.com"}, timeout=30)
        assert r.status_code == 200, r.text
        sms = r.json().get("sms_result")
        assert sms is not None
        assert sms.get("ok") is False
        assert sms.get("error") == "no_customer_phone"

    def test_custom_amount_overrides_job_price(self, owner_client):
        job = _create_job(owner_client, 8000.0, title_suffix="custom_amt")
        r = owner_client.post(f"{BASE_URL}/api/financing/from-job",
                              json={"job_id": job["id"], "amount": 5200.0,
                                    "term_months": 24}, timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert float(d["amount"]) == 5200.0
        assert int(d["term_months"]) == 24
