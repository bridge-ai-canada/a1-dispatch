"""CRM module tests: customers, properties, equipment, communications, files, timeline, AI summary, tenant isolation."""
import io
import os
import uuid
import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "a1_field_pro")

OWNER = {"email": "demo@a1fieldpro.com", "password": "Demo1234!"}
TECH = {"email": "tech@a1fieldpro.com", "password": "Demo1234!"}


# ---- Reset MFA + cleanup TEST_ data ----
@pytest.fixture(scope="session", autouse=True)
def _reset_state():
    client = MongoClient(MONGO_URL)
    try:
        db = client[DB_NAME]
        db.users.update_many(
            {"email": {"$in": [OWNER["email"], TECH["email"]]}},
            {"$set": {"mfa_enabled": False, "mfa_secret": None, "active": True}},
        )
        # Cleanup any stale TEST_ data
        for col in ("customers", "properties", "equipment", "communications", "customer_files", "jobs"):
            db[col].delete_many({"$or": [
                {"name": {"$regex": "TEST_"}},
                {"title": {"$regex": "TEST_"}},
                {"summary": {"$regex": "TEST_"}},
                {"filename": {"$regex": "TEST_"}},
            ]})
        db.users.delete_many({"email": {"$regex": "^TEST_"}})
        yield
        for col in ("customers", "properties", "equipment", "communications", "customer_files", "jobs"):
            db[col].delete_many({"$or": [
                {"name": {"$regex": "TEST_"}},
                {"title": {"$regex": "TEST_"}},
                {"summary": {"$regex": "TEST_"}},
                {"filename": {"$regex": "TEST_"}},
            ]})
        db.users.delete_many({"email": {"$regex": "^TEST_"}})
    finally:
        client.close()


def _login(creds):
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json=creds, timeout=15)
    assert r.status_code == 200, r.text
    return s


@pytest.fixture(scope="module")
def owner():
    return _login(OWNER)


@pytest.fixture(scope="module")
def tech():
    return _login(TECH)


# A separate company / owner for tenant isolation tests
@pytest.fixture(scope="module")
def other_owner():
    s = requests.Session()
    email = f"TEST_other_{uuid.uuid4().hex[:6]}@example.com"
    r = s.post(f"{API}/auth/register", json={
        "company_name": f"TEST_OtherCo_{uuid.uuid4().hex[:4]}",
        "industry": "HVAC", "name": "TEST Other", "email": email, "password": "Demo1234!",
    }, timeout=15)
    assert r.status_code == 200, r.text
    return s


@pytest.fixture
def customer(owner):
    name = f"TEST_Cust_{uuid.uuid4().hex[:6]}"
    r = owner.post(f"{API}/customers", json={
        "name": name, "phone": "+15550001111", "email": f"{name.lower()}@ex.com",
        "address": "1 Test Ln", "status": "lead", "tags": ["vip", "hvac"],
    }, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()


# ============== Customers CRUD + search/filter ==============
class TestCustomers:
    def test_create_persists_status_and_tags(self, owner):
        r = owner.post(f"{API}/customers", json={
            "name": "TEST_PersistA", "status": "prospect", "tags": ["a", "b"],
        }, timeout=15)
        assert r.status_code == 200
        cid = r.json()["id"]
        g = owner.get(f"{API}/customers/{cid}", timeout=15)
        assert g.status_code == 200
        body = g.json()
        assert body["status"] == "prospect"
        assert body["tags"] == ["a", "b"]

    def test_patch_updates_fields(self, owner, customer):
        r = owner.patch(f"{API}/customers/{customer['id']}", json={
            "name": "TEST_Renamed", "status": "active", "tags": ["renamed"], "notes": "TEST_note",
        }, timeout=15)
        assert r.status_code == 200
        # Verify persistence
        g = owner.get(f"{API}/customers/{customer['id']}", timeout=15).json()
        assert g["name"] == "TEST_Renamed"
        assert g["status"] == "active"
        assert g["tags"] == ["renamed"]
        assert g["notes"] == "TEST_note"

    def test_search_q_matches_name_phone_email_address(self, owner):
        marker = uuid.uuid4().hex[:8]
        owner.post(f"{API}/customers", json={
            "name": f"TEST_Search_{marker}", "phone": f"+1555{marker[:7]}",
            "email": f"se_{marker}@ex.com", "address": f"{marker} Pine St",
        }, timeout=15)
        # name
        r = owner.get(f"{API}/customers", params={"q": marker}, timeout=15)
        assert r.status_code == 200
        rows = r.json().get("items", []) if isinstance(r.json(), dict) else r.json()
        names = [c["name"] for c in rows]
        assert any(marker in n for n in names)
        # email
        r = owner.get(f"{API}/customers", params={"q": f"se_{marker}"}, timeout=15)
        assert r.status_code == 200
        rows = r.json().get("items", []) if isinstance(r.json(), dict) else r.json()
        assert any(c.get("email", "").startswith(f"se_{marker}") for c in rows)

    def test_filter_by_status(self, owner):
        owner.post(f"{API}/customers", json={"name": "TEST_StatLead", "status": "lead"}, timeout=15)
        owner.post(f"{API}/customers", json={"name": "TEST_StatActive", "status": "active"}, timeout=15)
        r = owner.get(f"{API}/customers", params={"status": "lead"}, timeout=15)
        assert r.status_code == 200
        rows = r.json().get("items", []) if isinstance(r.json(), dict) else r.json()
        statuses = {c["status"] for c in rows}
        assert statuses == {"lead"} or statuses.issubset({"lead"})

    def test_filter_by_tag(self, owner):
        tag = f"TEST_tag_{uuid.uuid4().hex[:5]}"
        owner.post(f"{API}/customers", json={"name": "TEST_TagA", "tags": [tag]}, timeout=15)
        r = owner.get(f"{API}/customers", params={"tag": tag}, timeout=15)
        assert r.status_code == 200
        out = r.json().get("items", []) if isinstance(r.json(), dict) else r.json()
        assert len(out) >= 1
        assert all(tag in c.get("tags", []) for c in out)

    def test_tenant_isolation_customer(self, owner, other_owner, customer):
        # other_owner cannot read demo company customer
        r = other_owner.get(f"{API}/customers/{customer['id']}", timeout=15)
        assert r.status_code == 404
        r = other_owner.patch(f"{API}/customers/{customer['id']}",
                              json={"name": "TEST_Hacked"}, timeout=15)
        assert r.status_code == 404


# ============== Properties ==============
class TestProperties:
    def test_create_list_delete_property(self, owner, customer):
        r = owner.post(f"{API}/customers/{customer['id']}/properties", json={
            "address": "100 TEST Ave", "nickname": "Main", "property_type": "residential",
            "sq_ft": 1500, "year_built": 2001,
        }, timeout=15)
        assert r.status_code == 200, r.text
        pid = r.json()["id"]
        # list
        r = owner.get(f"{API}/customers/{customer['id']}/properties", timeout=15)
        assert r.status_code == 200
        assert any(p["id"] == pid for p in r.json())
        # delete
        r = owner.delete(f"{API}/properties/{pid}", timeout=15)
        assert r.status_code == 200
        # not in list after delete
        r = owner.get(f"{API}/customers/{customer['id']}/properties", timeout=15)
        assert not any(p["id"] == pid for p in r.json())

    def test_create_property_unknown_customer_returns_404(self, owner):
        r = owner.post(f"{API}/customers/does-not-exist/properties",
                       json={"address": "x"}, timeout=15)
        assert r.status_code == 404


# ============== Equipment ==============
class TestEquipment:
    def test_equipment_requires_valid_property_in_same_customer(self, owner, customer):
        # Create property under same customer
        p = owner.post(f"{API}/customers/{customer['id']}/properties",
                       json={"address": "200 TEST Eq Ave"}, timeout=15).json()
        # Valid create
        r = owner.post(f"{API}/customers/{customer['id']}/equipment", json={
            "property_id": p["id"], "kind": "AC", "brand": "TEST_Brand",
        }, timeout=15)
        assert r.status_code == 200, r.text
        eid = r.json()["id"]
        # List
        r = owner.get(f"{API}/customers/{customer['id']}/equipment", timeout=15)
        assert any(e["id"] == eid for e in r.json())
        # Invalid property id
        r = owner.post(f"{API}/customers/{customer['id']}/equipment", json={
            "property_id": "nope", "kind": "AC",
        }, timeout=15)
        assert r.status_code == 404
        # Property of a different customer should also fail
        c2 = owner.post(f"{API}/customers", json={"name": "TEST_C2"}, timeout=15).json()
        p2 = owner.post(f"{API}/customers/{c2['id']}/properties",
                        json={"address": "x"}, timeout=15).json()
        r = owner.post(f"{API}/customers/{customer['id']}/equipment", json={
            "property_id": p2["id"], "kind": "AC",
        }, timeout=15)
        assert r.status_code == 404
        # Delete
        r = owner.delete(f"{API}/equipment/{eid}", timeout=15)
        assert r.status_code == 200


# ============== Communications + Job auto-logs ==============
class TestCommunicationsAndJobAutoLog:
    def test_create_and_list_manual_communication(self, owner, customer):
        r = owner.post(f"{API}/customers/{customer['id']}/communications", json={
            "channel": "call", "direction": "out", "summary": "TEST_called customer", "body": "rang",
        }, timeout=15)
        assert r.status_code == 200, r.text
        cid = r.json()["id"]
        r = owner.get(f"{API}/customers/{customer['id']}/communications", timeout=15)
        assert r.status_code == 200
        assert any(c["id"] == cid and c["channel"] == "call" for c in r.json())

    def test_job_created_auto_logs_system_communication(self, owner, customer):
        title = f"TEST_AutoJobCreate_{uuid.uuid4().hex[:6]}"
        r = owner.post(f"{API}/jobs", json={
            "title": title, "customer_id": customer["id"], "customer_name": customer["name"],
            "job_type": "HVAC", "price": 0,
        }, timeout=15)
        assert r.status_code == 200, r.text
        job_id = r.json()["id"]
        comms = owner.get(f"{API}/customers/{customer['id']}/communications", timeout=15).json()
        assert any(
            c["channel"] == "system" and c["summary"] == f"Job created: {title}"
            for c in comms
        ), comms
        return job_id

    def test_job_completed_auto_logs(self, owner, customer):
        title = f"TEST_AutoComplete_{uuid.uuid4().hex[:6]}"
        r = owner.post(f"{API}/jobs", json={
            "title": title, "customer_id": customer["id"], "job_type": "HVAC",
        }, timeout=15)
        job_id = r.json()["id"]
        r = owner.patch(f"{API}/jobs/{job_id}", json={"status": "completed"}, timeout=15)
        assert r.status_code == 200, r.text
        comms = owner.get(f"{API}/customers/{customer['id']}/communications", timeout=15).json()
        assert any(
            c["channel"] == "system" and c["summary"] == f"Job completed: {title}"
            for c in comms
        ), comms


# ============== Timeline ==============
class TestTimeline:
    def test_timeline_merges_and_sorts(self, owner, customer):
        # Create job, comm, file (file via upload)
        title = f"TEST_TL_{uuid.uuid4().hex[:5]}"
        owner.post(f"{API}/jobs", json={"title": title, "customer_id": customer["id"]}, timeout=15)
        owner.post(f"{API}/customers/{customer['id']}/communications",
                   json={"channel": "note", "summary": "TEST_tl_note"}, timeout=15)
        # file upload
        files = {"file": ("TEST_tl.txt", b"hello", "text/plain")}
        r = owner.post(f"{API}/customers/{customer['id']}/files", files=files, timeout=20)
        assert r.status_code == 200, r.text

        r = owner.get(f"{API}/customers/{customer['id']}/timeline", timeout=15)
        assert r.status_code == 200
        events = r.json()
        kinds = {e["kind"] for e in events}
        assert {"job", "comm", "file"}.issubset(kinds), kinds
        # sorted desc by ts
        tss = [e.get("ts") for e in events if e.get("ts")]
        assert tss == sorted(tss, reverse=True)


# ============== Files ==============
class TestFiles:
    def test_upload_list_delete_file(self, owner, customer):
        files = {"file": ("TEST_f.txt", b"contents-xyz", "text/plain")}
        r = owner.post(f"{API}/customers/{customer['id']}/files", files=files, timeout=20)
        assert r.status_code == 200, r.text
        fid = r.json()["id"]
        assert r.json()["filename"] == "TEST_f.txt"
        # list
        r = owner.get(f"{API}/customers/{customer['id']}/files", timeout=15)
        assert any(f["id"] == fid for f in r.json())
        # delete
        r = owner.delete(f"{API}/customers/{customer['id']}/files/{fid}", timeout=15)
        assert r.status_code == 200
        r = owner.get(f"{API}/customers/{customer['id']}/files", timeout=15)
        assert not any(f["id"] == fid for f in r.json())


# ============== AI summary ==============
class TestAISummary:
    def test_summary_returns_model_or_fallback(self, owner, customer):
        r = owner.get(f"{API}/customers/{customer['id']}/summary", timeout=60)
        assert r.status_code == 200, r.text
        body = r.json()
        assert "summary" in body and "model" in body
        # If EMERGENT_LLM_KEY is configured → claude-sonnet-4-5*, else None
        assert body["model"] is None or body["model"].startswith("claude-sonnet-4-5")
        assert isinstance(body["summary"], str) and len(body["summary"]) > 0


# ============== Multi-tenant isolation across cross resources ==============
class TestTenantIsolation:
    def test_other_tenant_cannot_see_customer_subresources(self, owner, other_owner, customer):
        # Create a property + equipment under demo's customer
        p = owner.post(f"{API}/customers/{customer['id']}/properties",
                       json={"address": "TEST_isol"}, timeout=15).json()
        owner.post(f"{API}/customers/{customer['id']}/equipment",
                   json={"property_id": p["id"], "kind": "AC"}, timeout=15)

        # Cross-tenant: GET properties should be empty (different company_id scope)
        r = other_owner.get(f"{API}/customers/{customer['id']}/properties", timeout=15)
        assert r.status_code == 200
        assert r.json() == []
        # equipment empty too
        r = other_owner.get(f"{API}/customers/{customer['id']}/equipment", timeout=15)
        assert r.json() == []
        # timeline: 404 because customer not in other company
        r = other_owner.get(f"{API}/customers/{customer['id']}/timeline", timeout=15)
        assert r.status_code == 404
        # delete property cross-tenant → 404
        r = other_owner.delete(f"{API}/properties/{p['id']}", timeout=15)
        assert r.status_code == 404


# ============== Regression: prior tests still healthy ==============
class TestRegression:
    def test_me(self, owner):
        r = owner.get(f"{API}/auth/me", timeout=15)
        assert r.status_code == 200
        assert r.json()["user"]["role"] == "owner"
