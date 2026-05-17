"""Iteration-10 tests: verify-email invite gate + recurring jobs + CSV exports + route optimization."""
import os
import sys
import uuid
import pytest
import requests
from pathlib import Path
from datetime import datetime, timezone, timedelta

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL")
if not BASE_URL:
    fenv = Path("/app/frontend/.env")
    for line in fenv.read_text().splitlines():
        if line.startswith("REACT_APP_BACKEND_URL="):
            BASE_URL = line.split("=", 1)[1].strip()
            break
BASE_URL = BASE_URL.rstrip("/")
API = f"{BASE_URL}/api"

DEMO_EMAIL = "demo@a1fieldpro.com"
DEMO_PASSWORD = "Demo1234!"
DISP_EMAIL = "dispatcher@a1fieldpro.com"
DISP_PASSWORD = "Demo1234!"
TECH_EMAIL = "tech@a1fieldpro.com"
TECH_PASSWORD = "Demo1234!"
SUPER_EMAIL = "superadmin@a1fieldpro.com"
SUPER_PASSWORD = "Super1234!"


def _load_env():
    from dotenv import load_dotenv
    load_dotenv(Path("/app/backend/.env"))


_load_env()


def login(email: str, password: str) -> requests.Session:
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=30)
    assert r.status_code == 200, f"login {email} failed: {r.status_code} {r.text}"
    return s


def run_db(coro_factory):
    import asyncio
    from motor.motor_asyncio import AsyncIOMotorClient

    async def _main():
        client = AsyncIOMotorClient(os.environ["MONGO_URL"])
        try:
            return await coro_factory(client[os.environ["DB_NAME"]])
        finally:
            client.close()
    return asyncio.run(_main())


# ----------------- fixtures -----------------
@pytest.fixture(scope="module")
def demo_session():
    return login(DEMO_EMAIL, DEMO_PASSWORD)


@pytest.fixture(scope="module")
def disp_session():
    return login(DISP_EMAIL, DISP_PASSWORD)


@pytest.fixture(scope="module")
def tech_session():
    return login(TECH_EMAIL, TECH_PASSWORD)


@pytest.fixture(scope="module")
def super_session():
    return login(SUPER_EMAIL, SUPER_PASSWORD)


@pytest.fixture
def created_recurring_ids():
    ids: list[str] = []
    yield ids
    if not ids:
        return

    async def cleanup(db):
        await db.recurring_jobs.delete_many({"id": {"$in": ids}})
        await db.jobs.delete_many({"recurring_id": {"$in": ids}})
    run_db(cleanup)


# ============================================================
#  REGRESSION: baseline still alive (smoke a few core endpoints)
# ============================================================
class TestRegressionSmoke:
    def test_auth_me(self, demo_session):
        r = demo_session.get(f"{API}/auth/me", timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert d["user"]["email"] == DEMO_EMAIL
        assert d["user"]["email_verified"] is True

    def test_list_jobs(self, demo_session):
        r = demo_session.get(f"{API}/jobs", timeout=30)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_list_customers(self, demo_session):
        r = demo_session.get(f"{API}/customers", timeout=30)
        assert r.status_code == 200

    def test_list_users(self, demo_session):
        r = demo_session.get(f"{API}/users", timeout=30)
        assert r.status_code == 200

    def test_activity_feed(self, demo_session):
        r = demo_session.get(f"{API}/activity?limit=5", timeout=30)
        assert r.status_code == 200

    def test_roles_config(self, demo_session):
        r = demo_session.get(f"{API}/config/roles", timeout=30)
        assert r.status_code == 200
        assert "roles" in r.json()


# ============================================================
#  Verify-email invite gate
# ============================================================
class TestInviteVerifyGate:
    """New user (email_verified=False) should be blocked from /users/invite."""

    @pytest.fixture
    def new_unverified_owner(self):
        # Register a brand new user (creates company + owner, email_verified=False by default)
        suffix = uuid.uuid4().hex[:8]
        email = f"test_unv_{suffix}@example.com"
        s = requests.Session()
        r = s.post(f"{API}/auth/register", json={
            "name": f"Unv User {suffix}",
            "email": email,
            "password": "Strong1234!",
            "company_name": f"TEST_unv_co_{suffix}",
        }, timeout=30)
        assert r.status_code == 200, f"register failed: {r.status_code} {r.text}"
        yield s, email

        async def cleanup(db):
            u = await db.users.find_one({"email": email}, {"_id": 0})
            if u:
                await db.companies.delete_many({"id": u.get("company_id")})
            await db.users.delete_many({"email": email})
        run_db(cleanup)

    def test_unverified_owner_invite_blocked(self, new_unverified_owner):
        s, email = new_unverified_owner
        r = s.post(f"{API}/users/invite", json={
            "name": "Should Fail",
            "email": f"target_{uuid.uuid4().hex[:8]}@example.com",
            "role": "technician",
        }, timeout=30)
        assert r.status_code == 403, f"expected 403 got {r.status_code}: {r.text}"
        detail = (r.json().get("detail") or "").lower()
        assert "verify" in detail and "email" in detail

    def test_verified_demo_owner_can_invite(self, demo_session):
        target_email = f"test_invite_{uuid.uuid4().hex[:8]}@example.com"
        r = demo_session.post(f"{API}/users/invite", json={
            "name": "Test Invite",
            "email": target_email,
            "role": "technician",
        }, timeout=30)
        assert r.status_code == 200, f"verified owner invite failed: {r.status_code} {r.text}"
        # cleanup
        async def cleanup(db):
            await db.users.delete_many({"email": target_email})
        run_db(cleanup)


# ============================================================
#  Recurring jobs CRUD + lifecycle
# ============================================================
class TestRecurringJobs:
    def test_list_recurring_empty_ok(self, demo_session):
        r = demo_session.get(f"{API}/recurring-jobs", timeout=30)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_create_monthly_autofills_interval(self, demo_session, created_recurring_ids):
        body = {
            "title": "TEST_recur_monthly",
            "address": "1 Test St, Austin TX 78701",
            "cadence": "monthly",
            "duration_min": 60,
            "price": 99.0,
        }
        r = demo_session.post(f"{API}/recurring-jobs", json=body, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["cadence"] == "monthly"
        assert d["interval_days"] == 30
        assert d["active"] is True
        assert "id" in d and "next_run_at" in d
        created_recurring_ids.append(d["id"])

    def test_create_custom_requires_interval(self, demo_session):
        r = demo_session.post(f"{API}/recurring-jobs", json={
            "title": "TEST_recur_custom_bad",
            "cadence": "custom",
        }, timeout=30)
        assert r.status_code == 400
        assert "interval_days" in (r.json().get("detail") or "").lower()

    def test_create_custom_with_interval(self, demo_session, created_recurring_ids):
        r = demo_session.post(f"{API}/recurring-jobs", json={
            "title": "TEST_recur_custom_ok",
            "cadence": "custom",
            "interval_days": 10,
        }, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["cadence"] == "custom"
        assert d["interval_days"] == 10
        created_recurring_ids.append(d["id"])

    def test_create_all_cadences(self, demo_session, created_recurring_ids):
        expected = {"weekly": 7, "biweekly": 14, "monthly": 30,
                    "quarterly": 90, "annually": 365}
        for cad, days in expected.items():
            r = demo_session.post(f"{API}/recurring-jobs", json={
                "title": f"TEST_recur_{cad}",
                "cadence": cad,
            }, timeout=30)
            assert r.status_code == 200, f"{cad}: {r.text}"
            d = r.json()
            assert d["interval_days"] == days, f"{cad} expected {days} got {d['interval_days']}"
            created_recurring_ids.append(d["id"])

    def test_patch_updates_interval_when_cadence_changes(self, demo_session, created_recurring_ids):
        # create monthly then patch to weekly
        c = demo_session.post(f"{API}/recurring-jobs", json={
            "title": "TEST_recur_patch", "cadence": "monthly",
        }, timeout=30).json()
        created_recurring_ids.append(c["id"])

        r = demo_session.patch(f"{API}/recurring-jobs/{c['id']}",
                               json={"cadence": "weekly"}, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["cadence"] == "weekly"
        assert d["interval_days"] == 7

    def test_patch_custom_changes_interval(self, demo_session, created_recurring_ids):
        c = demo_session.post(f"{API}/recurring-jobs", json={
            "title": "TEST_recur_patch2", "cadence": "custom", "interval_days": 5,
        }, timeout=30).json()
        created_recurring_ids.append(c["id"])
        r = demo_session.patch(f"{API}/recurring-jobs/{c['id']}",
                               json={"interval_days": 21}, timeout=30)
        assert r.status_code == 200
        assert r.json()["interval_days"] == 21

    def test_patch_no_fields_400(self, demo_session, created_recurring_ids):
        c = demo_session.post(f"{API}/recurring-jobs", json={
            "title": "TEST_recur_empty_patch", "cadence": "weekly",
        }, timeout=30).json()
        created_recurring_ids.append(c["id"])
        r = demo_session.patch(f"{API}/recurring-jobs/{c['id']}", json={}, timeout=30)
        assert r.status_code == 400

    def test_patch_not_found(self, demo_session):
        r = demo_session.patch(f"{API}/recurring-jobs/{uuid.uuid4()}",
                               json={"title": "x"}, timeout=30)
        assert r.status_code == 404

    def test_run_force_materializes(self, demo_session, created_recurring_ids):
        # create + force-run
        c = demo_session.post(f"{API}/recurring-jobs", json={
            "title": "TEST_recur_runforce",
            "address": "10 Run St, Austin TX 78702",
            "cadence": "monthly",
            "customer_name": "Run Cust",
            "duration_min": 45,
            "price": 150.0,
        }, timeout=30).json()
        rid = c["id"]
        created_recurring_ids.append(rid)

        r = demo_session.post(f"{API}/recurring-jobs/{rid}/run", timeout=30)
        assert r.status_code == 200, r.text
        job = r.json()
        assert job["source"] == "recurring"
        assert job["recurring_id"] == rid
        assert job["title"] == "TEST_recur_runforce"
        assert job["status"] == "scheduled"

        # verify the job exists via /jobs and recurring next_run_at advanced
        rec = demo_session.get(f"{API}/recurring-jobs", timeout=30).json()
        target = next((x for x in rec if x["id"] == rid), None)
        assert target is not None
        nra = datetime.fromisoformat(target["next_run_at"])
        if nra.tzinfo is None:
            nra = nra.replace(tzinfo=timezone.utc)
        delta = nra - datetime.now(timezone.utc)
        # ~30 days ahead (tolerance ±1 day)
        assert timedelta(days=29) <= delta <= timedelta(days=31), f"delta={delta}"

    def test_get_jobs_materializes_due(self, demo_session, created_recurring_ids):
        # next_run_at defaults to now -> immediately due
        c = demo_session.post(f"{API}/recurring-jobs", json={
            "title": "TEST_recur_listmat", "cadence": "weekly",
        }, timeout=30).json()
        rid = c["id"]
        created_recurring_ids.append(rid)

        r = demo_session.get(f"{API}/jobs", timeout=30)
        assert r.status_code == 200
        jobs = r.json()
        # at least one job created via this recurring template
        mat = [j for j in jobs if j.get("recurring_id") == rid]
        assert len(mat) >= 1, "GET /api/jobs did not materialize due recurring"
        assert mat[0].get("source") == "recurring"

    def test_activity_events_logged(self, demo_session, created_recurring_ids):
        c = demo_session.post(f"{API}/recurring-jobs", json={
            "title": "TEST_recur_activity", "cadence": "monthly",
        }, timeout=30).json()
        rid = c["id"]
        created_recurring_ids.append(rid)
        demo_session.post(f"{API}/recurring-jobs/{rid}/run", timeout=30)

        feed = demo_session.get(f"{API}/activity?limit=50", timeout=30).json()
        actions = {a.get("action") for a in feed}
        assert "recurring.created" in actions
        assert "recurring.materialized" in actions

    def test_delete_owner_ok(self, demo_session, created_recurring_ids):
        c = demo_session.post(f"{API}/recurring-jobs", json={
            "title": "TEST_recur_del_owner", "cadence": "weekly",
        }, timeout=30).json()
        rid = c["id"]
        r = demo_session.delete(f"{API}/recurring-jobs/{rid}", timeout=30)
        assert r.status_code == 200
        assert r.json().get("ok") is True

        feed = demo_session.get(f"{API}/activity?limit=50", timeout=30).json()
        assert any(a.get("action") == "recurring.deleted" for a in feed)

    def test_delete_dispatcher_ok(self, demo_session, disp_session, created_recurring_ids):
        # owner creates, dispatcher deletes -> allowed
        c = demo_session.post(f"{API}/recurring-jobs", json={
            "title": "TEST_recur_del_disp", "cadence": "weekly",
        }, timeout=30).json()
        rid = c["id"]
        r = disp_session.delete(f"{API}/recurring-jobs/{rid}", timeout=30)
        assert r.status_code == 200

    def test_delete_technician_forbidden(self, demo_session, tech_session, created_recurring_ids):
        c = demo_session.post(f"{API}/recurring-jobs", json={
            "title": "TEST_recur_del_tech", "cadence": "weekly",
        }, timeout=30).json()
        rid = c["id"]
        created_recurring_ids.append(rid)
        r = tech_session.delete(f"{API}/recurring-jobs/{rid}", timeout=30)
        assert r.status_code == 403

    def test_run_not_found(self, demo_session):
        r = demo_session.post(f"{API}/recurring-jobs/{uuid.uuid4()}/run", timeout=30)
        assert r.status_code == 404


# ============================================================
#  CSV Exports
# ============================================================
class TestCSVExports:
    @pytest.mark.parametrize("endpoint,first_col", [
        ("jobs", "id"),
        ("customers", "id"),
        ("payments", "id"),
    ])
    def test_export_owner_ok(self, demo_session, endpoint, first_col):
        r = demo_session.get(f"{API}/exports/{endpoint}.csv", timeout=30)
        assert r.status_code == 200, r.text
        ct = r.headers.get("content-type", "")
        assert "text/csv" in ct, f"content-type={ct}"
        cd = r.headers.get("content-disposition", "")
        assert "attachment" in cd and f"{endpoint}.csv" in cd
        body = r.text
        lines = body.strip().splitlines()
        assert len(lines) >= 1, "CSV missing header"
        header = lines[0]
        assert header.split(",")[0] == first_col

    def test_export_technician_forbidden(self, tech_session):
        for ep in ("jobs", "customers", "payments"):
            r = tech_session.get(f"{API}/exports/{ep}.csv", timeout=30)
            assert r.status_code == 403, f"{ep} expected 403 got {r.status_code}"

    def test_export_dispatcher_forbidden(self, disp_session):
        # dispatcher is NOT in (owner, accountant, super_admin)
        r = disp_session.get(f"{API}/exports/jobs.csv", timeout=30)
        assert r.status_code == 403

    def test_export_date_filter(self, demo_session):
        # future date range -> rows may be empty but still 200 + header
        future_from = (datetime.now(timezone.utc) + timedelta(days=365)).isoformat()
        future_to = (datetime.now(timezone.utc) + timedelta(days=400)).isoformat()
        r = demo_session.get(
            f"{API}/exports/jobs.csv",
            params={"from": future_from, "to": future_to},
            timeout=30,
        )
        assert r.status_code == 200
        lines = r.text.strip().splitlines()
        # header always present
        assert len(lines) >= 1
        assert lines[0].startswith("id,")


# ============================================================
#  Route optimization
# ============================================================
class TestRouteOptimize:
    @pytest.fixture
    def route_jobs(self, demo_session):
        # Resolve tech_id via /users
        users = demo_session.get(f"{API}/users", timeout=30).json()
        tech = next((u for u in users if u["email"] == TECH_EMAIL), None)
        assert tech, "tech user not found"
        tech_id = tech["id"]

        # Today's date in UTC
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        # Create 3 jobs assigned to tech today with different ZIPs (out of order)
        base = datetime.now(timezone.utc).replace(hour=9, minute=0, second=0, microsecond=0)
        addrs = [
            ("500 Maple St, Austin TX 78705", 90),  # zip3 high
            ("100 Oak Ave, Austin TX 78701", 60),   # zip1 low, low street
            ("250 Pine Rd, Austin TX 78702", 45),   # zip2 mid
        ]
        ids = []
        for i, (addr, dur) in enumerate(addrs):
            r = demo_session.post(f"{API}/jobs", json={
                "title": f"TEST_route_{i}",
                "customer_name": f"Route Cust {i}",
                "address": addr,
                "job_type": "HVAC",
                "assigned_to": tech_id,
                "scheduled_at": (base + timedelta(hours=i * 2)).isoformat(),
                "duration_min": dur,
                "price": 100.0,
                "status": "scheduled",
            }, timeout=30)
            assert r.status_code in (200, 201), r.text
            ids.append(r.json()["id"])

        yield {"tech_id": tech_id, "date": today, "job_ids": ids, "addrs": addrs}

        async def cleanup(db):
            await db.jobs.delete_many({"id": {"$in": ids}})
        run_db(cleanup)

    def test_optimize_dry_run_returns_plan_no_write(self, demo_session, route_jobs):
        body = {
            "technician_id": route_jobs["tech_id"],
            "date": route_jobs["date"],
            "gap_min": 30,
            "dry_run": True,
        }
        r = demo_session.post(f"{API}/jobs/optimize-route", json=body, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["ok"] is True
        assert d["dry_run"] is True
        assert d["reordered"] >= 3
        # order should be by zip ascending: 78701, 78702, 78705
        order = [p["address"] for p in d["jobs"]]
        zip_order = [a.split()[-1] for a in order]
        assert zip_order == sorted(zip_order), f"ZIPs not sorted: {zip_order}"

        # dry run shouldn't have written: fetch a job, scheduled_at unchanged
        before = {p["id"]: p["old_scheduled_at"] for p in d["jobs"]}
        all_jobs = demo_session.get(f"{API}/jobs", timeout=30).json()
        for j in all_jobs:
            if j["id"] in before:
                assert j["scheduled_at"] == before[j["id"]], "dry_run mutated jobs"

    def test_optimize_writes_and_logs(self, demo_session, route_jobs):
        body = {
            "technician_id": route_jobs["tech_id"],
            "date": route_jobs["date"],
            "gap_min": 30,
            "dry_run": False,
        }
        r = demo_session.post(f"{API}/jobs/optimize-route", json=body, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["dry_run"] is False
        plan = d["jobs"]
        assert len(plan) >= 3

        # Verify time spacing: each job's new_scheduled_at >= prev + duration + gap
        for prev, cur in zip(plan, plan[1:]):
            t_prev = datetime.fromisoformat(prev["new_scheduled_at"])
            t_cur = datetime.fromisoformat(cur["new_scheduled_at"])
            expected_gap = timedelta(minutes=int(prev["duration_min"]) + body["gap_min"])
            actual_gap = t_cur - t_prev
            assert actual_gap == expected_gap, \
                f"gap mismatch: {actual_gap} vs {expected_gap}"

        # Verify persistence
        all_jobs = demo_session.get(f"{API}/jobs", timeout=30).json()
        for p in plan:
            j = next(x for x in all_jobs if x["id"] == p["id"])
            assert j["scheduled_at"] == p["new_scheduled_at"]

        # Activity logged
        feed = demo_session.get(f"{API}/activity?limit=30", timeout=30).json()
        assert any(a.get("action") == "route.optimized" for a in feed)

    def test_optimize_technician_forbidden(self, tech_session, route_jobs):
        r = tech_session.post(f"{API}/jobs/optimize-route", json={
            "technician_id": route_jobs["tech_id"],
            "date": route_jobs["date"],
        }, timeout=30)
        assert r.status_code == 403

    def test_optimize_dispatcher_allowed(self, disp_session, route_jobs):
        r = disp_session.post(f"{API}/jobs/optimize-route", json={
            "technician_id": route_jobs["tech_id"],
            "date": route_jobs["date"],
            "dry_run": True,
        }, timeout=30)
        assert r.status_code == 200

    def test_optimize_no_jobs_returns_empty(self, demo_session, route_jobs):
        r = demo_session.post(f"{API}/jobs/optimize-route", json={
            "technician_id": str(uuid.uuid4()),
            "date": route_jobs["date"],
            "dry_run": True,
        }, timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert d["reordered"] == 0
        assert d["jobs"] == []
