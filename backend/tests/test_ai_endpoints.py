"""Backend tests for AI feature endpoints in routers/ai.py.

Uses the real OpenAI integration via Emergent universal key.
We assert response shape & status — not exact LLM content.
"""
import os
import time
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://a1-dispatch.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

OWNER = {"email": "demo@a1fieldpro.com", "password": "Demo1234!"}
DISPATCHER = {"email": "dispatcher@a1fieldpro.com", "password": "Demo1234!"}
TECH = {"email": "tech@a1fieldpro.com", "password": "Demo1234!"}

AI_TIMEOUT = 90  # AI calls can be slow


def _login(creds):
    r = requests.post(f"{API}/auth/login", json=creds, timeout=30)
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text[:200]}"
    return r.json()["token"]


@pytest.fixture(scope="module")
def owner_token():
    return _login(OWNER)


@pytest.fixture(scope="module")
def owner_headers(owner_token):
    return {"Authorization": f"Bearer {owner_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def dispatcher_headers():
    tok = _login(DISPATCHER)
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def owner_company_id(owner_headers):
    r = requests.get(f"{API}/auth/me", headers=owner_headers, timeout=15)
    assert r.status_code == 200
    return r.json()["user"]["company_id"]


@pytest.fixture(scope="module")
def a_job_id(owner_headers):
    """Get an existing job (any). Skip job-tests if none exists."""
    r = requests.get(f"{API}/jobs", headers=owner_headers, timeout=20)
    if r.status_code != 200:
        pytest.skip(f"Cannot list jobs: {r.status_code}")
    data = r.json()
    jobs = data if isinstance(data, list) else data.get("items") or data.get("jobs") or []
    if not jobs:
        pytest.skip("No jobs available in demo data")
    return jobs[0]["id"]


# ------------------------- 1. Estimate generator -------------------------
class TestEstimateGenerator:
    def test_generate_estimate_shape(self, owner_headers):
        payload = {"prompt": "AC not cooling, 10-year-old 3-ton split system, replace or repair?"}
        r = requests.post(f"{API}/ai/estimates/generate", headers=owner_headers,
                          json=payload, timeout=AI_TIMEOUT)
        assert r.status_code == 200, f"Status {r.status_code}: {r.text[:300]}"
        data = r.json()
        assert "title" in data and "intro" in data and "tiers" in data
        assert isinstance(data["tiers"], list)
        assert len(data["tiers"]) == 3, f"Expected 3 tiers, got {len(data['tiers'])}"
        keys = [t.get("key") for t in data["tiers"]]
        assert "good" in keys and "better" in keys and "best" in keys
        for t in data["tiers"]:
            assert "line_items" in t and isinstance(t["line_items"], list)
            assert "addons" in t and isinstance(t["addons"], list)
            for li in t["line_items"]:
                assert "description" in li
                assert "qty" in li
                assert "unit_price" in li
                assert isinstance(li.get("taxable"), bool)
                assert li.get("kind") in ("service", "material", "labor", "fee")
            for ad in t["addons"]:
                assert ad.get("selected") is False
                assert isinstance(ad.get("taxable"), bool)
                assert ad.get("kind") == "material"
        # better tier featured
        better = next(t for t in data["tiers"] if t.get("key") == "better")
        assert better.get("featured") is True

    def test_generate_estimate_empty_prompt(self, owner_headers):
        r = requests.post(f"{API}/ai/estimates/generate", headers=owner_headers,
                          json={"prompt": "   "}, timeout=15)
        assert r.status_code == 400


# ------------------------- 2. Call summary -------------------------
class TestCallSummary:
    def test_summarize_call_basic(self, owner_headers):
        notes = ("Customer called: AC blowing warm air since yesterday afternoon. "
                 "Wants someone out tomorrow morning. Sounded frustrated. Confirmed address.")
        r = requests.post(f"{API}/ai/calls/summarize", headers=owner_headers,
                          json={"notes": notes}, timeout=AI_TIMEOUT)
        assert r.status_code == 200, f"{r.status_code}: {r.text[:300]}"
        data = r.json()
        assert "summary" in data
        assert data.get("intent") in ("book", "quote", "complaint", "info", "other")
        assert data.get("sentiment") in ("positive", "neutral", "negative")
        assert isinstance(data.get("action_items"), list)
        assert "next_step" in data

    def test_summarize_call_empty_notes(self, owner_headers):
        r = requests.post(f"{API}/ai/calls/summarize", headers=owner_headers,
                          json={"notes": "  "}, timeout=15)
        assert r.status_code == 400


# ------------------------- 3. Tech notes polish -------------------------
class TestTechNotesPolish:
    def test_polish_basic(self, owner_headers):
        r = requests.post(f"{API}/ai/tech-notes/polish", headers=owner_headers,
                          json={"notes": "replaced cap, unit ok now, checked freon"},
                          timeout=AI_TIMEOUT)
        assert r.status_code == 200
        data = r.json()
        assert "polished" in data
        assert isinstance(data["polished"], str)
        assert len(data["polished"]) > 0

    def test_polish_empty_rejected(self, owner_headers):
        r = requests.post(f"{API}/ai/tech-notes/polish", headers=owner_headers,
                          json={"notes": ""}, timeout=15)
        assert r.status_code == 400


# ------------------------- 4. Job summary -------------------------
class TestJobSummary:
    def test_summary_for_existing_job(self, owner_headers, a_job_id):
        r = requests.post(f"{API}/ai/jobs/summarize", headers=owner_headers,
                          json={"job_id": a_job_id}, timeout=AI_TIMEOUT)
        assert r.status_code == 200, f"{r.status_code}: {r.text[:300]}"
        data = r.json()
        assert "summary" in data and isinstance(data["summary"], str)
        assert len(data["summary"]) > 0

    def test_summary_unknown_job_404(self, owner_headers):
        r = requests.post(f"{API}/ai/jobs/summarize", headers=owner_headers,
                          json={"job_id": f"nonexistent-{uuid.uuid4().hex}"}, timeout=15)
        assert r.status_code == 404


# ------------------------- 5. Upsell -------------------------
class TestUpsell:
    def test_upsell_shape(self, owner_headers, a_job_id):
        r = requests.post(f"{API}/ai/jobs/upsell", headers=owner_headers,
                          json={"job_id": a_job_id}, timeout=AI_TIMEOUT)
        assert r.status_code == 200, f"{r.status_code}: {r.text[:300]}"
        data = r.json()
        assert "title" in data
        assert "reason" in data
        assert "suggested_price" in data
        assert "confidence" in data
        # types
        assert isinstance(data["suggested_price"], (int, float))
        assert isinstance(data["confidence"], (int, float))


# ------------------------- 6. Maintenance scan & list & dismiss -------------------------
class TestMaintenance:
    def test_scan_small_limit(self, owner_headers):
        # Small limit to keep AI usage minimal
        r = requests.post(f"{API}/ai/maintenance/scan", headers=owner_headers,
                          json={"limit": 2}, timeout=AI_TIMEOUT + 60)
        assert r.status_code == 200, f"{r.status_code}: {r.text[:300]}"
        data = r.json()
        assert "scanned" in data and "suggested" in data
        assert isinstance(data["scanned"], int)
        assert isinstance(data["suggested"], int)

    def test_list_suggestions(self, owner_headers):
        r = requests.get(f"{API}/ai/maintenance/suggestions", headers=owner_headers, timeout=20)
        assert r.status_code == 200
        items = r.json()
        assert isinstance(items, list)
        for it in items:
            assert "_id" not in it  # mongo id excluded
            assert it.get("status") == "pending"

    def test_dismiss_suggestion(self, owner_headers):
        # Try dismissing any pending one. If none, create a fake doc via dismiss-of-nonexistent
        # which should still 200 (update_one with no match is harmless per current impl).
        r_list = requests.get(f"{API}/ai/maintenance/suggestions",
                              headers=owner_headers, timeout=20)
        items = r_list.json() if r_list.status_code == 200 else []
        sid = items[0]["id"] if items else f"fake-{uuid.uuid4().hex}"
        r = requests.post(f"{API}/ai/maintenance/{sid}/dismiss",
                          headers=owner_headers, timeout=15)
        assert r.status_code == 200
        assert r.json().get("ok") is True
        # If we dismissed a real one, it should no longer appear
        if items:
            r2 = requests.get(f"{API}/ai/maintenance/suggestions",
                              headers=owner_headers, timeout=20)
            ids2 = [x["id"] for x in r2.json()]
            assert sid not in ids2


# ------------------------- 7. Dispatcher assistant -------------------------
class TestDispatcher:
    def test_dispatcher_ask(self, owner_headers):
        r = requests.post(f"{API}/ai/dispatcher/ask", headers=owner_headers,
                          json={"question": "Who is the best tech to assign next?"},
                          timeout=AI_TIMEOUT)
        assert r.status_code == 200, f"{r.status_code}: {r.text[:300]}"
        data = r.json()
        assert "answer" in data and isinstance(data["answer"], str) and len(data["answer"]) > 0
        assert "session_id" in data and isinstance(data["session_id"], str)

    def test_dispatcher_empty_question(self, owner_headers):
        r = requests.post(f"{API}/ai/dispatcher/ask", headers=owner_headers,
                          json={"question": "   "}, timeout=10)
        assert r.status_code == 400


# ------------------------- 8. Public chatbot -------------------------
class TestPublicChatbot:
    def test_chatbot_no_auth(self, owner_company_id):
        # No auth header
        r = requests.post(f"{API}/public/ai/chatbot",
                          json={"company_id": owner_company_id,
                                "message": "Hi, do you service AC repairs?"},
                          timeout=AI_TIMEOUT)
        assert r.status_code == 200, f"{r.status_code}: {r.text[:300]}"
        data = r.json()
        assert "reply" in data and isinstance(data["reply"], str) and len(data["reply"]) > 0
        assert "session_id" in data

    def test_chatbot_invalid_company(self):
        r = requests.post(f"{API}/public/ai/chatbot",
                          json={"company_id": f"does-not-exist-{uuid.uuid4().hex}",
                                "message": "hello"},
                          timeout=20)
        assert r.status_code == 404


# ------------------------- 9. AI logs + RBAC + audit -------------------------
class TestAiLogs:
    def test_logs_for_owner(self, owner_headers):
        # By this point we've made several AI calls in this run; logs should exist
        r = requests.get(f"{API}/ai/logs?limit=50", headers=owner_headers, timeout=20)
        assert r.status_code == 200
        items = r.json()
        assert isinstance(items, list)
        assert len(items) > 0, "Expected at least one ai_logs entry from prior tests"
        first = items[0]
        for k in ("feature", "model", "success", "input_chars", "output_chars", "created_at"):
            assert k in first, f"missing field {k} in log entry"
        # at least one success entry
        assert any(x.get("success") is True for x in items)

    def test_logs_forbidden_for_dispatcher(self, dispatcher_headers):
        r = requests.get(f"{API}/ai/logs", headers=dispatcher_headers, timeout=15)
        assert r.status_code == 403


# ------------------------- 10. Multi-tenant isolation -------------------------
class TestTenantIsolation:
    def test_job_summary_other_tenant_returns_404(self, owner_headers):
        """A made-up job_id (no tenant match) must 404, never 200."""
        r = requests.post(f"{API}/ai/jobs/summarize", headers=owner_headers,
                          json={"job_id": "alien-tenant-job-id"}, timeout=15)
        assert r.status_code == 404

    def test_upsell_other_tenant_returns_404(self, owner_headers):
        r = requests.post(f"{API}/ai/jobs/upsell", headers=owner_headers,
                          json={"job_id": "alien-tenant-job-id"}, timeout=15)
        assert r.status_code == 404
