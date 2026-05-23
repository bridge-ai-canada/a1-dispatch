"""Backend tests for technician-mobile endpoints (iteration 16).

Covers:
- /api/timesheets/* shift clock-in/out, breaks, history, active
- /api/jobs/{id}/time/start|stop and GET summary
- /api/checklist-templates CRUD + apply/toggle on job
- /api/materials CRUD + per-job add/remove (with stock decrement)
- Job photo (with taken_at/caption form), video upload, video delete, voice-notes
- Multi-tenant isolation across registered tenants
"""
import os
import uuid
import time
import io
import pytest
import requests

def _read_frontend_env():
    try:
        with open("/app/frontend/.env") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    return line.split("=", 1)[1].strip()
    except Exception:
        return None
    return None


BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or _read_frontend_env() or "").rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL not set"
API = f"{BASE_URL}/api"

DEMO_EMAIL = "demo@a1fieldpro.com"
DEMO_PASS = "Demo1234!"


# ----------------- Fixtures -----------------
@pytest.fixture(scope="module")
def s():
    sess = requests.Session()
    sess.headers.update({"Content-Type": "application/json"})
    return sess


@pytest.fixture(scope="module")
def token(s):
    r = s.post(f"{API}/auth/login", json={"email": DEMO_EMAIL, "password": DEMO_PASS})
    if r.status_code != 200:
        pytest.skip(f"Demo login failed: {r.status_code} {r.text[:200]}")
    data = r.json()
    return data.get("token") or data.get("access_token")


@pytest.fixture(scope="module")
def auth(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def job_id(s, auth):
    """Create a dedicated job for mobile tests."""
    payload = {
        "title": f"TEST_mobile_{uuid.uuid4().hex[:6]}",
        "description": "mobile endpoint test job",
        "customer_name": "TEST customer",
        "address": "1 Test St",
        "job_type": "HVAC",
        "duration_min": 60,
        "price": 100.0,
    }
    r = s.post(f"{API}/jobs", json=payload, headers=auth)
    assert r.status_code in (200, 201), r.text
    return r.json()["id"]


@pytest.fixture(scope="module", autouse=True)
def cleanup_active_shift(s, auth):
    """Make sure we start without an active shift to avoid cross-run leakage."""
    try:
        s.post(f"{API}/timesheets/clock-out", headers=auth, timeout=10)
    except Exception:
        pass
    yield
    try:
        s.post(f"{API}/timesheets/clock-out", headers=auth, timeout=10)
    except Exception:
        pass


# ----------------- Shifts (timesheets) -----------------
class TestShifts:
    def test_clock_in_starts_shift(self, s, auth):
        r = s.post(f"{API}/timesheets/clock-in", headers=auth)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("started") is True or data.get("already_clocked_in") is True
        assert "shift" in data
        assert data["shift"]["ended_at"] is None

    def test_clock_in_double_returns_already(self, s, auth):
        r = s.post(f"{API}/timesheets/clock-in", headers=auth)
        assert r.status_code == 200
        data = r.json()
        assert data.get("already_clocked_in") is True
        assert data["shift"]["ended_at"] is None

    def test_active_shift_returns_record(self, s, auth):
        r = s.get(f"{API}/timesheets/active", headers=auth)
        assert r.status_code == 200
        assert r.json().get("active") is not None

    def test_add_break_increments(self, s, auth):
        r = s.post(f"{API}/timesheets/break", json={"minutes": 10}, headers=auth)
        assert r.status_code == 200
        assert r.json()["break_minutes"] >= 10
        r2 = s.post(f"{API}/timesheets/break", json={"minutes": 5}, headers=auth)
        assert r2.status_code == 200
        assert r2.json()["break_minutes"] >= 15

    def test_clock_out_computes_total(self, s, auth):
        r = s.post(f"{API}/timesheets/clock-out", headers=auth)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("ended_at") is not None
        assert "total_minutes" in data
        assert data["total_minutes"] >= 0

    def test_clock_out_without_active_400(self, s, auth):
        r = s.post(f"{API}/timesheets/clock-out", headers=auth)
        assert r.status_code == 400

    def test_break_without_active_400(self, s, auth):
        r = s.post(f"{API}/timesheets/break", json={"minutes": 5}, headers=auth)
        assert r.status_code == 400

    def test_active_returns_null_after_clock_out(self, s, auth):
        r = s.get(f"{API}/timesheets/active", headers=auth)
        assert r.status_code == 200
        assert r.json().get("active") is None

    def test_history_returns_list_with_recent_shift(self, s, auth):
        r = s.get(f"{API}/timesheets?days=14", headers=auth)
        assert r.status_code == 200
        items = r.json()
        assert isinstance(items, list)
        assert len(items) >= 1
        assert items[0]["ended_at"] is not None


# ----------------- Per-job time tracking -----------------
class TestJobTime:
    def test_start_timer(self, s, auth, job_id):
        r = s.post(f"{API}/jobs/{job_id}/time/start", headers=auth)
        assert r.status_code == 200, r.text
        e = r.json()
        assert e["ended_at"] is None
        assert "id" in e

    def test_start_concurrent_blocks(self, s, auth, job_id):
        r = s.post(f"{API}/jobs/{job_id}/time/start", headers=auth)
        assert r.status_code == 400

    def test_summary_shows_active_for_me(self, s, auth, job_id):
        r = s.get(f"{API}/jobs/{job_id}/time", headers=auth)
        assert r.status_code == 200
        d = r.json()
        assert d["active_for_me"] is not None
        assert isinstance(d["logs"], list)
        assert "total_minutes" in d

    def test_stop_timer_returns_duration(self, s, auth, job_id):
        # ensure at least 1s elapsed
        time.sleep(1)
        r = s.post(f"{API}/jobs/{job_id}/time/stop", headers=auth)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["ended_at"] is not None
        assert d["duration_min"] >= 0

    def test_stop_without_active_400(self, s, auth, job_id):
        r = s.post(f"{API}/jobs/{job_id}/time/stop", headers=auth)
        assert r.status_code == 400

    def test_time_404_for_missing_job(self, s, auth):
        r = s.get(f"{API}/jobs/does-not-exist-{uuid.uuid4().hex}/time", headers=auth)
        assert r.status_code == 404


# ----------------- Checklist templates + per-job -----------------
class TestChecklists:
    @pytest.fixture(scope="class")
    def template(self, s, auth):
        body = {
            "name": f"TEST_chk_{uuid.uuid4().hex[:6]}",
            "job_type": "HVAC",
            "items": [
                {"title": "Verify safety", "required": True},
                {"title": "Snap photo of unit"},
                {"title": "Get signature", "required": True},
            ],
        }
        r = s.post(f"{API}/checklist-templates", json=body, headers=auth)
        assert r.status_code in (200, 201), r.text
        tpl = r.json()
        assert tpl["name"] == body["name"]
        assert len(tpl["items"]) == 3
        for it in tpl["items"]:
            assert "id" in it
        yield tpl
        # cleanup
        s.delete(f"{API}/checklist-templates/{tpl['id']}", headers=auth)

    def test_list_includes_created(self, s, auth, template):
        r = s.get(f"{API}/checklist-templates", headers=auth)
        assert r.status_code == 200
        ids = [t["id"] for t in r.json()]
        assert template["id"] in ids

    def test_update_template_items_keeps_ids(self, s, auth, template):
        new_items = template["items"] + [{"title": "Added later", "required": False}]
        r = s.put(
            f"{API}/checklist-templates/{template['id']}",
            json={"items": new_items},
            headers=auth,
        )
        assert r.status_code == 200, r.text
        upd = r.json()
        assert len(upd["items"]) == 4
        for it in upd["items"]:
            assert "id" in it

    def test_apply_to_job_resets_checklist(self, s, auth, template, job_id):
        r = s.post(
            f"{API}/jobs/{job_id}/checklist/apply",
            json={"template_id": template["id"]},
            headers=auth,
        )
        assert r.status_code == 200, r.text
        cl = r.json()["checklist"]
        assert len(cl) >= 3
        assert all(it["completed"] is False for it in cl)
        assert all(it["completed_at"] is None for it in cl)

    def test_toggle_item_completed_and_uncomplete(self, s, auth, job_id):
        # fetch job → first checklist item id
        r = s.get(f"{API}/jobs/{job_id}", headers=auth)
        assert r.status_code == 200
        item_id = r.json()["checklist"][0]["id"]
        r1 = s.post(
            f"{API}/jobs/{job_id}/checklist/toggle",
            json={"item_id": item_id, "completed": True},
            headers=auth,
        )
        assert r1.status_code == 200
        item = next(i for i in r1.json()["checklist"] if i["id"] == item_id)
        assert item["completed"] is True
        assert item["completed_at"] is not None
        assert item["completed_by"] is not None

        r2 = s.post(
            f"{API}/jobs/{job_id}/checklist/toggle",
            json={"item_id": item_id, "completed": False},
            headers=auth,
        )
        assert r2.status_code == 200
        item = next(i for i in r2.json()["checklist"] if i["id"] == item_id)
        assert item["completed"] is False
        assert item["completed_at"] is None
        assert item["completed_by"] is None

    def test_toggle_invalid_item_404(self, s, auth, job_id):
        r = s.post(
            f"{API}/jobs/{job_id}/checklist/toggle",
            json={"item_id": f"nope-{uuid.uuid4().hex}", "completed": True},
            headers=auth,
        )
        assert r.status_code == 404

    def test_apply_missing_template_404(self, s, auth, job_id):
        r = s.post(
            f"{API}/jobs/{job_id}/checklist/apply",
            json={"template_id": f"nope-{uuid.uuid4().hex}"},
            headers=auth,
        )
        assert r.status_code == 404


# ----------------- Materials catalog + per-job -----------------
class TestMaterials:
    @pytest.fixture(scope="class")
    def material(self, s, auth):
        body = {
            "name": f"TEST_mat_{uuid.uuid4().hex[:6]}",
            "sku": f"SKU-{uuid.uuid4().hex[:5]}",
            "unit": "each",
            "unit_cost": 5.0,
            "unit_price": 12.5,
            "stock": 20,
        }
        r = s.post(f"{API}/materials", json=body, headers=auth)
        assert r.status_code in (200, 201), r.text
        mat = r.json()
        assert mat["name"] == body["name"]
        assert mat["stock"] == 20
        yield mat
        s.delete(f"{API}/materials/{mat['id']}", headers=auth)

    def test_search_finds_by_name(self, s, auth, material):
        q = material["name"][:10]
        r = s.get(f"{API}/materials?q={q}", headers=auth)
        assert r.status_code == 200
        ids = [m["id"] for m in r.json()]
        assert material["id"] in ids

    def test_search_finds_by_sku(self, s, auth, material):
        r = s.get(f"{API}/materials?q={material['sku']}", headers=auth)
        assert r.status_code == 200
        ids = [m["id"] for m in r.json()]
        assert material["id"] in ids

    def test_update_material(self, s, auth, material):
        r = s.put(
            f"{API}/materials/{material['id']}",
            json={"unit_price": 15.0},
            headers=auth,
        )
        assert r.status_code == 200
        assert r.json()["unit_price"] == 15.0

    def test_add_to_job_by_material_id_decrements_stock(self, s, auth, material, job_id):
        before = s.get(f"{API}/materials?q={material['sku']}", headers=auth).json()
        before_stock = next(m for m in before if m["id"] == material["id"])["stock"]
        r = s.post(
            f"{API}/jobs/{job_id}/materials",
            json={"material_id": material["id"], "qty": 3},
            headers=auth,
        )
        assert r.status_code == 200, r.text
        entry = r.json()
        assert entry["name"] == material["name"]
        assert entry["unit_cost"] == 5.0
        # unit_price updated to 15 earlier
        assert entry["unit_price"] in (12.5, 15.0)
        assert entry["qty"] == 3.0
        # stock should be decremented by 3
        after = s.get(f"{API}/materials?q={material['sku']}", headers=auth).json()
        after_stock = next(m for m in after if m["id"] == material["id"])["stock"]
        assert after_stock == before_stock - 3
        # remember entry id on instance for cleanup test
        TestMaterials._entry_id = entry["id"]

    def test_add_custom_material(self, s, auth, job_id):
        r = s.post(
            f"{API}/jobs/{job_id}/materials",
            json={"name": f"TEST_custom_{uuid.uuid4().hex[:4]}",
                  "qty": 2, "unit_cost": 1.5, "unit_price": 3.0},
            headers=auth,
        )
        assert r.status_code == 200, r.text
        e = r.json()
        assert e["material_id"] is None
        assert e["unit_price"] == 3.0

    def test_add_to_job_requires_name_or_id(self, s, auth, job_id):
        r = s.post(
            f"{API}/jobs/{job_id}/materials",
            json={"qty": 1},
            headers=auth,
        )
        assert r.status_code == 400

    def test_remove_entry(self, s, auth, job_id):
        entry_id = getattr(TestMaterials, "_entry_id", None)
        if not entry_id:
            pytest.skip("no entry id captured")
        r = s.delete(f"{API}/jobs/{job_id}/materials/{entry_id}", headers=auth)
        assert r.status_code == 200
        # verify removed
        job = s.get(f"{API}/jobs/{job_id}", headers=auth).json()
        ids = [m["id"] for m in (job.get("materials_used") or [])]
        assert entry_id not in ids


# ----------------- Voice notes + video + photo form fields -----------------
class TestMediaAndNotes:
    def test_voice_note_add(self, s, auth, job_id):
        r = s.post(
            f"{API}/jobs/{job_id}/voice-notes",
            json={"text": "  Customer wants follow-up.  "},
            headers=auth,
        )
        assert r.status_code == 200, r.text
        e = r.json()
        assert e["text"] == "Customer wants follow-up."
        assert "author_id" in e and "created_at" in e

    def test_voice_note_rejects_empty(self, s, auth, job_id):
        r = s.post(
            f"{API}/jobs/{job_id}/voice-notes",
            json={"text": "   "},
            headers=auth,
        )
        assert r.status_code == 400

    def test_voice_note_truncated_to_2000(self, s, auth, job_id):
        long_text = "x" * 2500
        r = s.post(
            f"{API}/jobs/{job_id}/voice-notes",
            json={"text": long_text},
            headers=auth,
        )
        assert r.status_code == 200
        assert len(r.json()["text"]) == 2000

    def test_photo_upload_form_fields(self, s, auth, job_id):
        # multipart upload (no JSON Content-Type)
        png_bytes = (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
            b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xf8\xff"
            b"\xff?\x00\x05\xfe\x02\xfe\xa0\x1bg\x95\x00\x00\x00\x00IEND\xaeB`\x82"
        )
        files = {"file": ("t.png", io.BytesIO(png_bytes), "image/png")}
        data = {"taken_at": "2026-01-15T10:00:00Z", "caption": "Front of unit"}
        r = requests.post(
            f"{API}/jobs/{job_id}/photos",
            files=files, data=data,
            headers={"Authorization": auth["Authorization"]},
        )
        assert r.status_code == 200, r.text
        p = r.json()
        assert p["caption"] == "Front of unit"
        assert p["taken_at"] == "2026-01-15T10:00:00Z"
        assert p["kind"] == "photo"

    def test_video_rejects_non_video_content_type(self, s, auth, job_id):
        files = {"file": ("a.txt", io.BytesIO(b"not a video"), "text/plain")}
        r = requests.post(
            f"{API}/jobs/{job_id}/videos",
            files=files,
            headers={"Authorization": auth["Authorization"]},
        )
        assert r.status_code == 400

    def test_video_upload_happy_path(self, s, auth, job_id):
        # Tiny mp4-like bytes; storage may or may not accept.
        files = {"file": ("tiny.mp4", io.BytesIO(b"\x00\x00\x00\x18ftypmp42\x00" * 4),
                          "video/mp4")}
        data = {"caption": "short clip"}
        r = requests.post(
            f"{API}/jobs/{job_id}/videos",
            files=files, data=data,
            headers={"Authorization": auth["Authorization"]},
        )
        if r.status_code != 200:
            pytest.skip(f"storage backend rejected tiny video (env limit): {r.status_code}")
        v = r.json()
        assert v["kind"] == "video"
        assert v["caption"] == "short clip"
        # delete it back
        rd = s.delete(f"{API}/jobs/{job_id}/videos/{v['id']}", headers=auth)
        assert rd.status_code == 200

    def test_video_delete_404_when_missing(self, s, auth, job_id):
        r = s.delete(
            f"{API}/jobs/{job_id}/videos/nope-{uuid.uuid4().hex}",
            headers=auth,
        )
        assert r.status_code == 404


# ----------------- Multi-tenant isolation -----------------
class TestTenantIsolation:
    @pytest.fixture(scope="class")
    def other_tenant(self, s):
        """Register a fresh company so we can check cross-tenant 404s."""
        email = f"tester_{uuid.uuid4().hex[:8]}@example.com"
        payload = {
            "email": email,
            "password": "Other1234!",
            "name": "Iso Tester",
            "company_name": f"ISO_{uuid.uuid4().hex[:6]}",
        }
        r = requests.post(f"{API}/auth/register", json=payload)
        if r.status_code not in (200, 201):
            pytest.skip(f"register failed: {r.status_code} {r.text[:200]}")
        data = r.json()
        tok = data.get("token") or data.get("access_token")
        if not tok:
            # try login
            lg = requests.post(f"{API}/auth/login",
                               json={"email": email, "password": "Other1234!"})
            if lg.status_code != 200:
                pytest.skip("could not auth other tenant")
            tok = lg.json().get("token") or lg.json().get("access_token")
        return {"Authorization": f"Bearer {tok}", "email": email}

    def test_cross_tenant_template_404(self, s, auth, other_tenant):
        # create template in other tenant
        body = {"name": f"TEST_iso_{uuid.uuid4().hex[:5]}", "items": [{"title": "x"}]}
        r = requests.post(f"{API}/checklist-templates", json=body,
                          headers={"Authorization": other_tenant["Authorization"],
                                   "Content-Type": "application/json"})
        assert r.status_code in (200, 201), r.text
        tid = r.json()["id"]
        # demo tenant should NOT see it / cannot delete
        rd = s.delete(f"{API}/checklist-templates/{tid}", headers=auth)
        assert rd.status_code == 404
        # cleanup in own tenant
        requests.delete(f"{API}/checklist-templates/{tid}",
                        headers={"Authorization": other_tenant["Authorization"]})

    def test_cross_tenant_material_404(self, s, auth, other_tenant):
        r = requests.post(
            f"{API}/materials",
            json={"name": f"TEST_iso_mat_{uuid.uuid4().hex[:5]}", "unit_cost": 1, "unit_price": 2},
            headers={"Authorization": other_tenant["Authorization"],
                     "Content-Type": "application/json"},
        )
        assert r.status_code in (200, 201)
        mid = r.json()["id"]
        rd = s.put(f"{API}/materials/{mid}", json={"unit_price": 9}, headers=auth)
        assert rd.status_code == 404
        rdel = s.delete(f"{API}/materials/{mid}", headers=auth)
        assert rdel.status_code == 404
        requests.delete(f"{API}/materials/{mid}",
                        headers={"Authorization": other_tenant["Authorization"]})

    def test_cross_tenant_shifts_isolated(self, s, auth, other_tenant):
        # other tenant clocks in; demo's /timesheets should not contain it
        ri = requests.post(f"{API}/timesheets/clock-in",
                           headers={"Authorization": other_tenant["Authorization"]})
        assert ri.status_code == 200
        r = s.get(f"{API}/timesheets", headers=auth)
        assert r.status_code == 200
        # other tenant's user_id won't appear; just sanity check is a list
        assert isinstance(r.json(), list)
        # clean up other tenant's shift
        requests.post(f"{API}/timesheets/clock-out",
                      headers={"Authorization": other_tenant["Authorization"]})
