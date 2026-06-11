"""Iteration 31 tests:
- New per-job checklist CRUD endpoints (GET/POST/PUT/DELETE items + clear)
- Per-job mutations must NOT touch master checklist_template doc
- Tenant isolation
- Analytics PDF export for all 6 report types (overview/revenue/technicians/marketing/financing/leaderboard)
"""
import os
import time
import uuid
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"

OWNER = {"email": "demo@a1fieldpro.com", "password": "Demo1234!"}


# --------------- Fixtures ---------------
@pytest.fixture(scope="session")
def owner_session():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json=OWNER, timeout=20)
    assert r.status_code == 200, f"owner login failed: {r.status_code} {r.text[:200]}"
    return s


@pytest.fixture(scope="session")
def demo_job_id(owner_session):
    r = owner_session.get(f"{API}/jobs", timeout=20)
    assert r.status_code == 200, r.text[:200]
    data = r.json()
    jobs = data if isinstance(data, list) else data.get("jobs") or data.get("items") or []
    assert jobs, "no demo jobs"
    return jobs[0]["id"]


@pytest.fixture
def fresh_template(owner_session):
    name = f"TEST_tpl_{uuid.uuid4().hex[:6]}"
    payload = {
        "name": name,
        "job_type": "hvac",
        "items": [
            {"title": "Check filter", "required": True},
            {"title": "Test thermostat", "required": False},
        ],
    }
    r = owner_session.post(f"{API}/checklist-templates", json=payload, timeout=15)
    assert r.status_code == 200, r.text[:300]
    tpl = r.json()
    yield tpl
    # cleanup
    try:
        owner_session.delete(f"{API}/checklist-templates/{tpl['id']}", timeout=10)
    except Exception:
        pass


# --------------- Template CRUD regression ---------------
class TestTemplatesRegression:
    def test_create_list_update_delete(self, owner_session):
        name = f"TEST_reg_{uuid.uuid4().hex[:6]}"
        r = owner_session.post(f"{API}/checklist-templates", json={
            "name": name, "job_type": "plumbing",
            "items": [{"title": "Shutoff valve", "required": True}],
        })
        assert r.status_code == 200
        tpl = r.json()
        assert tpl["name"] == name
        assert tpl["job_type"] == "plumbing"
        assert len(tpl["items"]) == 1
        assert "_id" not in tpl
        tid = tpl["id"]

        r2 = owner_session.get(f"{API}/checklist-templates")
        assert r2.status_code == 200
        assert any(t["id"] == tid for t in r2.json())

        r3 = owner_session.put(f"{API}/checklist-templates/{tid}", json={"name": name + "_upd"})
        assert r3.status_code == 200
        assert r3.json()["name"] == name + "_upd"

        r4 = owner_session.delete(f"{API}/checklist-templates/{tid}")
        assert r4.status_code == 200
        assert r4.json().get("ok") is True

        r5 = owner_session.delete(f"{API}/checklist-templates/{tid}")
        assert r5.status_code == 404


# --------------- Per-job checklist ---------------
class TestPerJobChecklist:
    def test_apply_and_toggle(self, owner_session, demo_job_id, fresh_template):
        r = owner_session.post(
            f"{API}/jobs/{demo_job_id}/checklist/apply",
            json={"template_id": fresh_template["id"]},
        )
        assert r.status_code == 200, r.text[:300]
        items = r.json()["checklist"]
        assert len(items) == 2
        first_id = items[0]["id"]

        r2 = owner_session.post(
            f"{API}/jobs/{demo_job_id}/checklist/toggle",
            json={"item_id": first_id, "completed": True},
        )
        assert r2.status_code == 200
        toggled = next(i for i in r2.json()["checklist"] if i["id"] == first_id)
        assert toggled["completed"] is True
        assert toggled["completed_at"] is not None

    def test_get_returns_items(self, owner_session, demo_job_id, fresh_template):
        owner_session.post(f"{API}/jobs/{demo_job_id}/checklist/apply",
                           json={"template_id": fresh_template["id"]})
        r = owner_session.get(f"{API}/jobs/{demo_job_id}/checklist")
        assert r.status_code == 200
        assert "checklist" in r.json()
        assert len(r.json()["checklist"]) == 2

    def test_add_item_empty_title_400(self, owner_session, demo_job_id):
        r = owner_session.post(f"{API}/jobs/{demo_job_id}/checklist/items",
                               json={"title": "   ", "required": False})
        assert r.status_code == 400, f"expected 400 for empty title, got {r.status_code}"

    def test_add_update_delete_per_job_item(self, owner_session, demo_job_id, fresh_template):
        # reset with template
        owner_session.post(f"{API}/jobs/{demo_job_id}/checklist/apply",
                           json={"template_id": fresh_template["id"]})

        # add
        r = owner_session.post(f"{API}/jobs/{demo_job_id}/checklist/items",
                               json={"title": "TEST_extra item", "required": True})
        assert r.status_code == 200, r.text[:300]
        items = r.json()["checklist"]
        new_item = next(i for i in items if i["title"] == "TEST_extra item")
        assert new_item["required"] is True
        assert new_item["completed"] is False
        item_id = new_item["id"]

        # update
        r2 = owner_session.put(
            f"{API}/jobs/{demo_job_id}/checklist/items/{item_id}",
            json={"title": "TEST_renamed", "required": False},
        )
        assert r2.status_code == 200
        updated = next(i for i in r2.json()["checklist"] if i["id"] == item_id)
        assert updated["title"] == "TEST_renamed"
        assert updated["required"] is False

        # update missing id -> 404
        r3 = owner_session.put(
            f"{API}/jobs/{demo_job_id}/checklist/items/{uuid.uuid4()}",
            json={"title": "ghost"},
        )
        assert r3.status_code == 404

        # delete
        r4 = owner_session.delete(f"{API}/jobs/{demo_job_id}/checklist/items/{item_id}")
        assert r4.status_code == 200
        assert all(i["id"] != item_id for i in r4.json()["checklist"])

        # delete missing -> 404
        r5 = owner_session.delete(f"{API}/jobs/{demo_job_id}/checklist/items/{uuid.uuid4()}")
        assert r5.status_code == 404

    def test_template_not_mutated_by_per_job_edits(self, owner_session, demo_job_id, fresh_template):
        tid = fresh_template["id"]
        # snapshot template items before
        r0 = owner_session.get(f"{API}/checklist-templates")
        before = next(t for t in r0.json() if t["id"] == tid)
        before_items = before["items"]

        # apply
        owner_session.post(f"{API}/jobs/{demo_job_id}/checklist/apply",
                           json={"template_id": tid})
        # mutate per-job: add + delete + clear
        owner_session.post(f"{API}/jobs/{demo_job_id}/checklist/items",
                           json={"title": "TEST_mutate", "required": True})
        owner_session.delete(f"{API}/jobs/{demo_job_id}/checklist")

        # template should be unchanged
        r1 = owner_session.get(f"{API}/checklist-templates")
        after = next(t for t in r1.json() if t["id"] == tid)
        assert after["items"] == before_items, "Master template was mutated by per-job edits!"

    def test_clear_checklist(self, owner_session, demo_job_id, fresh_template):
        owner_session.post(f"{API}/jobs/{demo_job_id}/checklist/apply",
                           json={"template_id": fresh_template["id"]})
        r = owner_session.delete(f"{API}/jobs/{demo_job_id}/checklist")
        assert r.status_code == 200
        assert r.json()["checklist"] == []


# --------------- Tenant isolation ---------------
class TestTenantIsolation:
    def test_other_tenant_cannot_access_job_checklist(self, owner_session, demo_job_id):
        # register a fresh company/owner
        email = f"iso_{uuid.uuid4().hex[:6]}@example.com"
        s = requests.Session()
        rr = s.post(f"{API}/auth/register", json={
            "email": email, "password": "Isolate1234!",
            "name": "Iso Owner", "company_name": f"IsoCo_{uuid.uuid4().hex[:4]}",
        })
        if rr.status_code not in (200, 201):
            pytest.skip(f"could not register isolation user: {rr.status_code} {rr.text[:200]}")
        # login (cookie session)
        lr = s.post(f"{API}/auth/login", json={"email": email, "password": "Isolate1234!"})
        assert lr.status_code == 200

        # GET other-tenant job checklist → 404
        r = s.get(f"{API}/jobs/{demo_job_id}/checklist")
        assert r.status_code == 404, f"expected 404, got {r.status_code}"

        # add item on other-tenant job → 404
        r2 = s.post(f"{API}/jobs/{demo_job_id}/checklist/items",
                    json={"title": "evil", "required": False})
        assert r2.status_code == 404

        # delete checklist on other tenant → 404
        r3 = s.delete(f"{API}/jobs/{demo_job_id}/checklist")
        assert r3.status_code == 404


# --------------- Analytics PDF export ---------------
PDF_MAGIC = b"%PDF"


class TestAnalyticsPdfExport:
    @pytest.mark.parametrize("report", [
        "overview", "revenue", "technicians", "marketing", "financing", "leaderboard",
    ])
    def test_pdf_export(self, owner_session, report):
        r = owner_session.get(f"{API}/analytics/export.pdf", params={"report": report}, timeout=30)
        assert r.status_code == 200, f"{report}: {r.status_code} {r.text[:200]}"
        ct = r.headers.get("content-type", "")
        assert "application/pdf" in ct, f"{report}: wrong content-type {ct}"
        assert r.content[:4] == PDF_MAGIC, f"{report}: not a real PDF"
        assert len(r.content) > 800, f"{report}: PDF suspiciously small ({len(r.content)})"
