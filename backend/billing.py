"""Pydantic models + math helpers for Estimates and Invoices."""
from typing import List, Optional, Literal
from pydantic import BaseModel, Field


# -------------------- Line items / shared --------------------
class LineItem(BaseModel):
    id: Optional[str] = None
    description: str
    qty: float = 1.0
    unit_price: float = 0.0
    taxable: bool = True
    kind: Literal["service", "material", "labor", "fee", "other"] = "service"


class Addon(BaseModel):
    id: Optional[str] = None
    description: str
    qty: float = 1.0
    unit_price: float = 0.0
    taxable: bool = True
    selected: bool = False  # toggled by customer in portal


class FinancingConfig(BaseModel):
    enabled: bool = False
    apr: float = 9.99            # annual percentage rate %
    term_months: int = 24
    apply_url: Optional[str] = ""
    provider: Optional[str] = "wisetack"


class Discount(BaseModel):
    type: Literal["percent", "fixed"] = "percent"
    value: float = 0.0


class Deposit(BaseModel):
    type: Literal["percent", "fixed", "none"] = "none"
    value: float = 0.0


# -------------------- Estimate --------------------
class EstimateTier(BaseModel):
    key: Literal["good", "better", "best"]
    name: str
    summary: Optional[str] = ""
    line_items: List[LineItem] = Field(default_factory=list)
    addons: List[Addon] = Field(default_factory=list)
    featured: bool = False
    cta_label: Optional[str] = "Approve this option"


class EstimateIn(BaseModel):
    title: str
    intro: Optional[str] = ""
    customer_id: Optional[str] = None
    customer_name: Optional[str] = ""
    customer_email: Optional[str] = ""
    customer_phone: Optional[str] = ""
    address: Optional[str] = ""
    job_id: Optional[str] = None
    tiers: List[EstimateTier] = Field(default_factory=list)
    tax_rate: float = 0.0  # percent
    discount: Discount = Field(default_factory=Discount)
    deposit: Deposit = Field(default_factory=Deposit)
    financing: FinancingConfig = Field(default_factory=FinancingConfig)
    terms: Optional[str] = ""
    expires_in_days: int = 30


class EstimateUpdate(BaseModel):
    title: Optional[str] = None
    intro: Optional[str] = None
    customer_id: Optional[str] = None
    customer_name: Optional[str] = None
    customer_email: Optional[str] = None
    customer_phone: Optional[str] = None
    address: Optional[str] = None
    job_id: Optional[str] = None
    tiers: Optional[List[EstimateTier]] = None
    tax_rate: Optional[float] = None
    discount: Optional[Discount] = None
    deposit: Optional[Deposit] = None
    financing: Optional[FinancingConfig] = None
    terms: Optional[str] = None
    expires_in_days: Optional[int] = None


class ApproveIn(BaseModel):
    selected_tier: Literal["good", "better", "best"]
    signer_name: str
    signature_base64: str
    selected_addons: List[str] = Field(default_factory=list)  # addon ids


class DeclineIn(BaseModel):
    reason: Optional[str] = ""


# -------------------- Invoice --------------------
class InvoiceIn(BaseModel):
    title: Optional[str] = ""
    customer_id: Optional[str] = None
    customer_name: Optional[str] = ""
    customer_email: Optional[str] = ""
    customer_phone: Optional[str] = ""
    address: Optional[str] = ""
    job_id: Optional[str] = None
    estimate_id: Optional[str] = None
    line_items: List[LineItem] = Field(default_factory=list)
    tax_rate: float = 0.0
    discount: Discount = Field(default_factory=Discount)
    deposit: Deposit = Field(default_factory=Deposit)
    due_in_days: int = 14
    terms: Optional[str] = ""
    notes: Optional[str] = ""


class InvoiceUpdate(BaseModel):
    title: Optional[str] = None
    customer_id: Optional[str] = None
    customer_name: Optional[str] = None
    customer_email: Optional[str] = None
    customer_phone: Optional[str] = None
    address: Optional[str] = None
    job_id: Optional[str] = None
    line_items: Optional[List[LineItem]] = None
    tax_rate: Optional[float] = None
    discount: Optional[Discount] = None
    deposit: Optional[Deposit] = None
    due_in_days: Optional[int] = None
    terms: Optional[str] = None
    notes: Optional[str] = None


# -------------------- Templates --------------------
class TemplateIn(BaseModel):
    name: str
    kind: Literal["estimate", "invoice"] = "estimate"
    description: Optional[str] = ""
    tiers: Optional[List[EstimateTier]] = None  # for estimate templates
    line_items: Optional[List[LineItem]] = None  # for invoice templates
    tax_rate: float = 0.0
    terms: Optional[str] = ""


class TemplateUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    tiers: Optional[List[EstimateTier]] = None
    line_items: Optional[List[LineItem]] = None
    tax_rate: Optional[float] = None
    terms: Optional[str] = None


class CheckoutPortalIn(BaseModel):
    origin_url: str
    pay_type: Literal["full", "deposit", "balance"] = "full"
    amount: Optional[float] = None  # optional override for partial


# -------------------- Math helpers --------------------
def _items_subtotal(items: List[dict]) -> float:
    return round(sum(float(i.get("qty", 0)) * float(i.get("unit_price", 0)) for i in items), 2)


def _items_taxable_subtotal(items: List[dict]) -> float:
    return round(sum(
        float(i.get("qty", 0)) * float(i.get("unit_price", 0))
        for i in items if i.get("taxable", True)
    ), 2)


def compute_totals(
    line_items: List[dict],
    *,
    tax_rate: float = 0.0,
    discount: Optional[dict] = None,
    deposit: Optional[dict] = None,
) -> dict:
    """Apply discount first (proportionally), then tax on remaining taxable amount.
    Returns: subtotal, discount_amount, taxable_amount, tax_amount, total, deposit_amount.
    """
    subtotal = _items_subtotal(line_items)
    taxable = _items_taxable_subtotal(line_items)

    discount = discount or {}
    dtype = discount.get("type", "percent")
    dval = float(discount.get("value", 0) or 0)
    if dtype == "percent":
        discount_amount = round(subtotal * (dval / 100.0), 2)
    else:
        discount_amount = round(min(dval, subtotal), 2)

    # Proportionally reduce taxable amount by the same ratio as the discount applies to subtotal
    if subtotal > 0 and discount_amount > 0:
        ratio = (subtotal - discount_amount) / subtotal
        taxable_after = round(taxable * ratio, 2)
    else:
        taxable_after = taxable

    tax_amount = round(taxable_after * (float(tax_rate or 0) / 100.0), 2)
    total = round(subtotal - discount_amount + tax_amount, 2)

    deposit = deposit or {}
    dep_type = deposit.get("type", "none")
    dep_val = float(deposit.get("value", 0) or 0)
    if dep_type == "percent":
        deposit_amount = round(total * (dep_val / 100.0), 2)
    elif dep_type == "fixed":
        deposit_amount = round(min(dep_val, total), 2)
    else:
        deposit_amount = 0.0

    return {
        "subtotal": subtotal,
        "discount_amount": discount_amount,
        "taxable_amount": taxable_after,
        "tax_amount": tax_amount,
        "total": total,
        "deposit_amount": deposit_amount,
    }


def tier_totals(tier: dict, *, tax_rate: float, discount: dict, deposit: dict) -> dict:
    """Compute totals for an estimate tier including selected addons."""
    items = list(tier.get("line_items") or [])
    # Include addons if selected (estimate level), but during builder/preview we show
    # all-addons-off subtotal. Customer can toggle in approval flow.
    selected_addons = [a for a in (tier.get("addons") or []) if a.get("selected")]
    return compute_totals(items + selected_addons, tax_rate=tax_rate,
                          discount=discount, deposit=deposit)


def monthly_payment(principal: float, apr: float, term_months: int) -> float:
    """Simple amortized monthly payment. Returns 0 if invalid."""
    if principal <= 0 or term_months <= 0:
        return 0.0
    if apr <= 0:
        return round(principal / term_months, 2)
    r = (apr / 100.0) / 12.0
    n = term_months
    pmt = principal * (r * (1 + r) ** n) / ((1 + r) ** n - 1)
    return round(pmt, 2)
