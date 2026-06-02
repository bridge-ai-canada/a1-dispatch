"""Iteration-11 tests: v1.10 Web-Push pipeline.

Coverage:
- GET /api/push/public-key (public, no auth)
- POST /api/push/subscribe (auth, upsert, idempotent)
- GET /api/push/subscriptions/me (auth, no keys leaked)
- DELETE /api/push/subscribe?endpoint=... (only owner can remove their own)
- POST /api/push/test (self, cross-role 403, cross-tenant 404, sent=0 with fake keys)
- POST /api/jobs hook (push fires silently to assigned tech, doesn't break create)
- PATCH /api/jobs/{id} hook (reassign + reschedule fire silently)
- requirements.txt contains pywebpush + py-vapid
"""
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
    for line in Path("/app/frontend/.env").read_text().splitlines():
        if line.startswith("REACT_APP_BACKEND_URL="):
            BASE_URL = line.split("=", 1)[1].strip()
            break
BASE_URL = BASE_URL.rstrip("/")
API = f"{BASE_URL}/api"

DEMO = ("demo@a1fieldpro.com", "Demo1234!")
DISP = ("dispatcher@a1fieldpro.com", "Demo1234!")
TECH = ("tech@a1fieldpro.com", "Demo1234!")
SUPER = ("superadmin@a1fieldpro.com", "Super1234!")


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
    r = s.get(f"{API}/auth/me", timeout=30)
    assert r.status_code == 200
    return r.json()


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


def _fake_sub(tag=""):
    """A subscription payload that mimics FCM but won't actually deliver."""
    eid = uuid.uuid4().hex
    return {
        "endpoint": f"https://fcm.googleapis.com/fcm/send/test-{tag}-{eid}",
        "keys": {
            # 65-byte uncompressed P-256 public key base64url-ish
            "p256dh": "BNcRdreALRFXTkOOUHK1EtK2wtaz5Ry4YfYCA_0QTpQtUbVlUls0VJXg7A8u-Ts1XbjhazAkj7I99e8QcYP7DkM",
            "auth": "tBHItJI5svbpez7KI4CCXg",
        },
        "user_agent": "pytest/iteration11",
    }


# ----------------- session fixtures -----------------
@pytest.fixture(scope="module")
def owner():
    return login(*DEMO)


@pytest.fixture(scope="module")
def dispatcher():
    return login(*DISP)


@pytest.fixture(scope="module")
def tech():
    return login(*TECH)


@pytest.fixture(scope="module")
def super_admin():
    return login(*SUPER)


@pytest.fixture(scope="module")
def owner_id(owner):
    return me(owner)["user"]["id"]


@pytest.fixture(scope="module")
def tech_id(tech):
    return me(tech)["user"]["id"]


@pytest.fixture(scope="module")
def disp_id(dispatcher):
    return me(dispatcher)["user"]["id"]


# Cleanup any subscription created in this module
@pytest.fixture(scope="module", autouse=True)
def cleanup_subs():
    yield
    async def _wipe(db):
        await db.push_subscriptions.delete_many({"user_agent": "pytest/iteration11"})
    try:
        run_db(_wipe)
    except Exception:
        pass


# ----------------- 1. requirements.txt -----------------
class TestRequirements:
    def test_pywebpush_listed(self):
        txt = Path("/app/backend/requirements.txt").read_text().lower()
        assert "pywebpush" in txt

    def test_pyvapid_listed(self):
        txt = Path("/app/backend/requirements.txt").read_text().lower()
        assert "py-vapid" in txt


# ----------------- 2. public-key -----------------
class TestPublicKey:
    def test_public_key_no_auth(self):
        # No auth required
        r = requests.get(f"{API}/push/public-key", timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "public_key" in data
        assert isinstance(data["public_key"], str)
        assert len(data["public_key"]) > 50  # base64url'd EC P-256 = ~87 chars

    def test_public_key_matches_env(self):
        r = requests.get(f"{API}/push/public-key", timeout=30)
        assert r.json()["public_key"] == os.environ.get("VAPID_PUBLIC_KEY", "")


# ----------------- 3. subscribe / list / delete -----------------
class TestSubscribeCrud:
    def test_subscribe_requires_auth(self):
        r = requests.post(f"{API}/push/subscribe", json=_fake_sub("noauth"), timeout=30)
        assert r.status_code == 401

    def test_subscribe_creates_row(self, owner, owner_id):
        sub = _fake_sub("a")
        r = owner.post(f"{API}/push/subscribe", json=sub, timeout=30)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["ok"] is True
        assert isinstance(body["id"], str) and len(body["id"]) >= 8

        # verify persisted in DB
        async def _check(db):
            return await db.push_subscriptions.find_one({"endpoint": sub["endpoint"]}, {"_id": 0})
        doc = run_db(_check)
        assert doc is not None
        assert doc["user_id"] == owner_id
        assert doc["active"] is True
        assert doc["keys"]["p256dh"] == sub["keys"]["p256dh"]

    def test_subscribe_is_idempotent(self, owner):
        sub = _fake_sub("idem")
        r1 = owner.post(f"{API}/push/subscribe", json=sub, timeout=30)
        assert r1.status_code == 200
        first_id = r1.json()["id"]
        # Re-subscribe with same endpoint
        r2 = owner.post(f"{API}/push/subscribe", json=sub, timeout=30)
        assert r2.status_code == 200
        assert r2.json()["id"] == first_id  # same row, no duplicate

        async def _count(db):
            return await db.push_subscriptions.count_documents({"endpoint": sub["endpoint"]})
        assert run_db(_count) == 1

    def test_list_my_subscriptions_excludes_keys(self, owner):
        sub = _fake_sub("list")
        owner.post(f"{API}/push/subscribe", json=sub, timeout=30)
        r = owner.get(f"{API}/push/subscriptions/me", timeout=30)
        assert r.status_code == 200
        items = r.json()
        assert isinstance(items, list)
        assert len(items) >= 1
        for it in items:
            assert "keys" not in it, "keys must not be exposed in /me listing"
            assert "endpoint" in it
            assert "user_id" in it

    def test_delete_my_subscription(self, owner):
        sub = _fake_sub("del")
        owner.post(f"{API}/push/subscribe", json=sub, timeout=30)
        r = owner.delete(f"{API}/push/subscribe", params={"endpoint": sub["endpoint"]}, timeout=30)
        assert r.status_code == 200
        assert r.json()["removed"] == 1

        async def _check(db):
            return await db.push_subscriptions.find_one({"endpoint": sub["endpoint"]})
        assert run_db(_check) is None

    def test_delete_not_my_subscription_noop(self, owner, tech):
        # owner subscribes
        sub = _fake_sub("xown")
        owner.post(f"{API}/push/subscribe", json=sub, timeout=30)
        # tech tries to delete owner's endpoint -> filter requires user_id match, so removed=0
        r = tech.delete(f"{API}/push/subscribe", params={"endpoint": sub["endpoint"]}, timeout=30)
        assert r.status_code == 200
        assert r.json()["removed"] == 0

        async def _check(db):
            return await db.push_subscriptions.find_one({"endpoint": sub["endpoint"]})
        # Owner's sub still exists
        assert run_db(_check) is not None


# ----------------- 4. push/test -----------------
class TestPushTest:
    def test_self_send_sent_zero(self, owner):
        # owner has a fake subscription; pywebpush will fail; sent=0 is acceptable
        owner.post(f"{API}/push/subscribe", json=_fake_sub("self"), timeout=30)
        r = owner.post(f"{API}/push/test", json={"title": "Hi", "body": "Yo"}, timeout=30)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["ok"] is True
        assert "sent" in body
        assert "removed" in body
        assert body["sent"] == 0  # fake keys can't deliver

    def test_technician_forbidden_other_user(self, tech, owner_id):
        r = tech.post(f"{API}/push/test", json={"user_id": owner_id}, timeout=30)
        assert r.status_code == 403

    def test_dispatcher_can_send_to_tech(self, dispatcher, tech_id):
        r = dispatcher.post(f"{API}/push/test", json={"user_id": tech_id, "title": "ping"}, timeout=30)
        assert r.status_code == 200
        assert r.json()["ok"] is True

    def test_owner_can_send_to_tech(self, owner, tech_id):
        r = owner.post(f"{API}/push/test", json={"user_id": tech_id}, timeout=30)
        assert r.status_code == 200

    def test_cross_tenant_404_for_owner(self, owner):
        # Create a foreign user in another company to target.
        async def _make_alien(db):
            uid = str(uuid.uuid4())
            cid = str(uuid.uuid4())
            await db.users.insert_one({
                "id": uid, "company_id": cid, "email": f"alien_{uid[:6]}@x.com",
                "name": "Alien", "role": "owner", "active": True, "email_verified": True,
                "mfa_enabled": False,
            })
            return uid, cid
        alien_uid, alien_cid = run_db(_make_alien)
        try:
            r = owner.post(f"{API}/push/test", json={"user_id": alien_uid}, timeout=30)
            assert r.status_code == 404, r.text
            assert "company" in r.json().get("detail", "").lower()
        finally:
            async def _cleanup(db):
                await db.users.delete_one({"id": alien_uid})
            run_db(_cleanup)

    def test_super_admin_bypasses_tenant_guard(self, super_admin):
        # Super admin can target any user (no 404 cross-tenant block)
        async def _make_alien(db):
            uid = str(uuid.uuid4())
            cid = str(uuid.uuid4())
            await db.users.insert_one({
                "id": uid, "company_id": cid, "email": f"alien2_{uid[:6]}@x.com",
                "name": "Alien2", "role": "owner", "active": True, "email_verified": True,
                "mfa_enabled": False,
            })
            return uid
        alien_uid = run_db(_make_alien)
        try:
            r = super_admin.post(f"{API}/push/test", json={"user_id": alien_uid}, timeout=30)
            assert r.status_code == 200, r.text
        finally:
            async def _c(db):
                await db.users.delete_one({"id": alien_uid})
            run_db(_c)


# ----------------- 5. job creation hook -----------------
class TestJobHooks:
    _created_ids = []

    @classmethod
    def teardown_class(cls):
        async def _wipe(db):
            if cls._created_ids:
                await db.jobs.delete_many({"id": {"$in": cls._created_ids}})
        try:
            run_db(_wipe)
        except Exception:
            pass

    def test_create_job_with_assignment_doesnt_500(self, owner, tech_id):
        # Subscribe tech with a fake endpoint so the push path executes against pywebpush.
        tech_sess = login(*TECH)
        tech_sess.post(f"{API}/push/subscribe", json=_fake_sub("jhook"), timeout=30)

        payload = {
            "title": "TEST_push_hook_create",
            "address": "1 Test St 78701",
            "job_type": "HVAC",
            "assigned_to": tech_id,
            "scheduled_at": (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat(),
            "duration_min": 60,
            "price": 100.0,
        }
        r = owner.post(f"{API}/jobs", json=payload, timeout=30)
        assert r.status_code in (200, 201), r.text
        job = r.json()
        self.__class__._created_ids.append(job["id"])
        assert job["assigned_to"] == tech_id
        assert job["title"] == "TEST_push_hook_create"
        # Verify persisted
        g = owner.get(f"{API}/jobs/{job['id']}", timeout=30)
        assert g.status_code == 200

    def test_create_job_without_assignment_ok(self, owner):
        payload = {
            "title": "TEST_push_hook_noassign",
            "address": "2 Test St",
            "job_type": "HVAC",
            "duration_min": 30,
            "price": 50.0,
        }
        r = owner.post(f"{API}/jobs", json=payload, timeout=30)
        assert r.status_code in (200, 201)
        self.__class__._created_ids.append(r.json()["id"])

    def test_create_job_self_assigned_skips_push(self, owner, owner_id):
        # assigned_to == actor → push branch is bypassed; just verify no 500
        payload = {
            "title": "TEST_push_hook_self",
            "address": "3 Test St",
            "job_type": "HVAC",
            "assigned_to": owner_id,
            "duration_min": 30,
            "price": 25.0,
        }
        r = owner.post(f"{API}/jobs", json=payload, timeout=30)
        assert r.status_code in (200, 201)
        self.__class__._created_ids.append(r.json()["id"])

    def test_patch_job_reassign_doesnt_500(self, owner, tech_id, disp_id):
        # create unassigned, then reassign to tech
        c = owner.post(f"{API}/jobs", json={
            "title": "TEST_push_reassign", "address": "4 Test St", "job_type": "HVAC",
            "duration_min": 30, "price": 10.0,
        }, timeout=30)
        assert c.status_code in (200, 201)
        jid = c.json()["id"]
        self.__class__._created_ids.append(jid)

        r = owner.patch(f"{API}/jobs/{jid}", json={"assigned_to": tech_id}, timeout=30)
        assert r.status_code == 200, r.text
        assert r.json()["assigned_to"] == tech_id

    def test_patch_job_reschedule_doesnt_500(self, owner, tech_id):
        c = owner.post(f"{API}/jobs", json={
            "title": "TEST_push_reschedule", "address": "5 Test St", "job_type": "HVAC",
            "assigned_to": tech_id,
            "scheduled_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
            "duration_min": 30, "price": 10.0,
        }, timeout=30)
        assert c.status_code in (200, 201)
        jid = c.json()["id"]
        self.__class__._created_ids.append(jid)

        new_when = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
        r = owner.patch(f"{API}/jobs/{jid}", json={"scheduled_at": new_when}, timeout=30)
        assert r.status_code == 200, r.text
        assert r.json()["scheduled_at"] == new_when


# ----------------- 6. regression smoke -----------------
class TestRegressionSmoke:
    def test_login_owner(self, owner):
        assert owner is not None

    def test_auth_me_owner(self, owner):
        r = owner.get(f"{API}/auth/me", timeout=30)
        assert r.status_code == 200
        assert r.json()["user"]["email"] == DEMO[0]

    def test_jobs_listing(self, owner):
        r = owner.get(f"{API}/jobs", timeout=30)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_customers_listing(self, owner):
        r = owner.get(f"{API}/customers", timeout=30)
        assert r.status_code == 200

    def test_dashboard_stats(self, owner):
        r = owner.get(f"{API}/dashboard/stats", timeout=30)
        assert r.status_code == 200
