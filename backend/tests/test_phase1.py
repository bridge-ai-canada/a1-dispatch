"""A1 Field Pro Phase 1 tests: photos, signature, files auth, public booking, drag-drop."""
import io
import os
import uuid
import base64
import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"

OWNER = {"email": "demo@a1fieldpro.com", "password": "Demo1234!"}

# 1x1 transparent PNG
PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGNgAAIAAAUAAen63NgAAAAASUVORK5CYII="
)
PNG_DATAURL = "data:image/png;base64," + base64.b64encode(PNG_BYTES).decode()


def _login(creds):
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json=creds, timeout=15)
    assert r.status_code == 200, r.text
    return s, r.json()


@pytest.fixture(scope="session")
def owner_session():
    s, _ = _login(OWNER)
    return s


@pytest.fixture(scope="session")
def owner_company_id(owner_session):
    r = owner_session.get(f"{API}/auth/me", timeout=10)
    return r.json()["company"]["id"]


@pytest.fixture
def fresh_job(owner_session):
    r = owner_session.post(f"{API}/jobs", json={
        "title": "TEST_Phase1", "price": 100.0, "status": "unscheduled"
    }, timeout=10)
    assert r.status_code == 200
    jid = r.json()["id"]
    yield jid
    owner_session.delete(f"{API}/jobs/{jid}", timeout=10)


# ---------- Drag-drop simulation: PATCH scheduled_at promotes unscheduled→scheduled ----------
def test_patch_scheduled_at_promotes_unscheduled(owner_session, fresh_job):
    r = owner_session.patch(f"{API}/jobs/{fresh_job}",
                            json={"scheduled_at": "2026-02-01T10:00:00+00:00"}, timeout=10)
    assert r.status_code == 200
    body = r.json()
    assert body["scheduled_at"].startswith("2026-02-01")
    assert body["status"] == "scheduled_installation"


# ---------- Photo upload + delete ----------
def test_photo_upload_and_delete(owner_session, fresh_job):
    files = {"file": ("test.png", io.BytesIO(PNG_BYTES), "image/png")}
    r = owner_session.post(f"{API}/jobs/{fresh_job}/photos", files=files, timeout=30)
    assert r.status_code == 200, r.text
    photo = r.json()
    assert photo["id"]
    assert photo["path"]
    assert photo["content_type"] == "image/png"

    # Verify on job
    job = owner_session.get(f"{API}/jobs/{fresh_job}", timeout=10).json()
    assert any(p["id"] == photo["id"] for p in (job.get("photos") or []))

    # Delete
    r = owner_session.delete(f"{API}/jobs/{fresh_job}/photos/{photo['id']}", timeout=10)
    assert r.status_code == 200
    job = owner_session.get(f"{API}/jobs/{fresh_job}", timeout=10).json()
    assert not any(p["id"] == photo["id"] for p in (job.get("photos") or []))


def test_photo_upload_rejects_non_image(owner_session, fresh_job):
    files = {"file": ("test.txt", io.BytesIO(b"hello"), "text/plain")}
    r = owner_session.post(f"{API}/jobs/{fresh_job}/photos", files=files, timeout=15)
    assert r.status_code == 400


# ---------- Signature ----------
def test_signature_save(owner_session, fresh_job):
    r = owner_session.post(f"{API}/jobs/{fresh_job}/signature",
                           json={"image_base64": PNG_DATAURL, "signer_name": "John Doe"}, timeout=30)
    assert r.status_code == 200, r.text
    sig = r.json()
    assert sig["path"]
    assert sig["signer_name"] == "John Doe"
    job = owner_session.get(f"{API}/jobs/{fresh_job}", timeout=10).json()
    assert job.get("signature", {}).get("path") == sig["path"]


def test_signature_invalid_base64(owner_session, fresh_job):
    r = owner_session.post(f"{API}/jobs/{fresh_job}/signature",
                           json={"image_base64": "!!!not-base64!!!"}, timeout=10)
    assert r.status_code == 400


# ---------- Files auth + multi-tenant isolation ----------
def test_files_unauthenticated_rejected():
    r = requests.get(f"{API}/files/a1fieldpro/anything/test.png", timeout=10, allow_redirects=False)
    assert r.status_code == 401


def test_files_cross_tenant_forbidden(owner_session, owner_company_id):
    # Path under different company id should be forbidden
    other_company = str(uuid.uuid4())
    path = f"a1fieldpro/{other_company}/jobs/x/file.png"
    r = owner_session.get(f"{API}/files/{path}", timeout=10)
    assert r.status_code == 403


def test_files_serves_own_photo(owner_session, owner_company_id, fresh_job):
    # Upload then fetch
    files = {"file": ("t.png", io.BytesIO(PNG_BYTES), "image/png")}
    up = owner_session.post(f"{API}/jobs/{fresh_job}/photos", files=files, timeout=30).json()
    path = up["path"]
    assert path.startswith(f"a1fieldpro/{owner_company_id}/")
    r = owner_session.get(f"{API}/files/{path}", timeout=30)
    assert r.status_code == 200
    assert r.headers.get("content-type", "").startswith("image/")


# ---------- Public Booking ----------
def test_public_company_returns_no_owner_id(owner_company_id):
    r = requests.get(f"{API}/public/companies/{owner_company_id}", timeout=10)
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == owner_company_id
    assert body.get("name")
    assert "owner_id" not in body


def test_public_company_404():
    r = requests.get(f"{API}/public/companies/{uuid.uuid4()}", timeout=10)
    assert r.status_code == 404


def test_public_booking_creates_unscheduled_job(owner_session, owner_company_id):
    payload = {
        "name": "TEST_Booking Cust",
        "phone": f"555-{uuid.uuid4().hex[:4]}",
        "email": "book@test.com",
        "address": "1 Test Way",
        "job_type": "HVAC",
        "description": "AC not cooling",
    }
    r = requests.post(f"{API}/public/companies/{owner_company_id}/bookings",
                      json=payload, timeout=15)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    jid = body["job_id"]

    # Verify via owner session
    job = owner_session.get(f"{API}/jobs/{jid}", timeout=10).json()
    assert job["status"] == "unscheduled"
    assert job.get("source") == "booking_widget"
    assert job["customer_name"] == payload["name"]
    owner_session.delete(f"{API}/jobs/{jid}", timeout=10)


def test_public_booking_invalid_company():
    r = requests.post(f"{API}/public/companies/{uuid.uuid4()}/bookings",
                      json={"name": "X", "phone": "1", "address": "a"}, timeout=10)
    assert r.status_code == 404
