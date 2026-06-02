"""Iteration-14 — A1 Field Pro v1.13.

Tests:
- GET /api/dashboard/leaderboard (owner; sort/shape)
- GET /api/dashboard/recurring-forecast (owner; shape)
- GET /api/me/push-prefs defaults
- PUT /api/me/push-prefs persists; GET reflects
- send_push_to_user honors prefs (via direct DB seed + POST /api/push/test for quiet hours;
  direct function call for tag-based skip)
- Geocoding hook on POST/PATCH /api/jobs; cache reuse
- WS heartbeat ping after 25s idle (skippable; this test is opt-in via env A1_RUN_WS_HEARTBEAT=1)
"""
import os
import asyncio
import json
import time
import pytest
import requests
import websockets
from pathlib import Path

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL")
if not BASE_URL:
    env_file = Path("/app/frontend/.env")
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip()
BASE_URL = BASE_URL.rstrip("/")
API = f"{BASE_URL}/api"
WS_URL = BASE_URL.replace("https://", "wss://").replace("http://", "ws://") + "/api/ws"

DEMO = ("demo@a1fieldpro.com", "Demo1234!")
TECH = ("tech@a1fieldpro.com", "Demo1234!")


def _login(email, pw):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": pw}, timeout=20)
    assert r.status_code == 200, f"login failed for {email}: {r.status_code} {r.text}"
    token = r.cookies.get("access_token")
    assert token, f"no access_token cookie: {dict(r.cookies)}"
    return token


def _bearer(t):
    return {"Authorization": f"Bearer {t}"}


@pytest.fixture(scope="module")
def owner_token():
    return _login(*DEMO)


@pytest.fixture(scope="module")
def tech_token():
    return _login(*TECH)


# ---------- Dashboard widgets ----------
class TestLeaderboard:
    def test_leaderboard_returns_list(self, owner_token):
        r = requests.get(f"{API}/dashboard/leaderboard", headers=_bearer(owner_token), timeout=20)
        assert r.status_code == 200, r.text
        data = r.json()
        assert isinstance(data, list)
        # Validate row shape if any
        for row in data:
            assert set(["tech_id", "name", "ratings_count", "rating_avg", "tip_total", "revenue"]).issubset(row.keys())
            assert isinstance(row["rating_avg"], (int, float))
            assert isinstance(row["tip_total"], (int, float))
        # Validate sort order: rating_avg DESC, then tip_total DESC
        for i in range(len(data) - 1):
            a, b = data[i], data[i + 1]
            assert (a["rating_avg"], a["tip_total"]) >= (b["rating_avg"], b["tip_total"])

    def test_leaderboard_days_param(self, owner_token):
        r = requests.get(f"{API}/dashboard/leaderboard?days=7", headers=_bearer(owner_token), timeout=20)
        assert r.status_code == 200
        assert isinstance(r.json(), list)


class TestRecurringForecast:
    def test_forecast_shape(self, owner_token):
        r = requests.get(f"{API}/dashboard/recurring-forecast", headers=_bearer(owner_token), timeout=20)
        assert r.status_code == 200, r.text
        data = r.json()
        for k in ("horizon_days", "total_expected", "active_plans", "annual_contract_value", "plans"):
            assert k in data, f"missing key: {k}"
        assert data["horizon_days"] == 30
        assert isinstance(data["plans"], list)
        for p in data["plans"]:
            for k in ("id", "title", "customer_name", "cadence", "interval_days",
                      "price", "occurrences", "expected_revenue", "next_run_at"):
                assert k in p, f"missing plan key: {k} in {p}"

    def test_forecast_custom_days(self, owner_token):
        r = requests.get(f"{API}/dashboard/recurring-forecast?days=60", headers=_bearer(owner_token), timeout=20)
        assert r.status_code == 200
        assert r.json()["horizon_days"] == 60


# ---------- Push prefs ----------
class TestPushPrefs:
    def test_defaults(self, tech_token):
        # Reset to default first (PUT with all True, null quiet hours)
        requests.put(f"{API}/me/push-prefs", headers=_bearer(tech_token), json={
            "job_assigned": True, "job_rescheduled": True, "payment_received": True,
            "tip_received": True, "rating_created": True, "rating_low_alert": True,
            "recurring_materialized": True,
        }, timeout=20)
        r = requests.get(f"{API}/me/push-prefs", headers=_bearer(tech_token), timeout=20)
        assert r.status_code == 200, r.text
        d = r.json()
        for k in ("job_assigned", "job_rescheduled", "payment_received", "tip_received",
                  "rating_created", "rating_low_alert", "recurring_materialized"):
            assert d.get(k) is True, f"default for {k} should be True; got {d}"
        # quiet hours should be None
        assert d.get("quiet_hours_start") is None
        assert d.get("quiet_hours_end") is None

    def test_put_persists(self, tech_token):
        payload = {
            "job_assigned": False, "job_rescheduled": True, "payment_received": False,
            "tip_received": True, "rating_created": False, "rating_low_alert": True,
            "recurring_materialized": False,
            "quiet_hours_start": 22, "quiet_hours_end": 7,
        }
        r = requests.put(f"{API}/me/push-prefs", headers=_bearer(tech_token), json=payload, timeout=20)
        assert r.status_code == 200, r.text
        assert r.json()["ok"] is True
        # GET reflects
        g = requests.get(f"{API}/me/push-prefs", headers=_bearer(tech_token), timeout=20).json()
        for k, v in payload.items():
            assert g[k] == v, f"{k}: expected {v} got {g.get(k)}"
        # Reset to defaults
        requests.put(f"{API}/me/push-prefs", headers=_bearer(tech_token), json={
            "job_assigned": True, "job_rescheduled": True, "payment_received": True,
            "tip_received": True, "rating_created": True, "rating_low_alert": True,
            "recurring_materialized": True,
        }, timeout=20)


# ---------- Geocoding hook ----------
class TestGeocode:
    @pytest.fixture(scope="class")
    def created_jobs(self, owner_token):
        ids = {}
        # 1) Famous address
        r = requests.post(f"{API}/jobs", headers=_bearer(owner_token), json={
            "title": "TEST_geo_white_house",
            "address": "White House, Washington DC",
            "status": "unscheduled",
        }, timeout=20)
        assert r.status_code == 200, r.text
        ids["wh1"] = r.json()["id"]
        # 2) Same address -> should hit cache
        r2 = requests.post(f"{API}/jobs", headers=_bearer(owner_token), json={
            "title": "TEST_geo_white_house_2",
            "address": "White House, Washington DC",
            "status": "unscheduled",
        }, timeout=20)
        assert r2.status_code == 200, r2.text
        ids["wh2"] = r2.json()["id"]
        # 3) No-address job
        r3 = requests.post(f"{API}/jobs", headers=_bearer(owner_token), json={
            "title": "TEST_geo_no_addr",
            "status": "unscheduled",
        }, timeout=20)
        assert r3.status_code == 200, r3.text
        ids["none"] = r3.json()["id"]
        yield ids
        # cleanup
        for jid in ids.values():
            try:
                requests.delete(f"{API}/jobs/{jid}", headers=_bearer(owner_token), timeout=10)
            except Exception:
                pass

    def _poll_for_location(self, owner_token, job_id, timeout=15):
        deadline = time.time() + timeout
        last = None
        while time.time() < deadline:
            r = requests.get(f"{API}/jobs/{job_id}", headers=_bearer(owner_token), timeout=10)
            assert r.status_code == 200
            last = r.json()
            if last.get("location") and last["location"].get("lat") is not None:
                return last
            time.sleep(0.7)
        return last

    def test_post_job_geocodes(self, owner_token, created_jobs):
        job = self._poll_for_location(owner_token, created_jobs["wh1"])
        assert job is not None
        loc = job.get("location") or {}
        assert "lat" in loc and "lng" in loc, f"no location on geocoded job: {job}"
        # White House lat~38.8977 lng~-77.0365
        assert 38.5 < loc["lat"] < 39.2, f"unexpected lat {loc['lat']}"
        assert -78 < loc["lng"] < -76.5, f"unexpected lng {loc['lng']}"

    def test_second_job_uses_cache(self, owner_token, created_jobs):
        # second job with same address should also have location (from cache, fast)
        job = self._poll_for_location(owner_token, created_jobs["wh2"], timeout=8)
        loc = (job or {}).get("location") or {}
        assert loc.get("lat") is not None, f"second job missing location: {job}"
        # Verify cache row exists (via direct DB)
        from pymongo import MongoClient
        mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
        db_name = os.environ.get("DB_NAME", "a1fieldpro")
        cli = MongoClient(mongo_url)
        row = cli[db_name].geocode_cache.find_one({"address": "white house, washington dc"})
        assert row is not None, "geocode_cache row missing for normalized address"
        assert row.get("lat") is not None
        cli.close()

    def test_no_address_no_location(self, owner_token, created_jobs):
        r = requests.get(f"{API}/jobs/{created_jobs['none']}", headers=_bearer(owner_token), timeout=10)
        assert r.status_code == 200
        assert r.json().get("location") is None

    def test_patch_address_regeocodes(self, owner_token):
        # Create empty-address job
        r = requests.post(f"{API}/jobs", headers=_bearer(owner_token), json={
            "title": "TEST_geo_patch",
            "status": "unscheduled",
        }, timeout=20)
        assert r.status_code == 200
        jid = r.json()["id"]
        try:
            assert r.json().get("location") is None
            # PATCH with a new famous address
            p = requests.patch(f"{API}/jobs/{jid}", headers=_bearer(owner_token), json={
                "address": "Eiffel Tower, Paris, France",
            }, timeout=20)
            assert p.status_code == 200, p.text
            # poll
            deadline = time.time() + 15
            loc = None
            while time.time() < deadline:
                g = requests.get(f"{API}/jobs/{jid}", headers=_bearer(owner_token), timeout=10).json()
                if g.get("location") and g["location"].get("lat") is not None:
                    loc = g["location"]; break
                time.sleep(0.7)
            assert loc is not None, "PATCH did not trigger re-geocode"
            # Eiffel Tower ~48.858, 2.294
            assert 48.5 < loc["lat"] < 49.2
            assert 2.0 < loc["lng"] < 2.6
        finally:
            requests.delete(f"{API}/jobs/{jid}", headers=_bearer(owner_token), timeout=10)


# ---------- Push prefs enforcement via /api/push/test ----------
class TestPushPrefsEnforcement:
    def test_quiet_hours_skips(self, tech_token):
        """Set quiet hours that include current UTC hour -> push should be skipped."""
        from datetime import datetime, timezone as _tz
        h = datetime.now(_tz.utc).hour
        # window [h-1, h+2) -> covers current
        qs = (h - 1) % 24
        qe = (h + 2) % 24
        prefs = {
            "job_assigned": True, "job_rescheduled": True, "payment_received": True,
            "tip_received": True, "rating_created": True, "rating_low_alert": True,
            "recurring_materialized": True,
            "quiet_hours_start": qs, "quiet_hours_end": qe,
        }
        r = requests.put(f"{API}/me/push-prefs", headers=_bearer(tech_token), json=prefs, timeout=20)
        assert r.status_code == 200
        try:
            t = requests.post(f"{API}/push/test", headers=_bearer(tech_token),
                              json={"title": "T", "body": "B"}, timeout=20)
            assert t.status_code == 200, t.text
            data = t.json()
            assert data.get("skipped") is True, f"expected skipped=True during quiet hours, got {data}"
            assert data.get("sent") == 0
        finally:
            # reset
            requests.put(f"{API}/me/push-prefs", headers=_bearer(tech_token), json={
                "job_assigned": True, "job_rescheduled": True, "payment_received": True,
                "tip_received": True, "rating_created": True, "rating_low_alert": True,
                "recurring_materialized": True,
            }, timeout=20)

    def test_outside_quiet_hours_not_skipped(self, tech_token):
        """Without quiet hours, /api/push/test returns skipped:false (sent=0 if no subs)."""
        # reset prefs
        requests.put(f"{API}/me/push-prefs", headers=_bearer(tech_token), json={
            "job_assigned": True, "job_rescheduled": True, "payment_received": True,
            "tip_received": True, "rating_created": True, "rating_low_alert": True,
            "recurring_materialized": True,
        }, timeout=20)
        t = requests.post(f"{API}/push/test", headers=_bearer(tech_token),
                          json={"title": "T", "body": "B"}, timeout=20)
        assert t.status_code == 200
        data = t.json()
        assert data.get("skipped") is False, f"expected skipped=False outside quiet hours, got {data}"


# ---------- send_push_to_user tag-prefix unit test (direct) ----------
@pytest.mark.asyncio
async def test_send_push_pay_skipped_when_payment_received_false():
    """Directly invoke send_push_to_user with tag='pay-xxx' and prefs payment_received=False."""
    import sys
    sys.path.insert(0, "/app/backend")
    import push_service
    push_service._VAPID_BROKEN = False  # reset module-level flag from prior tests
    from push_service import send_push_to_user
    from deps import db
    # Find tech user id
    user = await db.users.find_one({"email": "tech@a1fieldpro.com"}, {"id": 1, "_id": 0})
    assert user, "tech user not found"
    uid = user["id"]
    # Set prefs payment_received=False, no quiet hours
    await db.users.update_one(
        {"id": uid},
        {"$set": {"push_prefs": {
            "job_assigned": True, "job_rescheduled": True, "payment_received": False,
            "tip_received": True, "rating_created": True, "rating_low_alert": True,
            "recurring_materialized": True,
            "quiet_hours_start": None, "quiet_hours_end": None,
        }}},
    )
    try:
        res = await send_push_to_user(uid, {"title": "Paid", "body": "", "tag": "pay-abc123"})
        assert res.get("sent") == 0
        assert res.get("skipped") is True, f"expected skipped True when payment_received=False; got {res}"
    finally:
        # reset to defaults
        await db.users.update_one(
            {"id": uid},
            {"$set": {"push_prefs": {
                "job_assigned": True, "job_rescheduled": True, "payment_received": True,
                "tip_received": True, "rating_created": True, "rating_low_alert": True,
                "recurring_materialized": True,
                "quiet_hours_start": None, "quiet_hours_end": None,
            }}},
        )


# ---------- WS connect/disconnect (heartbeat optional via env) ----------
class TestWSHeartbeat:
    @pytest.mark.asyncio
    async def test_ws_connect_disconnect_no_error(self, owner_token):
        url = f"{WS_URL}?token={owner_token}"
        async with websockets.connect(url, open_timeout=10) as ws:
            hello = await asyncio.wait_for(ws.recv(), timeout=10)
            msg = json.loads(hello)
            assert msg.get("type") == "hello"
        # closes cleanly

    @pytest.mark.skipif(os.environ.get("A1_RUN_WS_HEARTBEAT") != "1",
                        reason="long-running heartbeat test; set A1_RUN_WS_HEARTBEAT=1 to run")
    @pytest.mark.asyncio
    async def test_ws_heartbeat_ping_after_idle(self, owner_token):
        url = f"{WS_URL}?token={owner_token}"
        async with websockets.connect(url, open_timeout=10) as ws:
            # consume hello
            await asyncio.wait_for(ws.recv(), timeout=10)
            # wait ~27s for ping
            got_ping = False
            try:
                while True:
                    m = await asyncio.wait_for(ws.recv(), timeout=30)
                    if json.loads(m).get("type") == "ping":
                        got_ping = True; break
            except asyncio.TimeoutError:
                pass
            assert got_ping, "expected heartbeat ping within 30s"
            # respond and ensure loop continues
            await ws.send("pong")
            # short wait for connection still alive
            await asyncio.sleep(1)
