"""Iteration 22 — Fresh Cash Finance test suite.

Covers:
- APR ladder + calculator math
- Application create (owner) + public token visibility
- Public view/submit/sign flow with decision sanity
- Buy-down quote + apply (mutates offer)
- Funding events auto-advance to funded
- Rentals (auto-calc weekly/monthly), dashboard, admin endpoints
- Public estimate -> finance idempotency
"""
import os
import pytest
import requests
from pathlib import Path

if not os.environ.get("REACT_APP_BACKEND_URL"):
    fe = Path("/app/frontend/.env")
    if fe.exists():
        for line in fe.read_text().splitlines():
            if line.startswith("REACT_APP_BACKEND_URL"):
                os.environ["REACT_APP_BACKEND_URL"] = line.split("=", 1)[1].strip()

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")

OWNER = {"email": "demo@a1fieldpro.com", "password": "Demo1234!"}
SUPER = {"email": "superadmin@a1fieldpro.com", "password": "Super1234!"}
TECH = {"email": "tech@a1fieldpro.com", "password": "Demo1234!"}


def _login(creds):
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json=creds, timeout=30)
    if r.status_code != 200:
        pytest.skip(f"login failed for {creds['email']}: {r.status_code} {r.text}")
    data = r.json()
    tok = data.get("access_token") or data.get("token")
    if tok:
        s.headers.update({"Authorization": f"Bearer {tok}"})
    return s


@pytest.fixture(scope="module")
def owner_client():
    return _login(OWNER)


@pytest.fixture(scope="module")
def super_client():
    return _login(SUPER)


@pytest.fixture(scope="module")
def tech_client():
    return _login(TECH)


# -------------------- Ladder + Calc --------------------
class TestLadderAndCalc:
    def test_ladder(self, owner_client):
        r = owner_client.get(f"{BASE_URL}/api/financing/ladder")
        assert r.status_code == 200, r.text
        items = r.json()
        assert isinstance(items, list) and len(items) == 5
        labels = [t["label"] for t in items]
        assert set(labels) >= {"excellent", "good", "fair", "subprime", "declined"}
        excellent = next(t for t in items if t["label"] == "excellent")
        assert excellent["base_apr"] == 6.99
        assert excellent["max_term"] == 84

    def test_calculate(self, owner_client):
        r = owner_client.post(
            f"{BASE_URL}/api/financing/calculate",
            json={"amount": 5000, "apr": 9.99, "term_months": 36},
        )
        assert r.status_code == 200, r.text
        d = r.json()
        assert abs(d["monthly_payment"] - 161.30) < 1.0
        assert len(d["schedule"]) == 36
        assert d["schedule"][-1]["balance"] == 0.0


# -------------------- Application flow --------------------
class TestApplicationFlow:
    app_id = None
    public_token = None

    def test_create_application(self, owner_client):
        r = owner_client.post(
            f"{BASE_URL}/api/financing/applications",
            json={
                "customer_name": "TEST_Finance_Customer",
                "customer_email": "test_finance@example.com",
                "amount": 5000,
                "term_months": 36,
            },
        )
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["status"] == "started"
        assert "public_token" in d and d["public_token"]
        assert "ssn4" not in str(d.get("applicant") or "")
        TestApplicationFlow.app_id = d["id"]
        TestApplicationFlow.public_token = d["public_token"]

    def test_list_strips_token(self, owner_client):
        r = owner_client.get(f"{BASE_URL}/api/financing/applications")
        assert r.status_code == 200
        items = r.json()
        assert isinstance(items, list)
        for it in items:
            assert "public_token" not in it

    def test_public_view(self):
        s = requests.Session()
        r = s.get(f"{BASE_URL}/api/public/financing/{TestApplicationFlow.public_token}")
        assert r.status_code == 200, r.text
        d = r.json()
        assert "application" in d and "company" in d
        assert "primary_color" in d["company"]
        app = d["application"]
        # PII stripped
        applicant = app.get("applicant") or {}
        assert "ssn4" not in applicant
        assert "dob" not in applicant
        assert "score" not in app
        assert "bureau" not in app

    def test_submit_without_consent_400(self):
        s = requests.Session()
        r = s.post(
            f"{BASE_URL}/api/public/financing/{TestApplicationFlow.public_token}/submit",
            json={
                "first_name": "Jane", "last_name": "Doe",
                "email": "jane@example.com", "phone": "5551234567",
                "dob": "1985-01-01", "ssn4": "1234",
                "fico_bucket": "excellent",
                "monthly_income": 6000, "monthly_obligations": 1000,
                "employment_status": "full_time",
                "consent_soft_pull": False,
            },
        )
        assert r.status_code == 400

    def test_submit_excellent_approved(self):
        s = requests.Session()
        r = s.post(
            f"{BASE_URL}/api/public/financing/{TestApplicationFlow.public_token}/submit",
            json={
                "first_name": "Jane", "last_name": "Doe",
                "email": "jane@example.com", "phone": "5551234567",
                "dob": "1985-01-01", "ssn4": "1234",
                "fico_bucket": "excellent",
                "monthly_income": 10000, "monthly_obligations": 500,
                "employment_status": "full_time",
                "consent_soft_pull": True,
            },
        )
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["decision"] == "approved"
        assert d["offer"]["apr"] == 6.99
        assert d["tier_label"] == "excellent"

    def test_buydown_quote(self, owner_client):
        r = owner_client.post(
            f"{BASE_URL}/api/financing/buydown/quote",
            json={"application_id": TestApplicationFlow.app_id, "fee_pct": 4},
        )
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["apr_reduction_points"] == 2.0
        assert d["new_apr"] == round(6.99 - 2.0, 2)
        assert d["customer_lifetime_savings"] > 0

    def test_buydown_apply(self, owner_client):
        r = owner_client.post(
            f"{BASE_URL}/api/financing/buydown",
            json={"application_id": TestApplicationFlow.app_id, "fee_pct": 4},
        )
        assert r.status_code == 200, r.text
        # Verify mutation
        r2 = owner_client.get(
            f"{BASE_URL}/api/financing/applications/{TestApplicationFlow.app_id}"
        )
        assert r2.status_code == 200
        offer = r2.json().get("offer") or {}
        assert offer.get("apr") == round(6.99 - 2.0, 2)
        assert "buydown" in offer

    def test_sign_application(self):
        s = requests.Session()
        r = s.post(
            f"{BASE_URL}/api/public/financing/{TestApplicationFlow.public_token}/sign",
            json={"signer_name": "Jane Doe", "signature_base64": "data:image/png;base64,AAAA"},
        )
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["status"] == "signed"
        assert d.get("contract_id")

    def test_disbursement_advances_to_funded(self, owner_client):
        r = owner_client.post(
            f"{BASE_URL}/api/financing/funding-events",
            json={
                "application_id": TestApplicationFlow.app_id,
                "amount": 5000,
                "kind": "disbursement",
                "memo": "TEST_disbursement",
            },
        )
        assert r.status_code == 200, r.text
        # Verify status flipped
        r2 = owner_client.get(
            f"{BASE_URL}/api/financing/applications/{TestApplicationFlow.app_id}"
        )
        assert r2.json()["status"] == "funded"


# -------------------- Decision sanity / DTI --------------------
class TestDecisionSanity:
    def test_fair_dti(self, owner_client):
        # Create
        r = owner_client.post(
            f"{BASE_URL}/api/financing/applications",
            json={"customer_name": "TEST_DTI", "amount": 5000, "term_months": 36},
        )
        assert r.status_code == 200
        token = r.json()["public_token"]
        # Submit fair w/ high DTI
        s = requests.Session()
        r2 = s.post(
            f"{BASE_URL}/api/public/financing/{token}/submit",
            json={
                "first_name": "Frank", "last_name": "Fair",
                "email": "frank@example.com", "phone": "5557654321",
                "dob": "1980-01-01", "ssn4": "9999",
                "fico_bucket": "fair",
                "monthly_income": 4000, "monthly_obligations": 1200,
                "employment_status": "full_time",
                "consent_soft_pull": True,
            },
        )
        assert r2.status_code == 200, r2.text
        d = r2.json()
        assert d["decision"] in ("approved", "counter_offer", "manual_review")
        # payment included; DTI present on offer
        offer = d.get("offer") or {}
        if offer:
            assert "dti" in offer


# -------------------- Rentals --------------------
class TestRentals:
    def test_create_rental_autocalc(self, owner_client):
        r = owner_client.post(
            f"{BASE_URL}/api/financing/rentals",
            json={
                "customer_name": "TEST_Rental",
                "equipment_name": "TEST_HVAC Unit",
                "equipment_value": 5200,
                "weekly_payment": 100,
                "term_weeks": 52,
            },
        )
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["weekly_payment"] == 100
        # monthly auto-derived
        assert d["monthly_payment"] > 0
        assert abs(d["monthly_payment"] - round(100 * 52 / 12, 2)) < 0.05

    def test_create_rental_defaults(self, owner_client):
        r = owner_client.post(
            f"{BASE_URL}/api/financing/rentals",
            json={
                "customer_name": "TEST_Rental2",
                "equipment_name": "TEST_HVAC Defaults",
                "equipment_value": 5200,
                "term_weeks": 52,
            },
        )
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["weekly_payment"] > 0 and d["monthly_payment"] > 0


# -------------------- Dashboard --------------------
class TestDashboard:
    def test_dashboard_rollup(self, owner_client):
        r = owner_client.get(f"{BASE_URL}/api/financing/dashboard")
        assert r.status_code == 200, r.text
        d = r.json()
        for k in ("pipeline", "total_funded", "total_buydown_fees",
                  "pending_amount", "rentals_active"):
            assert k in d
        assert d["total_funded"] >= 5000  # we disbursed at least one above


# -------------------- Admin --------------------
class TestAdmin:
    def test_owner_blocked_from_admin_list(self, owner_client):
        r = owner_client.get(f"{BASE_URL}/api/financing/admin/applications")
        assert r.status_code == 403

    def test_super_admin_list(self, super_client):
        r = super_client.get(f"{BASE_URL}/api/financing/admin/applications")
        assert r.status_code == 200, r.text
        assert isinstance(r.json(), list)

    def test_super_admin_metrics(self, super_client):
        r = super_client.get(f"{BASE_URL}/api/financing/admin/metrics")
        assert r.status_code == 200, r.text
        d = r.json()
        for k in ("by_status", "by_tier", "total_funded", "funding_events"):
            assert k in d

    def test_admin_override_decision(self, super_client, owner_client):
        # Create + submit a fresh app
        r = owner_client.post(
            f"{BASE_URL}/api/financing/applications",
            json={"customer_name": "TEST_AdminOverride", "amount": 6000, "term_months": 36},
        )
        aid = r.json()["id"]
        token = r.json()["public_token"]
        s = requests.Session()
        s.post(
            f"{BASE_URL}/api/public/financing/{token}/submit",
            json={
                "first_name": "Ova", "last_name": "Ride",
                "email": "ova@example.com", "phone": "5550000000",
                "dob": "1990-01-01", "ssn4": "2222",
                "fico_bucket": "good",
                "monthly_income": 8000, "monthly_obligations": 500,
                "employment_status": "full_time",
                "consent_soft_pull": True,
            },
        )
        # Override
        r2 = super_client.patch(
            f"{BASE_URL}/api/financing/admin/applications/{aid}/decision",
            json={"decision": "approved", "apr": 5.5, "term_months": 60, "reason": "TEST"},
        )
        assert r2.status_code == 200, r2.text
        d = r2.json()
        assert d["decision"] == "approved"
        assert d["offer"]["apr"] == 5.5
        assert d["offer"]["term_months"] == 60
        # recomputed monthly
        assert d["offer"]["monthly_payment"] > 0


# -------------------- Public estimate → finance --------------------
class TestEstimateFinance:
    def test_estimate_finance_idempotent(self, owner_client):
        # Create an estimate with a tier total >= MIN_AMOUNT
        # First create a customer
        cr = owner_client.post(
            f"{BASE_URL}/api/customers",
            json={"name": "TEST_FinanceCust", "email": "fc@example.com", "phone": "5555550000"},
        )
        if cr.status_code != 200:
            pytest.skip(f"customer create failed: {cr.status_code} {cr.text}")
        customer_id = cr.json().get("id")
        est_payload = {
            "customer_id": customer_id,
            "customer_name": "TEST_FinanceCust",
            "tiers": [
                {
                    "key": "good",
                    "name": "Good",
                    "line_items": [
                        {"description": "Service", "qty": 1, "unit_price": 5000},
                    ],
                }
            ],
        }
        er = owner_client.post(f"{BASE_URL}/api/estimates", json=est_payload)
        if er.status_code != 200:
            pytest.skip(f"estimate create failed: {er.status_code} {er.text}")
        est = er.json()
        token = est.get("public_token")
        if not token:
            pytest.skip("estimate has no public_token")
        # First call
        s = requests.Session()
        r1 = s.post(
            f"{BASE_URL}/api/public/estimates/{token}/finance",
            json={"selected_tier": "good"},
        )
        assert r1.status_code == 200, r1.text
        d1 = r1.json()
        assert d1["amount"] == 5000
        assert d1["application_id"]
        # Second call returns same app
        r2 = s.post(
            f"{BASE_URL}/api/public/estimates/{token}/finance",
            json={"selected_tier": "good"},
        )
        assert r2.status_code == 200
        d2 = r2.json()
        assert d2["application_id"] == d1["application_id"]
        assert d2["public_token"] == d1["public_token"]

    def test_estimate_finance_too_small_400(self, owner_client):
        cr = owner_client.post(
            f"{BASE_URL}/api/customers",
            json={"name": "TEST_TinyCust", "email": "tc@example.com", "phone": "5555550001"},
        )
        if cr.status_code != 200:
            pytest.skip()
        customer_id = cr.json().get("id")
        er = owner_client.post(
            f"{BASE_URL}/api/estimates",
            json={
                "customer_id": customer_id,
                "customer_name": "TEST_TinyCust",
                "tiers": [{"key": "good", "name": "Good",
                           "line_items": [{"description": "Tiny", "qty": 1, "unit_price": 100}]}],
            },
        )
        if er.status_code != 200:
            pytest.skip()
        token = er.json().get("public_token")
        if not token:
            pytest.skip()
        s = requests.Session()
        r = s.post(
            f"{BASE_URL}/api/public/estimates/{token}/finance",
            json={"selected_tier": "good"},
        )
        assert r.status_code == 400
