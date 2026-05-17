"""A1 Field Pro backend integration tests"""
import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://a1-dispatch.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

OWNER = {"email": "demo@a1fieldpro.com", "password": "Demo1234!"}
DISP = {"email": "dispatcher@a1fieldpro.com", "password": "Demo1234!"}
TECH = {"email": "tech@a1fieldpro.com", "password": "Demo1234!"}


def _login(creds):
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json=creds, timeout=15)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    return s, r.json()


@pytest.fixture(scope="session")
def owner_session():
    s, _ = _login(OWNER)
    return s


@pytest.fixture(scope="session")
def tech_session():
    s, _ = _login(TECH)
    return s


# ---------- Auth ----------
def test_health():
    r = requests.get(f"{API}/", timeout=10)
    assert r.status_code == 200
    assert r.json().get("status") == "ok"


def test_login_owner_sets_cookie():
    s, data = _login(OWNER)
    assert "access_token" in s.cookies
    assert data["user"]["email"] == OWNER["email"]
    assert data["user"]["role"] == "owner"
    assert "token" in data


def test_login_invalid():
    r = requests.post(f"{API}/auth/login", json={"email": "demo@a1fieldpro.com", "password": "wrong"}, timeout=10)
    assert r.status_code == 401


def test_me_returns_user_and_company(owner_session):
    r = owner_session.get(f"{API}/auth/me", timeout=10)
    assert r.status_code == 200
    body = r.json()
    assert body["user"]["email"] == OWNER["email"]
    assert body["company"]["name"]


def test_me_unauthenticated():
    r = requests.get(f"{API}/auth/me", timeout=10)
    assert r.status_code == 401


def test_logout_clears_cookie():
    s, _ = _login(OWNER)
    r = s.post(f"{API}/auth/logout", timeout=10)
    assert r.status_code == 200
    # Cookie should be cleared - subsequent /me should 401
    r2 = requests.get(f"{API}/auth/me", cookies={}, timeout=10)
    assert r2.status_code == 401


def test_register_creates_company_and_owner():
    email = f"test_{uuid.uuid4().hex[:8]}@example.com"
    s = requests.Session()
    r = s.post(f"{API}/auth/register", json={
        "company_name": "TEST_Co", "industry": "HVAC",
        "name": "Test Owner", "email": email, "password": "Demo1234!",
    }, timeout=15)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["user"]["email"] == email.lower()
    assert body["user"]["role"] == "owner"
    assert "access_token" in s.cookies
    me = s.get(f"{API}/auth/me", timeout=10)
    assert me.status_code == 200


# ---------- Jobs ----------
def test_list_jobs_seeded(owner_session):
    r = owner_session.get(f"{API}/jobs", timeout=10)
    assert r.status_code == 200
    jobs = r.json()
    assert isinstance(jobs, list)
    assert len(jobs) >= 4
    assert all("_id" not in j for j in jobs)
    assert all(j.get("company_id") for j in jobs)


def test_jobs_mine_for_technician(tech_session):
    r = tech_session.get(f"{API}/jobs", params={"mine": "true"}, timeout=10)
    assert r.status_code == 200
    jobs = r.json()
    assert len(jobs) >= 1
    tech_me = tech_session.get(f"{API}/auth/me", timeout=10).json()
    tech_id = tech_me["user"]["id"]
    assert all(j.get("assigned_to") == tech_id for j in jobs)


def test_job_crud(owner_session):
    payload = {
        "title": "TEST_Job", "description": "test",
        "customer_name": "TEST Customer", "address": "123 Test St",
        "job_type": "HVAC", "price": 250.0, "status": "unscheduled",
    }
    r = owner_session.post(f"{API}/jobs", json=payload, timeout=10)
    assert r.status_code == 200, r.text
    job = r.json()
    jid = job["id"]
    assert job["title"] == "TEST_Job"
    assert job["price"] == 250.0

    # GET
    r = owner_session.get(f"{API}/jobs/{jid}", timeout=10)
    assert r.status_code == 200 and r.json()["id"] == jid

    # PATCH
    r = owner_session.patch(f"{API}/jobs/{jid}", json={"status": "scheduled", "price": 275.0}, timeout=10)
    assert r.status_code == 200
    assert r.json()["status"] == "scheduled"
    assert r.json()["price"] == 275.0

    # DELETE
    r = owner_session.delete(f"{API}/jobs/{jid}", timeout=10)
    assert r.status_code == 200
    r = owner_session.get(f"{API}/jobs/{jid}", timeout=10)
    assert r.status_code == 404


def test_technician_cannot_delete_job(tech_session, owner_session):
    # owner creates job
    r = owner_session.post(f"{API}/jobs", json={"title": "TEST_NoDelete", "price": 10.0}, timeout=10)
    jid = r.json()["id"]
    # tech attempts delete
    r = tech_session.delete(f"{API}/jobs/{jid}", timeout=10)
    assert r.status_code == 403
    owner_session.delete(f"{API}/jobs/{jid}", timeout=10)  # cleanup


# ---------- Dashboard ----------
def test_dashboard_stats(owner_session):
    r = owner_session.get(f"{API}/dashboard/stats", timeout=10)
    assert r.status_code == 200
    d = r.json()
    for k in ["jobs_today", "revenue_today", "active_technicians", "completion_rate", "totals"]:
        assert k in d
    assert isinstance(d["totals"], dict)
    assert d["active_technicians"] >= 1


# ---------- Team ----------
def test_team_list(owner_session):
    r = owner_session.get(f"{API}/team", timeout=10)
    assert r.status_code == 200
    members = r.json()
    emails = [m["email"] for m in members]
    assert OWNER["email"] in emails and TECH["email"] in emails


def test_team_create_and_delete(owner_session):
    email = f"TEST_{uuid.uuid4().hex[:6]}@a1fieldpro.com"
    r = owner_session.post(f"{API}/team", json={
        "name": "TEST Tech", "email": email, "password": "Demo1234!", "role": "technician"
    }, timeout=10)
    assert r.status_code == 200, r.text
    uid = r.json()["id"]
    r = owner_session.delete(f"{API}/team/{uid}", timeout=10)
    assert r.status_code == 200


def test_tech_cannot_create_team(tech_session):
    r = tech_session.post(f"{API}/team", json={
        "name": "X", "email": f"TEST_{uuid.uuid4().hex[:6]}@x.com",
        "password": "Demo1234!", "role": "technician"
    }, timeout=10)
    assert r.status_code == 403


# ---------- Customers ----------
def test_customers_create_list(owner_session):
    r = owner_session.post(f"{API}/customers", json={"name": "TEST_Cust", "phone": "555"}, timeout=10)
    assert r.status_code == 200
    r = owner_session.get(f"{API}/customers", timeout=10)
    assert r.status_code == 200
    data = r.json()
    rows = data.get("items", data) if isinstance(data, dict) else data
    assert any(c["name"] == "TEST_Cust" for c in rows)


# ---------- Multi-tenant isolation ----------
def test_multi_tenant_isolation():
    # Create another tenant and ensure they see 0 jobs
    email = f"TEST_{uuid.uuid4().hex[:8]}@iso.com"
    s = requests.Session()
    r = s.post(f"{API}/auth/register", json={
        "company_name": "TEST_Iso", "industry": "HVAC",
        "name": "Iso Owner", "email": email, "password": "Demo1234!",
    }, timeout=15)
    assert r.status_code == 200
    r = s.get(f"{API}/jobs", timeout=10)
    assert r.status_code == 200
    assert r.json() == []


# ---------- Payments ----------
def test_payment_checkout(owner_session):
    # find a non-paid job with price
    jobs = owner_session.get(f"{API}/jobs", timeout=10).json()
    job = next((j for j in jobs if not j.get("paid") and float(j.get("price") or 0) > 0), None)
    assert job, "Need a billable job"
    r = owner_session.post(f"{API}/payments/checkout", json={
        "job_id": job["id"], "origin_url": BASE_URL
    }, timeout=20)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("url", "").startswith("http")
    assert body.get("session_id")
