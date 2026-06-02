"""Iteration-12 tests: v1.11 Push hooks expansion.

Coverage:
- POST /api/portal/jobs/{id}/rate          → push to tech (+owner on rating<=2)
- GET  /api/payments/status/{session_id}   → push on transition to paid
- POST /api/webhook/stripe                 → endpoint surface (no signature mocking)
- GET  /api/portal/payments/status/{sid}   → push on tip paid
- POST /api/recurring-jobs/{rid}/run       → push when assigned_to set & != actor
- GET  /api/jobs (lazy materialize)        → push on materialize
- GET  /api/recurring-jobs (lazy materialize)

Strategy:
Since the running server lives in a separate process we cannot monkeypatch
`push_service.send_push_to_user`. Instead we install REAL `push_subscriptions`
rows whose endpoint is unreachable (fake FCM endpoint). pywebpush will fail
silently inside the try/except. This validates the "never block parent" contract.

For each push trigger we also verify the corresponding *activity* event was
written so we know the parent endpoint actually finished executing the code
path that owns the push hook.
"""
import os
import sys
import uuid
import pytest
import requests
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL")
if not BASE_URL:
    for line in Path("/app/frontend/.env").read_text().splitlines():
        if line.startswith("REACT_APP_BACKEND_URL="):
            BASE_URL = line.split("=", 1)[1].strip()
            break
BASE_URL = BASE_URL.rstrip("/")
API = f"{BASE_URL}/api"

DEMO = ("demo@a1fieldpro.com", "Demo1234!")
TECH = ("tech@a1fieldpro.com", "Demo1234!")


def _load_env():
    from dotenv import load_dotenv
    load_dotenv(Path("/app/backend/.env"))


_load_env()


def login(email, password):
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=30)
    assert r.status_code == 200, f"login {email} failed: {r.status_code} {r.text}"
    return s


def me(s):
    return s.get(f"{API}/auth/me", timeout=15).json()


def run_db(fn):
    import asyncio
    from motor.motor_asyncio import AsyncIOMotorClient
    async def _main():
        c = AsyncIOMotorClient(os.environ["MONGO_URL"])
        try:
            return await fn(c[os.environ["DB_NAME"]])
        finally:
            c.close()
    return asyncio.run(_main())


def _fake_sub_row(user_id: str, tag: str) -> dict:
    return {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "endpoint": f"https://fcm.googleapis.com/fcm/send/test-iter12-{tag}-{uuid.uuid4().hex}",
        "keys": {
            "p256dh": "BNcRdreALRFXTkOOUHK1EtK2wtaz5Ry4YfYCA_0QTpQtUbVlUls0VJXg7A8u-Ts1XbjhazAkj7I99e8QcYP7DkM",
            "auth":   "tBHItJI5svbpez7KI4CCXg",
        },
        "user_agent": "pytest/iteration12",
        "active": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


# ===============================================================
# Module-scoped scenario: owner + tech + customer + completed job
# ===============================================================
@pytest.fixture(scope="module")
def scenario():
    from deps import hash_password, now_iso
    sfx = uuid.uuid4().hex[:8]
    owner_email = f"test_owner_{sfx}@example.com"
    tech_email  = f"test_tech_{sfx}@example.com"
    cust_email  = f"test_cust_{sfx}@example.com"
    company_id  = str(uuid.uuid4())
    owner_id    = str(uuid.uuid4())
    tech_id     = str(uuid.uuid4())
    cust_id     = str(uuid.uuid4())
    job_done    = str(uuid.uuid4())
    rj_id       = str(uuid.uuid4())

    async def _setup(db):
        await db.companies.insert_one({
            "id": company_id, "name": f"TEST_co_{sfx}", "industry": "HVAC",
            "owner_id": owner_id, "created_at": now_iso(),
        })
        await db.users.insert_many([
            {"id": owner_id, "company_id": company_id, "name": "TEST Owner",
             "email": owner_email, "password_hash": hash_password("Owner1234!"),
             "role": "owner", "active": True, "mfa_enabled": False, "email_verified": True,
             "created_at": now_iso()},
            {"id": tech_id, "company_id": company_id, "name": "TEST Tech",
             "email": tech_email, "password_hash": hash_password("Tech1234!"),
             "role": "technician", "active": True, "mfa_enabled": False, "email_verified": True,
             "created_at": now_iso()},
            {"id": cust_id, "company_id": None, "name": "TEST Cust",
             "email": cust_email, "password_hash": hash_password("Cust1234!"),
             "role": "customer", "active": True, "mfa_enabled": False, "email_verified": True,
             "created_at": now_iso()},
        ])
        await db.jobs.insert_one({
            "id": job_done, "company_id": company_id, "created_by": owner_id,
            "assigned_to": tech_id,
            "title": "TEST completed job", "customer_name": "TEST Cust",
            "customer_email": cust_email, "address": "1 TEST St",
            "job_type": "HVAC", "price": 200.0, "status": "completed",
            "paid": True, "created_at": now_iso(),
        })
        # Seed fake push subs for owner + tech (so push hooks have something to hit & fail silently)
        await db.push_subscriptions.insert_many([
            _fake_sub_row(owner_id, "owner"),
            _fake_sub_row(tech_id,  "tech"),
        ])

    run_db(_setup)
    data = dict(owner_email=owner_email, tech_email=tech_email, cust_email=cust_email,
                company_id=company_id, owner_id=owner_id, tech_id=tech_id, cust_id=cust_id,
                job_done=job_done, rj_id=rj_id)
    yield data

    async def _cleanup(db):
        await db.users.delete_many({"email": {"$in": [owner_email, tech_email, cust_email]}})
        await db.companies.delete_one({"id": company_id})
        await db.jobs.delete_many({"$or": [{"id": job_done}, {"recurring_id": rj_id}]})
        await db.recurring_jobs.delete_many({"id": rj_id})
        await db.activity.delete_many({"$or": [
            {"target_id": job_done}, {"target_id": rj_id},
        ]})
        await db.payment_transactions.delete_many({"job_id": job_done})
        await db.push_subscriptions.delete_many({"user_agent": "pytest/iteration12"})
    run_db(_cleanup)


# ===============================================================
# 1) Rate flow — push to tech (+ owner on low rating)
# ===============================================================
class TestRatePushHook:
    def test_rate_high_returns_ok_and_logs_activity(self, scenario):
        s = login(scenario["cust_email"], "Cust1234!")
        r = s.post(f"{API}/portal/jobs/{scenario['job_done']}/rate",
                   json={"rating": 5, "comment": "TEST great"}, timeout=20)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body == {"ok": True, "rating": 5}

        # Activity event must be present (proves push hook code path ran fully)
        async def _q(db):
            return await db.activity.find_one(
                {"target_id": scenario["job_done"], "action": "rating.created"},
                sort=[("created_at", -1)],
            )
        ev = run_db(_q)
        assert ev is not None
        assert ev["meta"]["rating"] == 5
        assert ev["meta"]["tech_id"] == scenario["tech_id"]

    def test_rate_low_still_returns_ok_owner_push_silent_fail(self, scenario):
        s = login(scenario["cust_email"], "Cust1234!")
        r = s.post(f"{API}/portal/jobs/{scenario['job_done']}/rate",
                   json={"rating": 1, "comment": "TEST bad"}, timeout=20)
        # Push to BOTH tech and owner is attempted; both fail (fake subs); endpoint must still 200
        assert r.status_code == 200, r.text
        assert r.json() == {"ok": True, "rating": 1}

        # Confirm the rated_at + rating fields were persisted on the job
        async def _q(db):
            return await db.jobs.find_one({"id": scenario["job_done"]}, {"_id": 0})
        job = run_db(_q)
        assert job["rating"] == 1
        assert job["rating_comment"] == "TEST bad"

    def test_rate_with_no_assigned_to_still_ok(self, scenario):
        """If job has no tech, push to tech is skipped — endpoint must still return 200."""
        async def _strip(db):
            await db.jobs.update_one({"id": scenario["job_done"]},
                                     {"$unset": {"assigned_to": ""}})
        run_db(_strip)
        s = login(scenario["cust_email"], "Cust1234!")
        r = s.post(f"{API}/portal/jobs/{scenario['job_done']}/rate",
                   json={"rating": 4}, timeout=20)
        assert r.status_code == 200, r.text
        assert r.json()["ok"] is True
        # restore for downstream tests
        async def _restore(db):
            await db.jobs.update_one({"id": scenario["job_done"]},
                                     {"$set": {"assigned_to": scenario["tech_id"]}})
        run_db(_restore)


# ===============================================================
# 2) /payments/status — push on transition to paid
# ===============================================================
class TestPaymentStatusPushHook:
    def test_status_short_circuit_on_already_paid_tx(self, scenario):
        """When tx is already paid, endpoint returns the tx without firing push.
        The push hook is gated on `tx.payment_status != 'paid'` at function entry.
        Logs in by impersonating owner via direct user record."""
        from deps import now_iso
        sid = f"sess_iter12_paid_{uuid.uuid4().hex}"
        async def _setup(db):
            await db.payment_transactions.insert_one({
                "id": str(uuid.uuid4()), "session_id": sid,
                "job_id": scenario["job_done"], "company_id": scenario["company_id"],
                "user_id": scenario["owner_id"], "amount": 99.0, "currency": "usd",
                "payment_status": "paid", "status": "complete", "type": "service",
                "processed": True, "metadata": {}, "created_at": now_iso(),
            })
        run_db(_setup)

        s = login(scenario["owner_email"], "Owner1234!")
        r = s.get(f"{API}/payments/status/{sid}", timeout=20)
        assert r.status_code == 200, r.text
        tx = r.json()
        assert tx["payment_status"] == "paid"
        assert tx["amount"] == 99.0

        async def _del(db):
            await db.payment_transactions.delete_one({"session_id": sid})
        run_db(_del)

    def test_status_404_for_unknown_session(self, scenario):
        s = login(scenario["owner_email"], "Owner1234!")
        r = s.get(f"{API}/payments/status/sess_iter12_does_not_exist", timeout=15)
        assert r.status_code == 404


# ===============================================================
# 3) /webhook/stripe — endpoint surface
# ===============================================================
class TestStripeWebhookSurface:
    def test_webhook_bad_signature_returns_400_not_500(self):
        """Webhook with invalid signature must NOT 500 — push hook lives behind
        a successful evt parse so we only verify the parent endpoint's behavior."""
        r = requests.post(f"{API}/webhook/stripe",
                          data=b'{"id":"evt_test","type":"checkout.session.completed"}',
                          headers={"Stripe-Signature": "t=0,v1=invalid"},
                          timeout=15)
        # Spec: handler raises HTTPException(400) on parse failure
        assert r.status_code in (400, 401, 403), f"unexpected {r.status_code}: {r.text}"
        # Never 500
        assert r.status_code < 500


# ===============================================================
# 4) Portal tip status — push on tip paid (use already-paid shortcut)
# ===============================================================
class TestPortalTipStatus:
    def test_portal_status_already_paid_returns_tx_no_push(self, scenario):
        from deps import now_iso
        sid = f"sess_iter12_tip_{uuid.uuid4().hex}"
        async def _setup(db):
            await db.payment_transactions.insert_one({
                "id": str(uuid.uuid4()), "session_id": sid,
                "job_id": scenario["job_done"], "company_id": scenario["company_id"],
                "user_id": scenario["cust_id"], "amount": 5.0, "currency": "usd",
                "payment_status": "paid", "status": "complete",
                "processed": True, "type": "tip",
                "metadata": {}, "created_at": now_iso(),
            })
        run_db(_setup)

        s = login(scenario["cust_email"], "Cust1234!")
        r = s.get(f"{API}/portal/payments/status/{sid}", timeout=15)
        assert r.status_code == 200, r.text
        tx = r.json()
        assert tx["type"] == "tip"
        assert tx["payment_status"] == "paid"

        async def _del(db):
            await db.payment_transactions.delete_one({"session_id": sid})
        run_db(_del)


# ===============================================================
# 5) Recurring run — push when assigned_to != actor
# ===============================================================
class TestRecurringRunPushHook:
    def test_force_run_assigned_to_tech_returns_job_and_logs_activity(self, scenario):
        from deps import now_iso
        rj_id = scenario["rj_id"]
        async def _setup(db):
            await db.recurring_jobs.insert_one({
                "id": rj_id, "company_id": scenario["company_id"],
                "created_by": scenario["owner_id"], "created_at": now_iso(),
                "next_run_at": now_iso(), "last_run_at": None,
                "title": "TEST recurring run", "description": "",
                "customer_id": None, "customer_name": "TEST Cust",
                "customer_phone": "", "customer_email": scenario["cust_email"],
                "address": "1 TEST St", "job_type": "HVAC",
                "assigned_to": scenario["tech_id"],
                "duration_min": 60, "price": 100.0,
                "cadence": "weekly", "interval_days": 7,
                "start_at": now_iso(), "active": True,
            })
        run_db(_setup)

        s = login(scenario["owner_email"], "Owner1234!")
        r = s.post(f"{API}/recurring-jobs/{rj_id}/run", timeout=30)
        assert r.status_code == 200, r.text
        job = r.json()
        assert job["recurring_id"] == rj_id
        assert job["assigned_to"] == scenario["tech_id"]
        assert job["status"] == "scheduled_installation"
        # endpoint stripped _id
        assert "_id" not in job

        # activity event written
        async def _q(db):
            return await db.activity.find_one({"action": "recurring.materialized", "target_id": rj_id},
                                              sort=[("created_at", -1)])
        ev = run_db(_q)
        assert ev is not None
        assert ev["meta"]["job_id"] == job["id"]

    def test_force_run_self_assigned_no_push_still_ok(self, scenario):
        """When the actor IS the assignee, push is skipped — endpoint must still 200."""
        from deps import now_iso
        rj_id2 = str(uuid.uuid4())
        async def _setup(db):
            await db.recurring_jobs.insert_one({
                "id": rj_id2, "company_id": scenario["company_id"],
                "created_by": scenario["owner_id"], "created_at": now_iso(),
                "next_run_at": now_iso(), "last_run_at": None,
                "title": "TEST recurring self", "description": "",
                "customer_name": "TEST Cust", "customer_email": scenario["cust_email"],
                "address": "1 TEST St", "job_type": "HVAC",
                "assigned_to": scenario["owner_id"],  # self
                "duration_min": 60, "price": 50.0,
                "cadence": "weekly", "interval_days": 7,
                "start_at": now_iso(), "active": True,
            })
        run_db(_setup)

        s = login(scenario["owner_email"], "Owner1234!")
        r = s.post(f"{API}/recurring-jobs/{rj_id2}/run", timeout=30)
        assert r.status_code == 200, r.text

        async def _cleanup(db):
            await db.recurring_jobs.delete_one({"id": rj_id2})
            await db.jobs.delete_many({"recurring_id": rj_id2})
            await db.activity.delete_many({"target_id": rj_id2})
        run_db(_cleanup)


# ===============================================================
# 6) Lazy materialization via GET /jobs and GET /recurring-jobs
# ===============================================================
class TestLazyMaterializePushHook:
    def test_get_jobs_materializes_due_recurring_with_push_silent_fail(self, scenario):
        """Insert a recurring plan whose next_run_at is in the past + assigned_to=tech,
        then call GET /api/jobs as owner. _materialize_due should run, fire push (fake
        sub → silent fail) and insert the materialized job."""
        from deps import now_iso
        past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        rj_id3 = str(uuid.uuid4())
        async def _setup(db):
            await db.recurring_jobs.insert_one({
                "id": rj_id3, "company_id": scenario["company_id"],
                "created_by": scenario["owner_id"], "created_at": now_iso(),
                "next_run_at": past, "last_run_at": None,
                "title": "TEST lazy materialize",
                "customer_name": "TEST Cust", "customer_email": scenario["cust_email"],
                "address": "1 TEST St", "job_type": "HVAC",
                "assigned_to": scenario["tech_id"],
                "duration_min": 60, "price": 75.0,
                "cadence": "weekly", "interval_days": 7,
                "active": True,
            })
        run_db(_setup)

        s = login(scenario["owner_email"], "Owner1234!")
        r = s.get(f"{API}/jobs", timeout=30)
        assert r.status_code == 200, r.text
        # The materialized job should be in the list
        jobs = r.json()
        mat = [j for j in jobs if j.get("recurring_id") == rj_id3]
        assert len(mat) >= 1, f"materialized job missing for {rj_id3}"
        assert mat[0]["assigned_to"] == scenario["tech_id"]
        assert mat[0]["status"] == "scheduled_installation"
        assert mat[0]["source"] == "recurring"

        # next_run_at should have advanced (no longer in the past)
        async def _q(db):
            return await db.recurring_jobs.find_one({"id": rj_id3}, {"_id": 0})
        rj = run_db(_q)
        assert rj["last_run_at"] is not None
        assert rj["next_run_at"] > past

        # cleanup
        async def _cleanup(db):
            await db.recurring_jobs.delete_one({"id": rj_id3})
            await db.jobs.delete_many({"recurring_id": rj_id3})
        run_db(_cleanup)

    def test_get_recurring_jobs_materializes_due_with_push_silent_fail(self, scenario):
        from deps import now_iso
        past = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
        rj_id4 = str(uuid.uuid4())
        async def _setup(db):
            await db.recurring_jobs.insert_one({
                "id": rj_id4, "company_id": scenario["company_id"],
                "created_by": scenario["owner_id"], "created_at": now_iso(),
                "next_run_at": past, "last_run_at": None,
                "title": "TEST lazy 2",
                "customer_name": "TEST Cust", "customer_email": scenario["cust_email"],
                "address": "2 TEST St", "job_type": "HVAC",
                "assigned_to": scenario["tech_id"],
                "duration_min": 60, "price": 80.0,
                "cadence": "weekly", "interval_days": 7,
                "active": True,
            })
        run_db(_setup)

        s = login(scenario["owner_email"], "Owner1234!")
        r = s.get(f"{API}/recurring-jobs", timeout=30)
        assert r.status_code == 200, r.text
        items = r.json()
        assert any(it["id"] == rj_id4 for it in items)

        # job should exist
        async def _q(db):
            return await db.jobs.find_one({"recurring_id": rj_id4}, {"_id": 0})
        j = run_db(_q)
        assert j is not None
        assert j["assigned_to"] == scenario["tech_id"]

        async def _cleanup(db):
            await db.recurring_jobs.delete_one({"id": rj_id4})
            await db.jobs.delete_many({"recurring_id": rj_id4})
        run_db(_cleanup)


# ===============================================================
# 7) Regression smoke — baseline endpoints still healthy
# ===============================================================
class TestRegressionSmoke:
    def test_root(self):
        r = requests.get(f"{API}/", timeout=15)
        assert r.status_code == 200 and r.json().get("status") == "ok"

    def test_demo_login_and_me(self):
        s = login(*DEMO)
        u = me(s)
        assert u["user"]["role"] == "owner"

    def test_jobs_list_owner(self):
        s = login(*DEMO)
        r = s.get(f"{API}/jobs", timeout=15)
        assert r.status_code == 200

    def test_recurring_list_owner(self):
        s = login(*DEMO)
        r = s.get(f"{API}/recurring-jobs", timeout=15)
        assert r.status_code == 200
