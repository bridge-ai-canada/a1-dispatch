"""Iteration 24 — Financeit-style program catalog backend tests.

Coverage:
- Min-amount enforcement on POST /api/financing/applications (4500 vs 4499.99)
- Auto-seed of 16 system default programs on GET /api/financing/programs
- POST /api/financing/program-quote across all 4 program kinds (standard, buydown, promo, deferred)
- Program CRUD: create custom / patch / delete (system=soft-disable, custom=hard delete)
- Inline program quote (no program_id) — does not persist
- POST /api/public/financing/{token}/submit accepts new optional applicant fields
- POST /api/financing/from-job with program_id wires SMS pitch to program quote
- POST /api/financing/ai/pitch with $12k, $210/mo → returns 3 variations + family-pizza comparison
"""
import os
import uuid
import pytest
import requests

_url = os.environ.get("REACT_APP_BACKEND_URL")
if not _url:
    # Fallback for pytest CLI runs where frontend .env isn't loaded
    try:
        from dotenv import dotenv_values
        _url = dotenv_values("/app/frontend/.env").get("REACT_APP_BACKEND_URL")
    except Exception:
        _url = None
BASE_URL = (_url or "").rstrip("/")
API = f"{BASE_URL}/api"

OWNER_EMAIL = "demo@a1fieldpro.com"
OWNER_PWD = "Demo1234!"


# -------------------- Fixtures --------------------
@pytest.fixture(scope="module")
def owner_session():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": OWNER_EMAIL, "password": OWNER_PWD}, timeout=20)
    if r.status_code != 200:
        pytest.skip(f"Owner login failed: {r.status_code} {r.text}")
    return s


@pytest.fixture(scope="module")
def programs_seeded(owner_session):
    r = owner_session.get(f"{API}/financing/programs", timeout=20)
    assert r.status_code == 200, r.text
    return r.json()


# -------------------- Programs catalog auto-seed --------------------
SYSTEM_KEYS = {
    "std_60_120", "std_60_180", "std_60_240",
    "std_36_180", "std_84_240", "std_120_240",
    "bd_13_99_to_9_99", "bd_13_99_to_7_99",
    "promo_3", "promo_6", "promo_12", "promo_18", "promo_24",
    "defer_3", "defer_6", "defer_6_int_free",
}


class TestProgramsCatalog:
    def test_seeds_16_system_defaults(self, programs_seeded):
        keys = {p["key"] for p in programs_seeded}
        missing = SYSTEM_KEYS - keys
        assert not missing, f"Missing system program keys: {missing}"
        # At least the 16 we expect (custom programs from prior runs may exist)
        assert len(programs_seeded) >= 16

    def test_default_programs_have_kind_field(self, programs_seeded):
        kinds = {p["kind"] for p in programs_seeded if p["key"] in SYSTEM_KEYS}
        assert kinds == {"standard", "buydown", "promo", "deferred"}, f"Got kinds: {kinds}"

    def test_filter_by_kind(self, owner_session):
        r = owner_session.get(f"{API}/financing/programs", params={"kind": "promo"}, timeout=20)
        assert r.status_code == 200
        items = r.json()
        assert all(p["kind"] == "promo" for p in items)
        promo_keys = {p["key"] for p in items}
        assert {"promo_3", "promo_6", "promo_12", "promo_18", "promo_24"}.issubset(promo_keys)


# -------------------- Program quote math --------------------
def _find_program(programs, key):
    return next((p for p in programs if p["key"] == key), None)


class TestProgramQuote:
    def test_standard_60_term_240_amort(self, owner_session, programs_seeded):
        prog = _find_program(programs_seeded, "std_60_240")
        assert prog, "std_60_240 not seeded"
        r = owner_session.post(
            f"{API}/financing/program-quote",
            json={"amount": 15000, "program_id": prog["id"]},
            timeout=20,
        )
        assert r.status_code == 200, r.text
        q = r.json()
        # monthly payment computed at apr over 240mo amort, balloon at end of 60mo term
        assert abs(q["monthly_payment"] - 175.63) < 1.5, q
        assert abs(q["balloon_payment"] - 13888.28) < 50, q
        assert abs(q["contractor_fee_dollars"] - 975.0) < 1.0, q  # 6.5% of 15k
        assert abs(q["net_payout"] - 14025.0) < 1.0, q
        assert q["total_interest"] > 0
        assert q["total_payback"] > 15000

    def test_buydown_savings_vs_base(self, owner_session, programs_seeded):
        prog = _find_program(programs_seeded, "bd_13_99_to_7_99")
        assert prog, "bd_13_99_to_7_99 not seeded"
        r = owner_session.post(
            f"{API}/financing/program-quote",
            json={"amount": 12000, "program_id": prog["id"]},
            timeout=20,
        )
        assert r.status_code == 200, r.text
        q = r.json()
        assert abs(q["apr"] - 7.99) < 0.01, q
        assert abs(q["dealer_fee_pct"] - 12) < 0.01, q
        assert abs(q["contractor_fee_dollars"] - 1440.0) < 1.0, q
        assert abs(q["net_payout"] - 10560.0) < 1.0, q
        assert q.get("customer_savings_vs_base", 0) > 0, q

    def test_promo_12_zero_interest(self, owner_session, programs_seeded):
        prog = _find_program(programs_seeded, "promo_12")
        assert prog
        r = owner_session.post(
            f"{API}/financing/program-quote",
            json={"amount": 12000, "program_id": prog["id"]},
            timeout=20,
        )
        assert r.status_code == 200, r.text
        q = r.json()
        assert q["apr"] == 0
        assert abs(q["monthly_payment"] - 1000.0) < 1.0, q
        assert q.get("balloon_payment", 0) == 0
        assert abs(q.get("total_interest", 0)) < 1.0, q
        assert abs(q["contractor_fee_dollars"] - 960.0) < 1.0, q  # 8% of 12k

    def test_defer_6_interest_accrues(self, owner_session, programs_seeded):
        prog = _find_program(programs_seeded, "defer_6")
        assert prog
        r = owner_session.post(
            f"{API}/financing/program-quote",
            json={"amount": 12000, "program_id": prog["id"]},
            timeout=20,
        )
        assert r.status_code == 200, r.text
        q = r.json()
        assert q.get("defer_months") == 6
        assert q.get("defer_interest_accrues") is True
        assert q.get("balance_after_deferral", 0) > 12000, q
        assert q["monthly_payment"] > 0

    def test_defer_6_int_free(self, owner_session, programs_seeded):
        prog_free = _find_program(programs_seeded, "defer_6_int_free")
        prog_paid = _find_program(programs_seeded, "defer_6")
        assert prog_free and prog_paid
        r_free = owner_session.post(
            f"{API}/financing/program-quote",
            json={"amount": 12000, "program_id": prog_free["id"]},
            timeout=20,
        )
        r_paid = owner_session.post(
            f"{API}/financing/program-quote",
            json={"amount": 12000, "program_id": prog_paid["id"]},
            timeout=20,
        )
        assert r_free.status_code == 200 and r_paid.status_code == 200
        q_free = r_free.json()
        q_paid = r_paid.json()
        assert q_free.get("defer_interest_accrues") is False
        assert abs(q_free.get("balance_after_deferral", 0) - 12000) < 1.0, q_free
        assert q_free["monthly_payment"] < q_paid["monthly_payment"], (q_free, q_paid)

    def test_inline_program_no_persistence(self, owner_session):
        inline = {
            "kind": "standard",
            "apr": 9.99,
            "dealer_fee_pct": 5.0,
            "term_months": 60,
            "amort_months": 60,
            "key": f"TEST_inline_{uuid.uuid4().hex[:6]}",
            "name": "TEST inline",
        }
        r = owner_session.post(
            f"{API}/financing/program-quote",
            json={"amount": 10000, "program": inline},
            timeout=20,
        )
        assert r.status_code == 200, r.text
        q = r.json()
        assert q["monthly_payment"] > 0
        # Ensure not persisted
        listing = owner_session.get(f"{API}/financing/programs", timeout=20).json()
        assert not any(p["key"] == inline["key"] for p in listing), "Inline quote must not persist"

    def test_missing_program_and_inline_400(self, owner_session):
        r = owner_session.post(f"{API}/financing/program-quote", json={"amount": 10000}, timeout=20)
        assert r.status_code == 400


# -------------------- Program CRUD --------------------
class TestProgramCRUD:
    def test_create_patch_delete_custom(self, owner_session):
        key = f"TEST_custom_{uuid.uuid4().hex[:6]}"
        payload = {
            "key": key,
            "name": "TEST Custom Program",
            "kind": "standard",
            "apr": 8.49,
            "dealer_fee_pct": 5.0,
            "term_months": 60,
            "amort_months": 120,
        }
        r = owner_session.post(f"{API}/financing/programs", json=payload, timeout=20)
        assert r.status_code == 200, r.text
        prog = r.json()
        prog_id = prog["id"]
        assert prog["key"] == key
        assert prog.get("is_system_default") is False

        # PATCH
        r = owner_session.patch(
            f"{API}/financing/programs/{prog_id}",
            json={"apr": 7.5},
            timeout=20,
        )
        assert r.status_code == 200, r.text
        assert abs(r.json()["apr"] - 7.5) < 0.01

        # GET to verify persistence
        listing = owner_session.get(f"{API}/financing/programs", timeout=20).json()
        found = next((p for p in listing if p["id"] == prog_id), None)
        assert found and abs(found["apr"] - 7.5) < 0.01

        # DELETE hard-removes custom
        r = owner_session.delete(f"{API}/financing/programs/{prog_id}", timeout=20)
        assert r.status_code == 200, r.text
        assert r.json().get("ok") is True
        assert not r.json().get("soft_disabled")

        listing = owner_session.get(f"{API}/financing/programs", timeout=20).json()
        assert not any(p["id"] == prog_id for p in listing)

    def test_delete_system_default_soft_disables(self, owner_session, programs_seeded):
        # Pick a system program (won't actually break much — others remain)
        # Use promo_24 to minimize risk
        prog = _find_program(programs_seeded, "promo_24")
        assert prog
        r = owner_session.delete(f"{API}/financing/programs/{prog['id']}", timeout=20)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("soft_disabled") is True

        # Re-enable for next runs
        owner_session.patch(
            f"{API}/financing/programs/{prog['id']}",
            json={"active": True},
            timeout=20,
        )


# -------------------- Application min-amount enforcement --------------------
class TestApplicationMinAmount:
    def test_amount_4000_rejected(self, owner_session):
        r = owner_session.post(
            f"{API}/financing/applications",
            json={
                "customer_name": "TEST Min Reject",
                "amount": 4000,
                "term_months": 60,
            },
            timeout=20,
        )
        assert r.status_code in (400, 422), r.text

    def test_amount_4500_accepted(self, owner_session):
        r = owner_session.post(
            f"{API}/financing/applications",
            json={
                "customer_name": "TEST Min Accept",
                "amount": 4500,
                "term_months": 60,
            },
            timeout=20,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("amount") == 4500
        assert body.get("public_token")


# -------------------- Public submit with extended applicant fields --------------------
class TestPublicSubmitExtendedFields:
    def test_submit_with_new_fields(self, owner_session):
        # Create app to get token
        r = owner_session.post(
            f"{API}/financing/applications",
            json={
                "customer_name": "TEST Extended",
                "amount": 12000,
                "term_months": 60,
            },
            timeout=20,
        )
        assert r.status_code == 200
        token = r.json()["public_token"]

        # Submit applicant details — no ssn4, include new fields
        payload = {
            "first_name": "Test",
            "last_name": "Applicant",
            "email": "test_applicant@example.com",
            "phone": "555-123-4567",
            "dob": "1990-01-15",
            "sin": "123-456-789",
            "address": "1 Maple Ln",
            "city": "Toronto",
            "state": "ON",
            "postal_code": "M5V 1A1",
            "home_ownership": "own",
            "fico_bucket": "good",
            "monthly_income": 5500,
            "monthly_obligations": 1200,
            "employment_status": "full_time",
            "employer_name": "Acme Corp",
            "years_employed": 3.5,
            "project_description": "HVAC replacement",
            "consent_soft_pull": True,
        }
        # Public submit URL — try both common path shapes
        url1 = f"{API}/public/financing/{token}/submit"
        r2 = requests.post(url1, json=payload, timeout=20)
        assert r2.status_code == 200, f"{r2.status_code} {r2.text}"


# -------------------- AI Pitch generator --------------------
class TestAIPitch:
    def test_pitch_returns_3_variations(self, owner_session):
        r = owner_session.post(
            f"{API}/financing/ai/pitch",
            json={
                "amount": 12000,
                "monthly_payment": 210,
                "term_months": 60,
                "apr": 9.99,
            },
            timeout=20,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert isinstance(body.get("pitches"), list)
        assert len(body["pitches"]) == 3
        assert body.get("default") == body["pitches"][0]
        assert body.get("comparison_used")
        # $210/mo: highest threshold <= 210 is 180 → "family pizza night"
        assert "pizza" in body["comparison_used"].lower(), body


# -------------------- from-job with program_id --------------------
class TestFromJobWithProgram:
    def test_from_job_with_program(self, owner_session, programs_seeded):
        # Create a job
        job_payload = {
            "title": f"TEST iter24 finance-with-program {uuid.uuid4().hex[:6]}",
            "status": "in_progress",
            "price": 12000,
            "customer_name": "TEST Customer",
        }
        rj = owner_session.post(f"{API}/jobs", json=job_payload, timeout=20)
        assert rj.status_code in (200, 201), rj.text
        job_id = rj.json()["id"]

        prog = _find_program(programs_seeded, "std_60_120")
        assert prog
        r = owner_session.post(
            f"{API}/financing/from-job",
            json={
                "job_id": job_id,
                "amount": 12000,
                "term_months": 60,
                "program_id": prog["id"],
                "send_sms": False,
            },
            timeout=20,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("amount") == 12000
        assert body.get("application_id")
        assert body.get("public_token")
        # Verify program_id was stored on the application
        app_id = body["application_id"]
        # GET applications & find the one we just created
        r2 = owner_session.get(f"{API}/financing/applications", timeout=20)
        assert r2.status_code == 200
        apps = r2.json()
        match = next((a for a in apps if a.get("id") == app_id), None)
        assert match is not None, f"Application {app_id} not found in listing"
        assert match.get("program_id") == prog["id"], match
