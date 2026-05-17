"""Iteration-13 — A1 Field Pro v1.12 Modern Dispatch Board.

Tests:
- POST /api/me/status (TechStatus)
- POST /api/me/location (LocationIn validation)
- GET  /api/team/locations (no _id, scoped to company)
- PATCH /api/jobs/{id}/priority (Literal + 404 cross-tenant)
- JobIn/JobUpdate accept optional `priority` field
- WebSocket /api/ws?token=<jwt>: hello, broadcast on job.create/update/priority/status/location, no cross-tenant leak, close 4401 on bad token
"""
import os
import json
import uuid
import asyncio
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


# ---------- helpers ----------
def _login(email, pw):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": pw}, timeout=20)
    assert r.status_code == 200, f"login failed for {email}: {r.status_code} {r.text}"
    token = r.cookies.get("access_token")
    assert token, f"no access_token cookie: {dict(r.cookies)}"
    return token, r.cookies


def _bearer(token):
    return {"Authorization": f"Bearer {token}"}


def _register_fresh_owner():
    """Creates a brand-new company with a fresh owner; returns (token, user_id, company_id)."""
    suffix = uuid.uuid4().hex[:8]
    email = f"TEST_iter13_{suffix}@example.com"
    payload = {
        "company_name": f"TEST Co {suffix}",
        "industry": "HVAC",
        "name": f"Test Owner {suffix}",
        "email": email,
        "password": "Strong1pass!",
    }
    r = requests.post(f"{API}/auth/register", json=payload, timeout=20)
    assert r.status_code in (200, 201), f"register failed: {r.status_code} {r.text}"
    token = r.cookies.get("access_token")
    me = requests.get(f"{API}/auth/me", headers=_bearer(token), timeout=20).json()
    return token, me["user"]["id"], me["user"]["company_id"], email


@pytest.fixture(scope="module")
def demo_token():
    t, _ = _login(*DEMO)
    return t


@pytest.fixture(scope="module")
def tech_token():
    t, _ = _login(*TECH)
    return t


# ---------- tech status ----------
class TestTechStatus:
    def test_update_status_persists(self, tech_token):
        for s in ("on_route", "on_site", "break", "available"):
            r = requests.post(f"{API}/me/status", json={"status": s},
                              headers=_bearer(tech_token), timeout=15)
            assert r.status_code == 200, r.text
            assert r.json()["status"] == s

        # Verify persistence via team locations (tech is part of demo company)
        r2 = requests.get(f"{API}/team/locations", headers=_bearer(tech_token), timeout=15)
        assert r2.status_code == 200
        me_row = next((u for u in r2.json() if u.get("role") == "technician"), None)
        assert me_row is not None
        assert me_row["tech_status"] == "available"

    def test_invalid_status_422(self, tech_token):
        r = requests.post(f"{API}/me/status", json={"status": "lunch"},
                          headers=_bearer(tech_token), timeout=15)
        assert r.status_code == 422

    def test_status_requires_auth(self):
        r = requests.post(f"{API}/me/status", json={"status": "available"}, timeout=15)
        assert r.status_code == 401


# ---------- GPS location ----------
class TestLocation:
    def test_update_location_ok(self, tech_token):
        r = requests.post(f"{API}/me/location",
                          json={"latitude": 30.2672, "longitude": -97.7431, "accuracy_m": 12.5},
                          headers=_bearer(tech_token), timeout=15)
        assert r.status_code == 200
        assert r.json()["ok"] is True

    def test_location_out_of_range_422(self, tech_token):
        bad_payloads = [
            {"latitude": 91.0, "longitude": 0.0},
            {"latitude": -91.0, "longitude": 0.0},
            {"latitude": 0.0, "longitude": 181.0},
            {"latitude": 0.0, "longitude": -181.0},
        ]
        for p in bad_payloads:
            r = requests.post(f"{API}/me/location", json=p, headers=_bearer(tech_token), timeout=15)
            assert r.status_code == 422, f"expected 422 for {p}, got {r.status_code}"

    def test_team_locations_no_id_and_has_fields(self, demo_token):
        r = requests.get(f"{API}/team/locations", headers=_bearer(demo_token), timeout=15)
        assert r.status_code == 200
        rows = r.json()
        assert isinstance(rows, list) and len(rows) >= 3  # owner, dispatcher, tech
        for u in rows:
            assert "_id" not in u
            assert "id" in u and "name" in u and "role" in u
        # The tech with our seeded location should be visible
        tech = next((u for u in rows if u.get("role") == "technician"), None)
        assert tech is not None
        if tech.get("last_location"):
            loc = tech["last_location"]
            assert -90 <= loc["lat"] <= 90 and -180 <= loc["lng"] <= 180

    def test_team_locations_scoped_to_company(self):
        token, _, _, _ = _register_fresh_owner()
        r = requests.get(f"{API}/team/locations", headers=_bearer(token), timeout=15)
        assert r.status_code == 200
        rows = r.json()
        # Fresh company should only have the new owner (1 user), NOT demo users
        emails_or_names = [u.get("name", "") for u in rows]
        assert len(rows) == 1
        assert "Tom Technician" not in emails_or_names
        assert "Demo Owner" not in emails_or_names


# ---------- Job priority ----------
class TestJobPriority:
    def test_create_job_with_priority(self, demo_token):
        r = requests.post(f"{API}/jobs",
                          json={"title": "TEST_priority_create", "priority": "emergency"},
                          headers=_bearer(demo_token), timeout=15)
        assert r.status_code == 200, r.text
        job = r.json()
        assert job["priority"] == "emergency"
        # Cleanup
        requests.delete(f"{API}/jobs/{job['id']}", headers=_bearer(demo_token), timeout=15)

    def test_default_priority_normal(self, demo_token):
        r = requests.post(f"{API}/jobs", json={"title": "TEST_default_prio"},
                          headers=_bearer(demo_token), timeout=15)
        assert r.status_code == 200
        job = r.json()
        assert job["priority"] == "normal"
        requests.delete(f"{API}/jobs/{job['id']}", headers=_bearer(demo_token), timeout=15)

    def test_patch_priority_valid(self, demo_token):
        # create then patch
        c = requests.post(f"{API}/jobs", json={"title": "TEST_patch_prio"},
                          headers=_bearer(demo_token), timeout=15).json()
        for p in ("low", "high", "emergency", "normal"):
            r = requests.patch(f"{API}/jobs/{c['id']}/priority", json={"priority": p},
                               headers=_bearer(demo_token), timeout=15)
            assert r.status_code == 200, r.text
            assert r.json()["priority"] == p
        requests.delete(f"{API}/jobs/{c['id']}", headers=_bearer(demo_token), timeout=15)

    def test_patch_priority_invalid(self, demo_token):
        c = requests.post(f"{API}/jobs", json={"title": "TEST_invalid_prio"},
                          headers=_bearer(demo_token), timeout=15).json()
        r = requests.patch(f"{API}/jobs/{c['id']}/priority", json={"priority": "urgent"},
                           headers=_bearer(demo_token), timeout=15)
        assert r.status_code == 422
        requests.delete(f"{API}/jobs/{c['id']}", headers=_bearer(demo_token), timeout=15)

    def test_patch_priority_404_cross_tenant(self, demo_token):
        # Create job under fresh tenant
        ft, _, _, _ = _register_fresh_owner()
        j = requests.post(f"{API}/jobs", json={"title": "TEST_other_tenant"},
                          headers=_bearer(ft), timeout=15).json()
        # demo user tries to patch it
        r = requests.patch(f"{API}/jobs/{j['id']}/priority", json={"priority": "high"},
                           headers=_bearer(demo_token), timeout=15)
        assert r.status_code == 404

    def test_patch_priority_404_missing(self, demo_token):
        r = requests.patch(f"{API}/jobs/{uuid.uuid4()}/priority", json={"priority": "high"},
                           headers=_bearer(demo_token), timeout=15)
        assert r.status_code == 404


# ---------- WebSocket ----------
async def _ws_recv_until(ws, want_type, timeout=8.0):
    """Drain messages until we see one with matching type, or timeout returns None."""
    try:
        async with asyncio.timeout(timeout):
            while True:
                raw = await ws.recv()
                msg = json.loads(raw)
                if msg.get("type") == want_type:
                    return msg
    except (asyncio.TimeoutError, TimeoutError):
        return None


class TestWebSocket:
    def test_ws_rejects_bad_token(self):
        async def run():
            try:
                async with websockets.connect(f"{WS_URL}?token=garbage") as ws:
                    await ws.recv()  # should close immediately
                    return ws.close_code
            except websockets.exceptions.ConnectionClosed as e:
                return e.code
            except Exception as e:
                return str(e)
        code = asyncio.run(run())
        # NOTE: server calls close(code=4401) BEFORE accept(), which Starlette converts
        # to an HTTP 403 handshake rejection — the 4401 close code never reaches the
        # client. Accept either form as "rejected"; flagged in report.
        assert code == 4401 or "403" in str(code) or "401" in str(code), \
            f"expected rejection (4401 or HTTP 403/401), got {code}"

    def test_ws_rejects_missing_token(self):
        async def run():
            try:
                async with websockets.connect(WS_URL) as ws:
                    await ws.recv()
                    return ws.close_code
            except Exception as e:
                # Server returns HTTP 422 (missing query) which appears as InvalidStatusCode/HandshakeError
                return type(e).__name__
        result = asyncio.run(run())
        # Either close code or handshake rejection is acceptable
        assert result not in (None, 1000), f"connection should not have succeeded: {result}"

    def test_ws_hello_and_broadcast_job_created(self, demo_token):
        async def run():
            async with websockets.connect(f"{WS_URL}?token={demo_token}") as ws:
                hello = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
                assert hello["type"] == "hello"
                # Trigger an event via REST in a side thread
                created = await asyncio.to_thread(
                    requests.post, f"{API}/jobs",
                    json={"title": "TEST_ws_broadcast", "priority": "high"},
                    headers=_bearer(demo_token), timeout=15,
                )
                assert created.status_code == 200
                job = created.json()
                msg = await _ws_recv_until(ws, "job.created", timeout=6)
                assert msg is not None, "did not receive job.created event"
                assert msg["data"]["id"] == job["id"]
                assert msg["data"]["priority"] == "high"
                # Cleanup
                await asyncio.to_thread(requests.delete, f"{API}/jobs/{job['id']}",
                                        headers=_bearer(demo_token), timeout=15)
                return True
        assert asyncio.run(run())

    def test_ws_broadcast_job_updated_and_priority(self, demo_token):
        async def run():
            async with websockets.connect(f"{WS_URL}?token={demo_token}") as ws:
                await asyncio.wait_for(ws.recv(), timeout=5)  # hello
                # Create
                j = await asyncio.to_thread(
                    requests.post, f"{API}/jobs", json={"title": "TEST_ws_update"},
                    headers=_bearer(demo_token), timeout=15,
                )
                jid = j.json()["id"]
                await _ws_recv_until(ws, "job.created", timeout=6)
                # PATCH job
                await asyncio.to_thread(
                    requests.patch, f"{API}/jobs/{jid}", json={"title": "TEST_ws_update_2"},
                    headers=_bearer(demo_token), timeout=15,
                )
                m1 = await _ws_recv_until(ws, "job.updated", timeout=6)
                assert m1 is not None and m1["data"]["id"] == jid
                # PATCH priority
                await asyncio.to_thread(
                    requests.patch, f"{API}/jobs/{jid}/priority", json={"priority": "emergency"},
                    headers=_bearer(demo_token), timeout=15,
                )
                m2 = await _ws_recv_until(ws, "job.updated", timeout=6)
                assert m2 is not None and m2["data"]["priority"] == "emergency"
                await asyncio.to_thread(requests.delete, f"{API}/jobs/{jid}",
                                        headers=_bearer(demo_token), timeout=15)
                return True
        assert asyncio.run(run())

    def test_ws_broadcast_user_status_and_location(self, demo_token, tech_token):
        async def run():
            async with websockets.connect(f"{WS_URL}?token={demo_token}") as ws:
                await asyncio.wait_for(ws.recv(), timeout=5)  # hello
                await asyncio.to_thread(
                    requests.post, f"{API}/me/status", json={"status": "on_route"},
                    headers=_bearer(tech_token), timeout=15,
                )
                ms = await _ws_recv_until(ws, "user.status", timeout=6)
                assert ms is not None and ms["data"]["status"] == "on_route"

                await asyncio.to_thread(
                    requests.post, f"{API}/me/location",
                    json={"latitude": 31.0, "longitude": -97.0},
                    headers=_bearer(tech_token), timeout=15,
                )
                ml = await _ws_recv_until(ws, "user.location", timeout=6)
                assert ml is not None and ml["data"]["lat"] == 31.0
                return True
        assert asyncio.run(run())

    def test_ws_no_cross_tenant_leak(self, demo_token):
        async def run():
            # Connect as fresh tenant
            fresh_token, _, _, _ = await asyncio.to_thread(_register_fresh_owner)
            async with websockets.connect(f"{WS_URL}?token={fresh_token}") as ws_fresh:
                await asyncio.wait_for(ws_fresh.recv(), timeout=5)  # hello
                # Trigger an event in demo tenant
                created = await asyncio.to_thread(
                    requests.post, f"{API}/jobs",
                    json={"title": "TEST_no_leak"},
                    headers=_bearer(demo_token), timeout=15,
                )
                jid = created.json()["id"]
                # Fresh tenant socket should NOT see this event
                msg = await _ws_recv_until(ws_fresh, "job.created", timeout=4)
                assert msg is None, f"cross-tenant leak: {msg}"
                await asyncio.to_thread(requests.delete, f"{API}/jobs/{jid}",
                                        headers=_bearer(demo_token), timeout=15)
                return True
        assert asyncio.run(run())
