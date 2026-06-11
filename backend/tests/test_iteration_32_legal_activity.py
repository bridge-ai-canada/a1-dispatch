"""Iteration 32 tests:
- /api/legal/{slug} HTML + .txt routes (public, no auth, cacheable)
- Per-job checklist mutations emit log_activity rows
- Regression: per-job checklist CRUD + analytics PDF export still pass (delegated to iter31 suite when run together)
"""
import os
import uuid
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"

OWNER = {"email": "demo@a1fieldpro.com", "password": "Demo1234!"}


@pytest.fixture(scope="session")
def owner_session():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json=OWNER, timeout=20)
    assert r.status_code == 200, f"owner login failed: {r.status_code} {r.text[:200]}"
    return s


@pytest.fixture(scope="session")
def demo_job_id(owner_session):
    r = owner_session.get(f"{API}/jobs", timeout=20)
    assert r.status_code == 200
    data = r.json()
    jobs = data if isinstance(data, list) else data.get("jobs") or data.get("items") or []
    assert jobs, "no demo jobs"
    return jobs[0]["id"]


# -------------------- Legal endpoints (public, no auth) --------------------
class TestLegalEndpoints:
    def test_privacy_html(self):
        r = requests.get(f"{API}/legal/privacy", timeout=15)
        assert r.status_code == 200, r.text[:200]
        ct = r.headers.get("content-type", "")
        assert "text/html" in ct, f"wrong content-type: {ct}"
        # Backend sets Cache-Control: public, max-age=3600 (verified via localhost),
        # but the preview ingress (cloudflare/k8s) overrides it with no-store on the
        # public URL. Verify backend response directly.
        try:
            local = requests.get("http://localhost:8001/api/legal/privacy", timeout=10)
            cache = local.headers.get("cache-control", "")
            assert "max-age=3600" in cache, f"backend cache-control wrong: {cache}"
        except requests.exceptions.ConnectionError:
            pass  # not co-located with backend; skip
        body = r.text
        assert "<title>Privacy Policy \u00b7 A1 Field Pro</title>" in body, \
            f"title not found. head: {body[:500]}"
        # html escaping: ensure raw '&' from markdown was escaped to &amp; somewhere
        # (privacy doc contains 2 '&' chars)
        assert "&amp;" in body, "Expected HTML-escaped ampersand in rendered body"

    def test_terms_html(self):
        r = requests.get(f"{API}/legal/terms", timeout=15)
        assert r.status_code == 200, r.text[:200]
        assert "text/html" in r.headers.get("content-type", "")
        assert "Terms of Service" in r.text

    def test_privacy_txt(self):
        r = requests.get(f"{API}/legal/privacy.txt", timeout=15)
        assert r.status_code == 200
        ct = r.headers.get("content-type", "")
        assert "text/plain" in ct and "charset=utf-8" in ct, f"wrong ct: {ct}"
        assert r.text.startswith("# Privacy Policy"), f"unexpected start: {r.text[:120]}"

    def test_terms_txt(self):
        r = requests.get(f"{API}/legal/terms.txt", timeout=15)
        assert r.status_code == 200
        assert "text/plain" in r.headers.get("content-type", "")
        assert r.text.startswith("#"), r.text[:120]

    def test_nonexistent_slug_404(self):
        r = requests.get(f"{API}/legal/nonexistent", timeout=15)
        assert r.status_code == 404
        r2 = requests.get(f"{API}/legal/nonexistent.txt", timeout=15)
        assert r2.status_code == 404

    def test_legal_no_auth_required(self):
        # bare session w/o any cookies
        s = requests.Session()
        r = s.get(f"{API}/legal/privacy", timeout=15)
        assert r.status_code == 200


# -------------------- Activity log on per-job checklist mutations --------------------
@pytest.fixture
def fresh_template(owner_session):
    name = f"TEST_act_{uuid.uuid4().hex[:6]}"
    payload = {
        "name": name, "job_type": "hvac",
        "items": [
            {"title": "Check filter", "required": True},
            {"title": "Test thermostat", "required": False},
        ],
    }
    r = owner_session.post(f"{API}/checklist-templates", json=payload, timeout=15)
    assert r.status_code == 200, r.text[:300]
    tpl = r.json()
    yield tpl
    try:
        owner_session.delete(f"{API}/checklist-templates/{tpl['id']}", timeout=10)
    except Exception:
        pass


def _find_activity(session, action: str, target_id: str, limit=50):
    """Fetch recent activity for current company and find first matching row."""
    r = session.get(f"{API}/activity", params={"limit": limit, "action": action}, timeout=15)
    if r.status_code != 200:
        # try without filter
        r = session.get(f"{API}/activity", params={"limit": limit}, timeout=15)
    assert r.status_code == 200, f"activity fetch failed: {r.status_code} {r.text[:200]}"
    rows = r.json() if isinstance(r.json(), list) else r.json().get("items") or r.json().get("activity") or []
    matches = [row for row in rows if row.get("action") == action and row.get("target_id") == target_id]
    return matches


class TestChecklistActivityLog:
    def test_add_item_logged(self, owner_session, demo_job_id, fresh_template):
        # apply template first
        owner_session.post(f"{API}/jobs/{demo_job_id}/checklist/apply",
                           json={"template_id": fresh_template["id"]})
        # add an item
        r = owner_session.post(f"{API}/jobs/{demo_job_id}/checklist/items",
                               json={"title": "TEST_log_added", "required": True})
        assert r.status_code == 200
        added = next(i for i in r.json()["checklist"] if i["title"] == "TEST_log_added")

        matches = _find_activity(owner_session, "job.checklist.item.added", demo_job_id)
        assert matches, "no activity row for job.checklist.item.added"
        # most recent first by default — check the latest matches has correct meta
        latest = matches[0]
        assert latest["target_type"] == "job"
        assert latest["target_id"] == demo_job_id
        meta = latest.get("meta") or {}
        # title should be present in some recent matching log
        assert any(m.get("meta", {}).get("title") == "TEST_log_added" for m in matches), \
            f"expected meta.title in some activity row. got: {[m.get('meta') for m in matches[:3]]}"

    def test_update_item_logged(self, owner_session, demo_job_id, fresh_template):
        owner_session.post(f"{API}/jobs/{demo_job_id}/checklist/apply",
                           json={"template_id": fresh_template["id"]})
        r = owner_session.post(f"{API}/jobs/{demo_job_id}/checklist/items",
                               json={"title": "TEST_to_update", "required": False})
        item_id = next(i for i in r.json()["checklist"] if i["title"] == "TEST_to_update")["id"]

        r2 = owner_session.put(f"{API}/jobs/{demo_job_id}/checklist/items/{item_id}",
                               json={"title": "TEST_was_updated"})
        assert r2.status_code == 200

        matches = _find_activity(owner_session, "job.checklist.item.updated", demo_job_id)
        assert matches, "no activity for job.checklist.item.updated"
        assert any(m.get("meta", {}).get("item_id") == item_id for m in matches), \
            f"item_id not found in activity meta. samples: {[m.get('meta') for m in matches[:3]]}"

    def test_delete_item_logged(self, owner_session, demo_job_id, fresh_template):
        owner_session.post(f"{API}/jobs/{demo_job_id}/checklist/apply",
                           json={"template_id": fresh_template["id"]})
        r = owner_session.post(f"{API}/jobs/{demo_job_id}/checklist/items",
                               json={"title": "TEST_to_remove", "required": False})
        item_id = next(i for i in r.json()["checklist"] if i["title"] == "TEST_to_remove")["id"]

        r2 = owner_session.delete(f"{API}/jobs/{demo_job_id}/checklist/items/{item_id}")
        assert r2.status_code == 200

        matches = _find_activity(owner_session, "job.checklist.item.removed", demo_job_id)
        assert matches, "no activity for job.checklist.item.removed"
        assert any(m.get("meta", {}).get("item_id") == item_id for m in matches)

    def test_clear_checklist_logged(self, owner_session, demo_job_id, fresh_template):
        owner_session.post(f"{API}/jobs/{demo_job_id}/checklist/apply",
                           json={"template_id": fresh_template["id"]})
        # ensure 2+ items present from template
        r0 = owner_session.get(f"{API}/jobs/{demo_job_id}/checklist")
        count_before = len(r0.json()["checklist"])
        assert count_before >= 1

        r = owner_session.delete(f"{API}/jobs/{demo_job_id}/checklist")
        assert r.status_code == 200

        matches = _find_activity(owner_session, "job.checklist.cleared", demo_job_id)
        assert matches, "no activity for job.checklist.cleared"
        # meta.removed_count should equal count_before for the most recent match
        latest = matches[0]
        assert latest.get("meta", {}).get("removed_count") == count_before, \
            f"removed_count mismatch: meta={latest.get('meta')} expected={count_before}"


# -------------------- Regression: PDF export still works --------------------
PDF_MAGIC = b"%PDF"

class TestAnalyticsPdfRegression:
    @pytest.mark.parametrize("report", [
        "overview", "revenue", "technicians", "marketing", "financing", "leaderboard",
    ])
    def test_pdf_export(self, owner_session, report):
        r = owner_session.get(f"{API}/analytics/export.pdf",
                              params={"report": report}, timeout=30)
        assert r.status_code == 200, f"{report}: {r.status_code} {r.text[:200]}"
        assert "application/pdf" in r.headers.get("content-type", "")
        assert r.content[:4] == PDF_MAGIC
        assert len(r.content) > 800
