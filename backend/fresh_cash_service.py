"""Fresh Cash Finance — decisioning engine + amortization math.

Architecture:
- `BureauAdapter` protocol with two implementations:
   - `MockBureauAdapter` (default): deterministic scoring from inputs — used in dev.
   - `RealBureauAdapter` (env-gated): proxy for Plaid Credit / Experian / Equifax.
     Wired but inactive until the bureau provider env vars are set.
- `decide()` runs the pipeline: prequal → DTI check → tier select → counter-offer logic.

Plug in a real bureau later by setting env:
  CREDIT_BUREAU_PROVIDER = "plaid" | "experian" | "equifax"
  CREDIT_BUREAU_API_KEY  = "..."
  CREDIT_BUREAU_BASE_URL = "..."
The current code will preserve the same `decide()` signature.
"""
import os
import logging
from typing import Protocol

logger = logging.getLogger("a1fieldpro.freshcash")

# -------------------- APR ladder --------------------
# (lower_score, upper_score, base_apr, max_term_months, label)
APR_LADDER = [
    (740, 850, 6.99, 84, "excellent"),
    (700, 739, 9.99, 60, "good"),
    (660, 699, 14.99, 48, "fair"),
    (580, 659, 19.99, 24, "subprime"),
    (0,   579, None,  0,  "declined"),
]

FICO_BUCKETS = {
    "excellent": 760,
    "good":      720,
    "fair":      680,
    "poor":      640,
    "subprime":  590,
    "unknown":   680,  # neutral assumption
}

MIN_AMOUNT = 4500.0
MAX_AMOUNT = 150000.0
MIN_TERM = 3
MAX_TERM = 120
DTI_LIMIT = 0.45  # debt-to-income cap
MAX_AMORT = 240   # months (20 years) — used by long-amort programs


# -------------------- Bureau adapter --------------------
class BureauAdapter(Protocol):
    async def soft_pull(self, applicant: dict) -> dict:
        """Return {score:int, bureau:str, raw:dict}."""
        ...


class MockBureauAdapter:
    name = "mock"

    async def soft_pull(self, applicant: dict) -> dict:
        bucket = (applicant.get("fico_bucket") or "unknown").lower()
        score = FICO_BUCKETS.get(bucket, 680)
        # tiny deterministic spread by ssn4 / name hash for realism
        seed = (applicant.get("ssn4") or applicant.get("email") or "0") + str(applicant.get("dob") or "")
        score += (sum(ord(c) for c in seed) % 20) - 10
        score = max(300, min(score, 850))
        return {"score": score, "bureau": "mock", "raw": {"derived": True}}


class RealBureauAdapter:
    """Env-gated stub. Will issue a real soft-pull when configured."""
    name = "real"

    def __init__(self):
        self.provider = os.environ.get("CREDIT_BUREAU_PROVIDER", "").lower()
        self.api_key = os.environ.get("CREDIT_BUREAU_API_KEY", "")
        self.base_url = os.environ.get("CREDIT_BUREAU_BASE_URL", "")

    @property
    def configured(self) -> bool:
        return bool(self.provider and self.api_key and self.base_url)

    async def soft_pull(self, applicant: dict) -> dict:
        if not self.configured:
            raise RuntimeError("Real bureau not configured")
        # Real HTTP call will go here — keep interface stable for swap-in.
        # import httpx
        # async with httpx.AsyncClient(timeout=15) as c:
        #     r = await c.post(f"{self.base_url}/soft-pull",
        #                      headers={"Authorization": f"Bearer {self.api_key}"},
        #                      json={...})
        #     ...
        raise NotImplementedError(
            f"RealBureauAdapter wired for {self.provider} but no provider HTTP yet."
        )


def _get_adapter() -> BureauAdapter:
    real = RealBureauAdapter()
    if real.configured:
        try:
            # smoke-test instantiation; real call happens later in soft_pull
            return real
        except Exception as e:
            logger.warning(f"Real bureau adapter init failed, falling back to mock: {e}")
    return MockBureauAdapter()


# -------------------- Math --------------------
def monthly_payment(principal: float, apr: float, term_months: int) -> float:
    if principal <= 0 or term_months <= 0:
        return 0.0
    if apr <= 0:
        return round(principal / term_months, 2)
    r = (apr / 100.0) / 12.0
    pmt = principal * (r * (1 + r) ** term_months) / ((1 + r) ** term_months - 1)
    return round(pmt, 2)


def amortization_schedule(principal: float, apr: float, term_months: int) -> list:
    """Standard amortization table. Each row: {n, payment, principal, interest, balance}."""
    if principal <= 0 or term_months <= 0:
        return []
    pmt = monthly_payment(principal, apr, term_months)
    r = (apr / 100.0) / 12.0
    balance = principal
    rows = []
    for n in range(1, term_months + 1):
        interest = round(balance * r, 2) if r > 0 else 0.0
        principal_part = round(pmt - interest, 2)
        if n == term_months:
            # last row: square the balance
            principal_part = round(balance, 2)
            pmt_last = round(principal_part + interest, 2)
            rows.append({"n": n, "payment": pmt_last, "principal": principal_part,
                         "interest": interest, "balance": 0.0})
            break
        balance = round(balance - principal_part, 2)
        rows.append({"n": n, "payment": pmt, "principal": principal_part,
                     "interest": interest, "balance": max(balance, 0.0)})
    return rows


def total_finance_charge(principal: float, apr: float, term_months: int) -> float:
    pmt = monthly_payment(principal, apr, term_months)
    return round(pmt * term_months - principal, 2)


# -------------------- Program-aware quote --------------------
# Programs describe the deal structure (Standard / Buy-Down / 0% Promo / Deferred)
# and let admins shape contractor economics. A "term" is what the customer pays;
# "amortization" is the schedule used to compute the monthly payment — a balloon
# at the end of the term covers the remaining balance.
def program_quote(amount: float, program: dict) -> dict:
    """Compute the payment economics for an `amount` against a financing program.

    program dict shape:
      - kind: "standard" | "buydown" | "promo" | "deferred"
      - apr: customer APR (post-buydown)
      - base_apr: pre-buydown APR (for buydown programs); else None
      - buydown_pct: how many APR points the contractor bought down (0 if N/A)
      - dealer_fee_pct: contractor fee as % of financed amount (e.g., 4.5)
      - term_months: customer payback term
      - amort_months: amortization schedule length (>= term_months). Balloon at end of term.
      - promo_months: if kind=='promo', equal-payment 0% term (3/6/12/18/24)
      - defer_months: months of payment deferral (kind=='deferred')
      - defer_interest_accrues: True = interest accrues during deferral
    """
    amount = float(amount or 0)
    kind = (program.get("kind") or "standard").lower()
    dealer_fee_pct = float(program.get("dealer_fee_pct") or 0)
    contractor_fee_dollars = round(amount * (dealer_fee_pct / 100.0), 2)
    net_payout = round(amount - contractor_fee_dollars, 2)
    quote = {
        "kind": kind,
        "amount": amount,
        "dealer_fee_pct": dealer_fee_pct,
        "contractor_fee_dollars": contractor_fee_dollars,
        "net_payout": net_payout,
    }

    if kind == "promo":
        # 0% equal-payment plan over promo_months
        promo_months = int(program.get("promo_months") or 12)
        pmt = round(amount / promo_months, 2)
        quote.update({
            "apr": 0.0, "base_apr": None, "buydown_pct": 0.0,
            "term_months": promo_months, "amort_months": promo_months,
            "monthly_payment": pmt, "balloon_payment": 0.0,
            "total_interest": 0.0,
            "total_payback": round(pmt * promo_months, 2),
            "promo_months": promo_months,
        })
        return quote

    if kind == "deferred":
        defer_months = int(program.get("defer_months") or 6)
        apr = float(program.get("apr") or 9.99)
        term = int(program.get("term_months") or 60)
        amort = int(program.get("amort_months") or term)
        interest_accrues = bool(program.get("defer_interest_accrues", True))
        # If interest accrues during the deferral, balance grows; payments start after deferral.
        start_principal = amount
        if interest_accrues and apr > 0:
            r = (apr / 100.0) / 12.0
            start_principal = round(amount * ((1 + r) ** defer_months), 2)
        amort_pmt = monthly_payment(start_principal, apr, amort)
        # Balloon when amort > term (payments only for `term` months after deferral)
        balance_after_term = _balance_after(start_principal, apr, amort_pmt, term)
        quote.update({
            "apr": apr, "base_apr": None, "buydown_pct": 0.0,
            "term_months": term + defer_months, "amort_months": amort,
            "monthly_payment": amort_pmt,
            "defer_months": defer_months,
            "defer_interest_accrues": interest_accrues,
            "balance_after_deferral": start_principal,
            "balloon_payment": round(balance_after_term, 2) if amort > term else 0.0,
            "total_interest": round(amort_pmt * term + balance_after_term - amount, 2),
            "total_payback": round(amort_pmt * term + balance_after_term, 2),
        })
        return quote

    # standard or buydown — uses term/amort + apr
    apr = float(program.get("apr") or 9.99)
    base_apr = program.get("base_apr")
    buydown_pct = float(program.get("buydown_pct") or 0)
    term = int(program.get("term_months") or 60)
    amort = int(program.get("amort_months") or term)
    amort_pmt = monthly_payment(amount, apr, amort)
    balance_after_term = _balance_after(amount, apr, amort_pmt, term)
    # Customer savings vs base_apr (for buydown programs)
    customer_savings = 0.0
    if base_apr and base_apr > apr:
        base_pmt = monthly_payment(amount, float(base_apr), amort)
        customer_savings = round((base_pmt - amort_pmt) * term, 2)
    quote.update({
        "apr": apr, "base_apr": base_apr, "buydown_pct": buydown_pct,
        "term_months": term, "amort_months": amort,
        "monthly_payment": amort_pmt,
        "balloon_payment": round(balance_after_term, 2) if amort > term else 0.0,
        "total_interest": round(amort_pmt * term + balance_after_term - amount, 2),
        "total_payback": round(amort_pmt * term + balance_after_term, 2),
        "customer_savings_vs_base": customer_savings,
    })
    return quote


def _balance_after(principal: float, apr: float, payment: float, months: int) -> float:
    """Remaining balance after `months` payments at `payment` and `apr`."""
    if months <= 0:
        return round(principal, 2)
    r = (apr / 100.0) / 12.0
    if r <= 0:
        return max(0.0, round(principal - payment * months, 2))
    bal = principal
    for _ in range(months):
        interest = bal * r
        bal = bal + interest - payment
        if bal < 0:
            return 0.0
    return round(bal, 2)


# -------------------- Default programs catalog --------------------
# Companies are seeded with these. Admins can edit/add per-tenant.
DEFAULT_PROGRAMS = [
    # Standard APR programs
    {"key": "std_60_120", "name": "Standard 60mo / 120mo amort", "kind": "standard",
     "apr": 9.99, "dealer_fee_pct": 4.5, "term_months": 60, "amort_months": 120,
     "active": True, "is_system_default": True},
    {"key": "std_60_180", "name": "Standard 60mo / 180mo amort", "kind": "standard",
     "apr": 11.99, "dealer_fee_pct": 5.5, "term_months": 60, "amort_months": 180,
     "active": True, "is_system_default": True},
    {"key": "std_60_240", "name": "Standard 60mo / 240mo amort", "kind": "standard",
     "apr": 12.99, "dealer_fee_pct": 6.5, "term_months": 60, "amort_months": 240,
     "active": True, "is_system_default": True},
    {"key": "std_36_180", "name": "Standard 36mo / 180mo amort", "kind": "standard",
     "apr": 10.99, "dealer_fee_pct": 5.0, "term_months": 36, "amort_months": 180,
     "active": True, "is_system_default": True},
    {"key": "std_84_240", "name": "Standard 84mo / 240mo amort", "kind": "standard",
     "apr": 11.99, "dealer_fee_pct": 6.0, "term_months": 84, "amort_months": 240,
     "active": True, "is_system_default": True},
    {"key": "std_120_240", "name": "Standard 120mo / 240mo amort", "kind": "standard",
     "apr": 13.99, "dealer_fee_pct": 7.0, "term_months": 120, "amort_months": 240,
     "active": True, "is_system_default": True},
    # Buy-down programs
    {"key": "bd_13_99_to_9_99", "name": "Buy-down 13.99% → 9.99%", "kind": "buydown",
     "apr": 9.99, "base_apr": 13.99, "buydown_pct": 4.0, "dealer_fee_pct": 8.0,
     "term_months": 60, "amort_months": 120,
     "active": True, "is_system_default": True},
    {"key": "bd_13_99_to_7_99", "name": "Buy-down 13.99% → 7.99%", "kind": "buydown",
     "apr": 7.99, "base_apr": 13.99, "buydown_pct": 6.0, "dealer_fee_pct": 12.0,
     "term_months": 60, "amort_months": 120,
     "active": True, "is_system_default": True},
    # 0% Promotional plans (equal payments)
    {"key": "promo_3", "name": "0% / 3-month equal payments", "kind": "promo",
     "promo_months": 3, "dealer_fee_pct": 4.0, "apr": 0.0,
     "active": True, "is_system_default": True},
    {"key": "promo_6", "name": "0% / 6-month equal payments", "kind": "promo",
     "promo_months": 6, "dealer_fee_pct": 6.0, "apr": 0.0,
     "active": True, "is_system_default": True},
    {"key": "promo_12", "name": "0% / 12-month equal payments", "kind": "promo",
     "promo_months": 12, "dealer_fee_pct": 8.0, "apr": 0.0,
     "active": True, "is_system_default": True},
    {"key": "promo_18", "name": "0% / 18-month equal payments", "kind": "promo",
     "promo_months": 18, "dealer_fee_pct": 10.0, "apr": 0.0,
     "active": True, "is_system_default": True},
    {"key": "promo_24", "name": "0% / 24-month equal payments", "kind": "promo",
     "promo_months": 24, "dealer_fee_pct": 12.0, "apr": 0.0,
     "active": True, "is_system_default": True},
    # Deferred-payment plans
    {"key": "defer_3", "name": "3-month deferred / 60mo standard", "kind": "deferred",
     "defer_months": 3, "defer_interest_accrues": True,
     "apr": 9.99, "dealer_fee_pct": 5.5, "term_months": 60, "amort_months": 60,
     "active": True, "is_system_default": True},
    {"key": "defer_6", "name": "6-month deferred / 60mo standard", "kind": "deferred",
     "defer_months": 6, "defer_interest_accrues": True,
     "apr": 9.99, "dealer_fee_pct": 7.0, "term_months": 60, "amort_months": 60,
     "active": True, "is_system_default": True},
    {"key": "defer_6_int_free", "name": "6-month deferred / no interest accrual", "kind": "deferred",
     "defer_months": 6, "defer_interest_accrues": False,
     "apr": 9.99, "dealer_fee_pct": 10.0, "term_months": 60, "amort_months": 60,
     "active": True, "is_system_default": True},
]


# -------------------- Tier select + decision --------------------
def select_tier(score: int) -> dict:
    for lo, hi, apr, max_term, label in APR_LADDER:
        if lo <= score <= hi:
            return {"label": label, "base_apr": apr, "max_term": max_term,
                    "score_range": (lo, hi)}
    return {"label": "declined", "base_apr": None, "max_term": 0, "score_range": (0, 0)}


def estimate_dti(monthly_income: float, monthly_obligations: float, new_payment: float) -> float:
    """Debt-to-income with the proposed new payment included."""
    if monthly_income <= 0:
        return 1.0
    return round((monthly_obligations + new_payment) / monthly_income, 3)


async def decide(application: dict) -> dict:
    """Run a soft-pull + decisioning. Returns a structured decision dict.

    Decision values:
      - approved           : all good, single offer
      - counter_offer      : approved at a stricter term/amount
      - manual_review      : referred to human (DTI just over limit, etc.)
      - declined           : score too low
    """
    amount = float(application.get("amount") or 0)
    term = int(application.get("term_months") or 36)
    monthly_income = float(application.get("monthly_income") or 0)
    monthly_obligations = float(application.get("monthly_obligations") or 0)

    if amount < MIN_AMOUNT or amount > MAX_AMOUNT:
        return {
            "decision": "declined", "reason": "amount_out_of_range",
            "min_amount": MIN_AMOUNT, "max_amount": MAX_AMOUNT,
            "bureau": None, "score": None, "tier": None, "offer": None,
        }

    adapter = _get_adapter()
    try:
        pull = await adapter.soft_pull(application)
    except Exception as e:
        logger.error(f"Bureau pull failed, defaulting to mock: {e}")
        pull = await MockBureauAdapter().soft_pull(application)

    score = int(pull["score"])
    tier = select_tier(score)

    if tier["label"] == "declined":
        return {
            "decision": "declined", "reason": "score_too_low",
            "bureau": pull["bureau"], "score": score, "tier": tier, "offer": None,
        }

    final_term = min(term, tier["max_term"])
    apr = tier["base_apr"]
    pmt = monthly_payment(amount, apr, final_term)
    dti = estimate_dti(monthly_income, monthly_obligations, pmt)

    if dti > DTI_LIMIT:
        # try max term to reduce payment, then re-evaluate
        relaxed_term = tier["max_term"]
        pmt_relaxed = monthly_payment(amount, apr, relaxed_term)
        dti_relaxed = estimate_dti(monthly_income, monthly_obligations, pmt_relaxed)
        if dti_relaxed <= DTI_LIMIT:
            return {
                "decision": "counter_offer", "reason": "dti_exceeded_use_max_term",
                "bureau": pull["bureau"], "score": score, "tier": tier,
                "offer": {
                    "amount": amount, "apr": apr, "term_months": relaxed_term,
                    "monthly_payment": pmt_relaxed,
                    "total_finance_charge": total_finance_charge(amount, apr, relaxed_term),
                    "dti": dti_relaxed,
                },
            }
        # over DTI even with max term → manual review
        return {
            "decision": "manual_review", "reason": "high_dti",
            "bureau": pull["bureau"], "score": score, "tier": tier,
            "offer": {
                "amount": amount, "apr": apr, "term_months": relaxed_term,
                "monthly_payment": pmt_relaxed,
                "total_finance_charge": total_finance_charge(amount, apr, relaxed_term),
                "dti": dti_relaxed,
            },
        }

    return {
        "decision": "approved", "reason": "ok",
        "bureau": pull["bureau"], "score": score, "tier": tier,
        "offer": {
            "amount": amount, "apr": apr, "term_months": final_term,
            "monthly_payment": pmt,
            "total_finance_charge": total_finance_charge(amount, apr, final_term),
            "dti": dti,
        },
    }


# -------------------- Buy-down --------------------
BUYDOWN_RATIO = 0.5  # contractor fee % → customer APR reduction in points


def buydown_quote(amount: float, apr: float, term_months: int, fee_pct: float) -> dict:
    """Contractor pays fee_pct (%) of financed amount to reduce customer APR.
    The reduction is fee_pct × BUYDOWN_RATIO points (e.g., 4% fee → 2 APR points off).
    """
    fee_pct = max(0.0, min(fee_pct or 0.0, 8.0))
    reduction = round(fee_pct * BUYDOWN_RATIO, 2)
    new_apr = max(0.0, round(apr - reduction, 2))
    contractor_fee = round(amount * (fee_pct / 100.0), 2)
    new_pmt = monthly_payment(amount, new_apr, term_months)
    customer_savings = round(
        (monthly_payment(amount, apr, term_months) - new_pmt) * term_months, 2
    )
    return {
        "fee_pct": fee_pct,
        "contractor_fee": contractor_fee,
        "apr_reduction_points": reduction,
        "new_apr": new_apr,
        "new_monthly_payment": new_pmt,
        "customer_lifetime_savings": customer_savings,
    }
