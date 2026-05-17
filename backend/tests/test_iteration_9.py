"""Iteration-9 tests: server.py refactor regression + new portal rate/tip + email.sent activity."""
import os
import sys
import uuid
import time
import pytest
import requests
from pathlib import Path

# allow importing deps for direct DB access (for customer-role setup)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL")
if not BASE_URL:
    # fallback to frontend .env file
    fenv = Path("/app/frontend/.env")
    for line in fenv.read_text().splitlines():
        if line.startswith("REACT_APP_BACKEND_URL="):
            BASE_URL = line.split("=", 1)[1].strip()
            break
BASE_URL = BASE_URL.rstrip("/")
API = f"{BASE_URL}/api"

DEMO_EMAIL = "demo@a1fieldpro.com"
DEMO_PASSWORD = "Demo1234!"
SUPER_EMAIL = "superadmin@a1fieldpro.com"
SUPER_PASSWORD = "Super1234!"


# ----------------- helpers -----------------
def login(email: str, password: str) -> requests.Session:
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=30)
    assert r.status_code == 200, f"login {email} failed: {r.status_code} {r.text}"
    return s


def _load_env():
    from dotenv import load_dotenv
    load_dotenv(Path("/app/backend/.env"))

_load_env()


def run_db(coro_factory):
    """Run a coroutine factory that takes (db) on a FRESH motor client/loop.
    coro_factory: callable(db) -> coroutine
    """
    import asyncio
    from motor.motor_asyncio import AsyncIOMotorClient
    async def _main():
        client = AsyncIOMotorClient(os.environ["MONGO_URL"])
        try:
            return await coro_factory(client[os.environ["DB_NAME"]])
        finally:
            client.close()
    return asyncio.run(_main())


# ============================================================
# REGRESSION: basic public + auth endpoints after router split
# ============================================================
class TestRegressionAfterRefactor:
    def test_root_api(self):
        r = requests.get(f"{API}/", timeout=15)
        assert r.status_code == 200
        assert r.json().get("status") == "ok"

    def test_login_demo_owner(self):
        s = login(DEMO_EMAIL, DEMO_PASSWORD)
        me = s.get(f"{API}/auth/me", timeout=15)
        assert me.status_code == 200
        body = me.json()
        assert body["user"]["email"] == DEMO_EMAIL
        assert body["user"]["role"] == "owner"
        assert body.get("company") is not None

    def test_login_superadmin(self):
        s = login(SUPER_EMAIL, SUPER_PASSWORD)
        me = s.get(f"{API}/auth/me", timeout=15)
        assert me.status_code == 200
        assert me.json()["user"]["role"] == "super_admin"

    def test_jobs_list(self):
        s = login(DEMO_EMAIL, DEMO_PASSWORD)
        r = s.get(f"{API}/jobs", timeout=15)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_dashboard_stats(self):
        s = login(DEMO_EMAIL, DEMO_PASSWORD)
        r = s.get(f"{API}/dashboard/stats", timeout=15)
        assert r.status_code == 200

    def test_activity_endpoint(self):
        s = login(DEMO_EMAIL, DEMO_PASSWORD)
        r = s.get(f"{API}/activity?limit=10", timeout=15)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_sessions_list(self):
        s = login(DEMO_EMAIL, DEMO_PASSWORD)
        r = s.get(f"{API}/sessions", timeout=15)
        assert r.status_code == 200


# ============================================================
# NEW: email.sent activity logged with meta from /auth/forgot
# ============================================================
class TestEmailSentActivity:
    def test_forgot_emits_email_sent_activity(self):
        # Trigger forgot for demo owner — send_email is called with actor=user
        fr = requests.post(f"{API}/auth/forgot", json={"email": DEMO_EMAIL}, timeout=20)
        assert fr.status_code == 200
        # poll the activity feed (owner view)
        time.sleep(1.5)
        s = login(DEMO_EMAIL, DEMO_PASSWORD)
        r = s.get(f"{API}/activity?action=email.sent&limit=20", timeout=15)
        assert r.status_code == 200
        events = r.json()
        assert isinstance(events, list)
        assert len(events) >= 1, "expected at least one email.sent activity event"
        ev = events[0]
        assert ev["action"] == "email.sent"
        meta = ev.get("meta") or {}
        # Required keys per spec: to, subject, purpose, status
        for k in ("to", "subject", "purpose", "status"):
            assert k in meta, f"missing meta.{k}: {meta}"
        assert meta["status"] in ("sent", "failed", "no_id", "skipped")
        # optional keys: email_id (when sent), error (when failed)
        if meta["status"] == "sent":
            assert "email_id" in meta
        if meta["status"] == "failed":
            assert "error" in meta


# ============================================================
# NEW: portal rate + tip-checkout + payment status
# ============================================================
@pytest.fixture(scope="module")
def portal_scenario():
    """Create a fresh owner+co+completed-job, then a customer user matching customer_email."""
    from deps import hash_password, now_iso
    suffix = uuid.uuid4().hex[:8]
    owner_email = f"test_owner_{suffix}@example.com"
    cust_email = f"test_cust_{suffix}@example.com"
    company_id = str(uuid.uuid4())
    owner_id = str(uuid.uuid4())
    cust_id = str(uuid.uuid4())
    job_completed = str(uuid.uuid4())
    job_scheduled = str(uuid.uuid4())

    async def _setup(db):
        await db.companies.insert_one({
            "id": company_id, "name": f"TEST_co_{suffix}", "industry": "HVAC",
            "owner_id": owner_id, "created_at": now_iso(),
        })
        await db.users.insert_many([
            {"id": owner_id, "company_id": company_id, "name": "TEST Owner",
             "email": owner_email, "password_hash": hash_password("Owner1234!"),
             "role": "owner", "active": True, "mfa_enabled": False, "mfa_secret": None,
             "email_verified": True, "created_at": now_iso()},
            {"id": cust_id, "company_id": None, "name": "TEST Customer",
             "email": cust_email, "password_hash": hash_password("Cust1234!"),
             "role": "customer", "active": True, "mfa_enabled": False, "mfa_secret": None,
             "email_verified": True, "created_at": now_iso()},
        ])
        await db.jobs.insert_many([
            {"id": job_completed, "company_id": company_id, "created_by": owner_id,
             "title": "TEST completed job", "customer_name": "TEST Customer",
             "customer_email": cust_email, "address": "1 TEST St",
             "job_type": "HVAC", "price": 200.0, "status": "completed",
             "paid": True, "created_at": now_iso()},
            {"id": job_scheduled, "company_id": company_id, "created_by": owner_id,
             "title": "TEST scheduled job", "customer_name": "TEST Customer",
             "customer_email": cust_email, "address": "2 TEST St",
             "job_type": "HVAC", "price": 100.0, "status": "scheduled",
             "paid": False, "created_at": now_iso()},
        ])

    run_db(_setup)
    data = {
        "owner_email": owner_email, "cust_email": cust_email,
        "cust_id": cust_id,
        "company_id": company_id, "job_completed": job_completed,
        "job_scheduled": job_scheduled,
    }
    yield data

    async def _cleanup(db):
        await db.users.delete_many({"email": {"$in": [owner_email, cust_email]}})
        await db.companies.delete_one({"id": company_id})
        await db.jobs.delete_many({"id": {"$in": [job_completed, job_scheduled]}})
        await db.activity.delete_many({"target_id": {"$in": [job_completed, job_scheduled]}})
        await db.payment_transactions.delete_many({"job_id": {"$in": [job_completed, job_scheduled]}})
    run_db(_cleanup)


class TestPortalRate:
    def test_rate_forbidden_for_non_customer(self, portal_scenario):
        # owner cannot rate
        s = login(portal_scenario["owner_email"], "Owner1234!")
        r = s.post(f"{API}/portal/jobs/{portal_scenario['job_completed']}/rate",
                   json={"rating": 5, "comment": "great"}, timeout=15)
        assert r.status_code == 403, r.text

    def test_rate_404_for_foreign_job(self, portal_scenario):
        s = login(portal_scenario["cust_email"], "Cust1234!")
        # demo company's seeded completed job — not owned by this customer
        owner_s = login(DEMO_EMAIL, DEMO_PASSWORD)
        jobs = owner_s.get(f"{API}/jobs", timeout=15).json()
        foreign_job = next((j for j in jobs if j.get("status") == "completed"), None)
        assert foreign_job, "no completed job in demo company"
        r = s.post(f"{API}/portal/jobs/{foreign_job['id']}/rate",
                   json={"rating": 5}, timeout=15)
        assert r.status_code == 404, r.text

    def test_rate_400_when_not_completed(self, portal_scenario):
        s = login(portal_scenario["cust_email"], "Cust1234!")
        r = s.post(f"{API}/portal/jobs/{portal_scenario['job_scheduled']}/rate",
                   json={"rating": 4}, timeout=15)
        assert r.status_code == 400, r.text

    def test_rate_422_invalid_rating(self, portal_scenario):
        s = login(portal_scenario["cust_email"], "Cust1234!")
        for bad in (0, 6, -1, 99):
            r = s.post(f"{API}/portal/jobs/{portal_scenario['job_completed']}/rate",
                       json={"rating": bad}, timeout=15)
            assert r.status_code == 422, f"bad rating {bad} -> {r.status_code} {r.text}"

    def test_rate_200_persists_and_logs_activity(self, portal_scenario):
        s = login(portal_scenario["cust_email"], "Cust1234!")
        r = s.post(f"{API}/portal/jobs/{portal_scenario['job_completed']}/rate",
                   json={"rating": 5, "comment": "excellent"}, timeout=15)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("ok") is True
        assert body.get("rating") == 5

        # verify persistence via direct DB
        async def _check(db):
            return await db.jobs.find_one({"id": portal_scenario["job_completed"]}, {"_id": 0})
        job = run_db(_check)
        assert job["rating"] == 5
        assert job["rating_comment"] == "excellent"
        assert job["rated_by"] == portal_scenario["cust_email"]
        assert job.get("rated_at")

        # verify activity event
        async def _act(db):
            return await db.activity.find_one(
                {"target_id": portal_scenario["job_completed"], "action": "rating.created"},
                {"_id": 0},
            )
        act = run_db(_act)
        assert act is not None
        assert act["meta"]["rating"] == 5


class TestPortalTipCheckout:
    def test_tip_checkout_forbidden_for_non_customer(self, portal_scenario):
        s = login(portal_scenario["owner_email"], "Owner1234!")
        r = s.post(f"{API}/portal/jobs/{portal_scenario['job_completed']}/tip-checkout",
                   json={"amount": 5.0, "origin_url": "https://example.com"}, timeout=20)
        assert r.status_code == 403

    def test_tip_checkout_404_for_foreign_job(self, portal_scenario):
        s = login(portal_scenario["cust_email"], "Cust1234!")
        r = s.post(f"{API}/portal/jobs/{uuid.uuid4()}/tip-checkout",
                   json={"amount": 5.0, "origin_url": "https://example.com"}, timeout=20)
        assert r.status_code == 404

    def test_tip_checkout_400_on_non_completed(self, portal_scenario):
        s = login(portal_scenario["cust_email"], "Cust1234!")
        r = s.post(f"{API}/portal/jobs/{portal_scenario['job_scheduled']}/tip-checkout",
                   json={"amount": 5.0, "origin_url": "https://example.com"}, timeout=20)
        assert r.status_code == 400

    def test_tip_checkout_400_on_non_positive_amount(self, portal_scenario):
        s = login(portal_scenario["cust_email"], "Cust1234!")
        for bad in (0, -1.0):
            r = s.post(f"{API}/portal/jobs/{portal_scenario['job_completed']}/tip-checkout",
                       json={"amount": bad, "origin_url": "https://example.com"}, timeout=20)
            assert r.status_code == 400, f"amount {bad} -> {r.status_code} {r.text}"

    def test_tip_checkout_200_returns_url_and_inserts_tx(self, portal_scenario):
        s = login(portal_scenario["cust_email"], "Cust1234!")
        r = s.post(f"{API}/portal/jobs/{portal_scenario['job_completed']}/tip-checkout",
                   json={"amount": 7.5, "origin_url": "https://example.com"}, timeout=30)
        assert r.status_code == 200, r.text
        body = r.json()
        assert "url" in body and body["url"].startswith("http")
        assert "session_id" in body and body["session_id"]

        # verify tx persisted with type=tip
        async def _check(db):
            return await db.payment_transactions.find_one(
                {"session_id": body["session_id"]}, {"_id": 0}
            )
        tx = run_db(_check)
        assert tx is not None
        assert tx["type"] == "tip"
        assert tx["job_id"] == portal_scenario["job_completed"]
        assert tx["amount"] == 7.5
        assert tx["payment_status"] == "initiated"

        # stash for next test
        portal_scenario["last_session_id"] = body["session_id"]


class TestPortalPaymentStatus:
    def test_status_404_for_foreign_tx(self, portal_scenario):
        # Insert a tx for a different user, then try to fetch as cust
        from deps import now_iso
        sid = f"sess_test_{uuid.uuid4().hex}"
        foreign_uid = str(uuid.uuid4())
        async def _insert(db):
            await db.payment_transactions.insert_one({
                "id": str(uuid.uuid4()), "session_id": sid,
                "job_id": portal_scenario["job_completed"],
                "company_id": portal_scenario["company_id"],
                "user_id": foreign_uid, "amount": 5.0, "currency": "usd",
                "payment_status": "paid", "status": "complete", "type": "tip",
                "metadata": {}, "created_at": now_iso(),
            })
        run_db(_insert)

        s = login(portal_scenario["cust_email"], "Cust1234!")
        r = s.get(f"{API}/portal/payments/status/{sid}", timeout=15)
        assert r.status_code == 404, r.text

        # cleanup
        async def _del(db):
            await db.payment_transactions.delete_one({"session_id": sid})
        run_db(_del)

    def test_status_returns_paid_tx_when_already_processed(self, portal_scenario):
        """Manually insert a paid+processed tip tx; verify polling returns it (short-circuit)."""
        from deps import now_iso
        sid = f"sess_paid_{uuid.uuid4().hex}"
        cust_uid = portal_scenario["cust_id"]

        async def _insert(db):
            await db.payment_transactions.insert_one({
                "id": str(uuid.uuid4()), "session_id": sid,
                "job_id": portal_scenario["job_completed"],
                "company_id": portal_scenario["company_id"],
                "user_id": cust_uid, "amount": 12.0, "currency": "usd",
                "payment_status": "paid", "status": "complete",
                "processed": True, "type": "tip",
                "metadata": {}, "created_at": now_iso(),
            })
        run_db(_insert)

        s = login(portal_scenario["cust_email"], "Cust1234!")
        r = s.get(f"{API}/portal/payments/status/{sid}", timeout=15)
        assert r.status_code == 200, r.text
        tx = r.json()
        assert tx["payment_status"] == "paid"
        assert tx["type"] == "tip"
        assert tx["amount"] == 12.0

        # cleanup
        async def _del(db):
            await db.payment_transactions.delete_one({"session_id": sid})
        run_db(_del)

    def test_status_requires_customer_role(self, portal_scenario):
        # owner trying portal endpoint -> 403
        s = login(portal_scenario["owner_email"], "Owner1234!")
        r = s.get(f"{API}/portal/payments/status/anything", timeout=15)
        assert r.status_code == 403


# ============================================================
# NEW: public company endpoint exposes `industry`
# ============================================================
class TestPublicCompanyIndustry:
    def test_industry_present(self):
        # Find the demo company id via owner /auth/me
        s = login(DEMO_EMAIL, DEMO_PASSWORD)
        me = s.get(f"{API}/auth/me", timeout=15).json()
        company_id = me["company"]["id"]

        r = requests.get(f"{API}/public/companies/{company_id}", timeout=15)
        assert r.status_code == 200
        body = r.json()
        assert "industry" in body, f"industry missing in: {body}"
        assert body["industry"] == "HVAC"
        # owner_id should be projected out (public)
        assert "owner_id" not in body

    def test_public_company_404(self):
        r = requests.get(f"{API}/public/companies/{uuid.uuid4()}", timeout=15)
        assert r.status_code == 404


# ============================================================
# REGRESSION: v1.6 rules still enforced
# ============================================================
class TestV16RulesStillEnforced:
    def test_hex_color_regex_enforced(self):
        s = login(DEMO_EMAIL, DEMO_PASSWORD)
        # bad
        r = s.patch(f"{API}/companies/me", json={"primary_color": "red"}, timeout=15)
        assert r.status_code == 422, r.text
        # good
        r = s.patch(f"{API}/companies/me", json={"primary_color": "#1D4ED8"}, timeout=15)
        assert r.status_code in (200, 204), r.text

    def test_password_strength_register(self):
        # short
        r = requests.post(f"{API}/auth/register", json={
            "company_name": "TEST_pw_co",
            "industry": "HVAC",
            "name": "Pw Tester",
            "email": f"TEST_pw_{uuid.uuid4().hex[:8]}@example.com",
            "password": "ab12",  # too short
        }, timeout=15)
        assert r.status_code == 422
        # no digit
        r = requests.post(f"{API}/auth/register", json={
            "company_name": "TEST_pw_co",
            "industry": "HVAC",
            "name": "Pw Tester",
            "email": f"TEST_pw_{uuid.uuid4().hex[:8]}@example.com",
            "password": "abcdefgh",
        }, timeout=15)
        assert r.status_code == 422

    def test_email_verify_gate_before_checkout(self):
        # Register a fresh unverified owner with strong pw
        email = f"TEST_unv_{uuid.uuid4().hex[:8]}@example.com"
        r = requests.post(f"{API}/auth/register", json={
            "company_name": f"TEST_unv_co_{uuid.uuid4().hex[:6]}",
            "industry": "HVAC",
            "name": "Unv Owner",
            "email": email,
            "password": "Strong1234!",
        }, timeout=20)
        assert r.status_code == 200, r.text

        s = login(email, "Strong1234!")
        # create a job
        jr = s.post(f"{API}/jobs", json={
            "title": "TEST job", "customer_name": "x", "customer_phone": "555",
            "address": "1 st", "job_type": "HVAC", "price": 100.0,
        }, timeout=15)
        assert jr.status_code == 200, jr.text
        job_id = jr.json()["id"]
        # checkout should be blocked
        co = s.post(f"{API}/payments/checkout", json={
            "job_id": job_id, "origin_url": "https://example.com",
        }, timeout=20)
        assert co.status_code == 403
        assert "Verify your email" in co.text
