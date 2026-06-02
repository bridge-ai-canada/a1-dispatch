"""Phase 2C tests: email verification, Google login, customer portal, booking customer_email."""
import os
import sys
import uuid
import pytest
import requests
from unittest.mock import patch, MagicMock
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "a1_field_pro")

# Add backend to path so we can import server for monkeypatch
sys.path.insert(0, "/app/backend")

SUPER = {"email": "superadmin@a1fieldpro.com", "password": "Super1234!"}
OWNER = {"email": "demo@a1fieldpro.com", "password": "Demo1234!"}
TECH = {"email": "tech@a1fieldpro.com", "password": "Demo1234!"}


@pytest.fixture(scope="session", autouse=True)
def _reset_mfa_state():
    client = MongoClient(MONGO_URL)
    try:
        db = client[DB_NAME]
        db.users.update_many(
            {"email": {"$in": [SUPER["email"], OWNER["email"], TECH["email"]]}},
            {"$set": {"mfa_enabled": False, "mfa_secret": None, "active": True}},
        )
        db.users.delete_many({"email": {"$regex": "^(TEST_|test_)"}})
        db.jobs.delete_many({"title": {"$regex": "TEST"}})
        db.customers.delete_many({"name": {"$regex": "TEST"}})
        yield
        db.users.update_many(
            {"email": {"$in": [SUPER["email"], OWNER["email"], TECH["email"]]}},
            {"$set": {"mfa_enabled": False, "mfa_secret": None, "active": True}},
        )
        db.users.delete_many({"email": {"$regex": "^(TEST_|test_)"}})
        db.jobs.delete_many({"title": {"$regex": "TEST"}})
        db.customers.delete_many({"name": {"$regex": "TEST"}})
    finally:
        client.close()


def _login(creds):
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json=creds, timeout=15)
    assert r.status_code == 200, r.text
    return s


@pytest.fixture
def owner_session():
    return _login(OWNER)


@pytest.fixture
def tech_session():
    return _login(TECH)


# ---------------- Registration: email_verified=false ----------------
class TestRegistrationVerify:
    def test_register_sets_email_verified_false(self):
        email = f"TEST_reg_{uuid.uuid4().hex[:8]}@example.com"
        r = requests.post(f"{API}/auth/register", json={
            "company_name": "TEST_RegCo", "industry": "HVAC",
            "name": "TEST Reg", "email": email, "password": "TestPass123!",
        }, timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["user"]["email_verified"] is False
        # token present
        assert "token" in data

    def test_verify_endpoint_with_invalid_token(self):
        r = requests.post(f"{API}/auth/verify", params={"token": "not-a-jwt"}, timeout=15)
        assert r.status_code == 400

    def test_verify_resend_and_then_verify(self):
        # Register new user
        email = f"TEST_v_{uuid.uuid4().hex[:8]}@example.com"
        s = requests.Session()
        r = s.post(f"{API}/auth/register", json={
            "company_name": "TEST_VerCo", "industry": "HVAC",
            "name": "TEST Ver", "email": email, "password": "TestPass123!",
        }, timeout=15)
        assert r.status_code == 200
        # Resend should return verify_url
        r = s.post(f"{API}/auth/verify/resend", timeout=15)
        assert r.status_code == 200, r.text
        body = r.json()
        assert "verify_url" in body
        assert "email_sent" in body
        # extract token from verify_url and call /auth/verify
        token = body["verify_url"].split("token=")[-1]
        r = requests.post(f"{API}/auth/verify", params={"token": token}, timeout=15)
        assert r.status_code == 200
        # idempotent — calling resend again should return already_verified
        r = s.post(f"{API}/auth/verify/resend", timeout=15)
        assert r.status_code == 200
        assert r.json().get("already_verified") is True

    def test_verify_resend_requires_auth(self):
        r = requests.post(f"{API}/auth/verify/resend", timeout=15)
        assert r.status_code == 401


# ---------------- Google exchange ----------------
class TestGoogleExchange:
    def test_google_exchange_bad_session_returns_400(self):
        r = requests.post(f"{API}/auth/google/exchange",
                          json={"session_id": "definitely-bad-" + uuid.uuid4().hex}, timeout=20)
        assert r.status_code == 400
        assert "Google" in r.json().get("detail", "")

    @pytest.mark.asyncio
    async def test_google_exchange_happy_path_creates_customer(self):
        """Patch the auth router's `requests.get` to simulate Emergent's session-data API.
        We exercise the handler in-process (it shares the same MongoDB as the live server)."""
        import importlib
        auth_mod = importlib.import_module("routers.auth")
        deps_mod = importlib.import_module("deps")

        fake_email = f"test_g_{uuid.uuid4().hex[:8]}@example.com"
        fake_resp = MagicMock()
        fake_resp.raise_for_status = MagicMock()
        fake_resp.json = MagicMock(return_value={
            "email": fake_email, "name": "TEST Google User",
            "picture": "https://example.com/p.png",
        })

        from fastapi import Response
        from starlette.requests import Request as StarletteRequest

        scope = {
            "type": "http", "method": "POST", "path": "/api/auth/google/exchange",
            "headers": [], "client": ("127.0.0.1", 0), "query_string": b"",
            "scheme": "http", "server": ("test", 80), "root_path": "",
        }
        req = StarletteRequest(scope)
        resp = Response()
        body = deps_mod.GoogleExchangeIn(session_id="fake-good-session")
        with patch.object(auth_mod, "requests") as mock_requests:
            mock_requests.get.return_value = fake_resp
            out = await auth_mod.google_exchange(body, req, resp)
        assert "user" in out and "token" in out
        u = out["user"]
        assert u["email"] == fake_email
        assert u["role"] == "customer"
        assert u["company_id"] is None
        assert u["email_verified"] is True
        assert u["google_linked"] is True
        assert "_id" not in u


# ---------------- Customer Portal ----------------
class TestPortal:
    def test_portal_jobs_forbidden_for_owner(self, owner_session):
        r = owner_session.get(f"{API}/portal/jobs", timeout=15)
        assert r.status_code == 403

    def test_portal_companies_forbidden_for_tech(self, tech_session):
        r = tech_session.get(f"{API}/portal/companies", timeout=15)
        assert r.status_code == 403

    def test_portal_jobs_unauth(self):
        r = requests.get(f"{API}/portal/jobs", timeout=15)
        assert r.status_code == 401

    def test_portal_flow_with_booking_and_customer(self, owner_session):
        """End-to-end:
        1. Find demo company_id
        2. Submit public booking with TEST_ customer email
        3. Promote a TEST_ user to role=customer with the same email
        4. Login as that user → /portal/jobs returns the booking
        5. /portal/companies returns the demo company
        """
        # 1. demo company
        me = owner_session.get(f"{API}/auth/me", timeout=15).json()
        company_id = me["user"]["company_id"]
        assert company_id

        # 2. submit booking
        cust_email = f"test_cust_{uuid.uuid4().hex[:6]}@example.com"
        cust_pw = "CustPass123!"
        r = requests.post(f"{API}/public/companies/{company_id}/bookings", json={
            "name": "TEST Customer",
            "phone": "+15551234567",
            "email": cust_email,
            "address": "123 Test St",
            "job_type": "HVAC",
            "description": "TEST_portal booking",
            "preferred_date": None,
        }, timeout=15)
        assert r.status_code == 200, r.text
        job = r.json()
        assert "job_id" in job
        # Verify customer_email persisted in DB
        client = MongoClient(MONGO_URL)
        try:
            db = client[DB_NAME]
            stored = db.jobs.find_one({"id": job["job_id"]}, {"_id": 0})
            assert stored is not None
            assert stored["customer_email"] == cust_email
            assert stored["title"].startswith("HVAC")
        finally:
            client.close()

        # 3. Create a customer user with the same email directly via mongo
        client = MongoClient(MONGO_URL)
        try:
            db = client[DB_NAME]
            # Use register endpoint to get proper hashing, then promote role
            r = requests.post(f"{API}/auth/register", json={
                "company_name": "TEST_CustCo", "industry": "HVAC",
                "name": "TEST Cust Owner", "email": cust_email, "password": cust_pw,
            }, timeout=15)
            assert r.status_code == 200
            db.users.update_one({"email": cust_email},
                                {"$set": {"role": "customer", "company_id": None}})
        finally:
            client.close()

        # 4. Login as customer (no MFA on fresh user)
        cs = requests.Session()
        r = cs.post(f"{API}/auth/login", json={"email": cust_email, "password": cust_pw}, timeout=15)
        assert r.status_code == 200, r.text
        r = cs.get(f"{API}/portal/jobs", timeout=15)
        assert r.status_code == 200
        jobs = r.json()
        assert any(j["customer_email"] == cust_email for j in jobs), jobs

        # 5. portal companies includes demo company
        r = cs.get(f"{API}/portal/companies", timeout=15)
        assert r.status_code == 200
        cos = r.json()
        assert any(c["id"] == company_id for c in cos), cos
        # _id should not be exposed
        for c in cos:
            assert "_id" not in c


# ---------------- Booking widget customer_email ----------------
class TestBookingEmail:
    def test_booking_creates_job_with_customer_email(self, owner_session):
        me = owner_session.get(f"{API}/auth/me", timeout=15).json()
        company_id = me["user"]["company_id"]
        em = f"TEST_be_{uuid.uuid4().hex[:6]}@example.com"
        r = requests.post(f"{API}/public/companies/{company_id}/bookings", json={
            "name": "TEST Booking Email",
            "phone": "+15559998888",
            "email": em,
            "address": "456 Bk St",
            "job_type": "Plumbing",
            "description": "TEST_email booking",
        }, timeout=15)
        assert r.status_code == 200, r.text
        out = r.json()
        assert "job_id" in out
        client = MongoClient(MONGO_URL)
        try:
            db = client[DB_NAME]
            stored = db.jobs.find_one({"id": out["job_id"]}, {"_id": 0})
            assert stored["customer_email"] == em
        finally:
            client.close()

    def test_booking_without_email_still_works(self, owner_session):
        me = owner_session.get(f"{API}/auth/me", timeout=15).json()
        company_id = me["user"]["company_id"]
        r = requests.post(f"{API}/public/companies/{company_id}/bookings", json={
            "name": "TEST NoEmail",
            "phone": "+15557776666",
            "address": "789 NoEm St",
            "job_type": "HVAC",
        }, timeout=15)
        assert r.status_code == 200, r.text


# ---------------- Regression smoke ----------------
class TestRegression:
    def test_login_still_works(self):
        s = _login(OWNER)
        r = s.get(f"{API}/auth/me", timeout=15)
        assert r.status_code == 200
        assert r.json()["user"]["role"] == "owner"

    def test_super_admin_login(self):
        s = _login(SUPER)
        r = s.get(f"{API}/auth/me", timeout=15)
        assert r.status_code == 200
        assert r.json()["user"]["role"] == "super_admin"
