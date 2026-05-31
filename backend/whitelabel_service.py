"""White-label / subscription utilities — plans catalog, defaults, template substitution.

Single source of truth for: subscription plans, default branding, default message
templates, feature gating, and `render_template()` for email + SMS bodies.
"""
import re
from string import Template
from typing import Optional


# -------------------- Subscription plans --------------------
# Keep in sync with the marketing page + Stripe price IDs (when configured).
PLANS = {
    "basic": {
        "key": "basic",
        "name": "Basic",
        "price_usd": 49,
        "interval": "month",
        "seats": 1,
        "features": {
            "ai_assist": False,
            "branches": False,
            "custom_domain": False,
            "franchise": False,
            "api_access": False,
            "white_label": True,
            "sms_reminders": True,
        },
        "tagline": "For solo operators getting started.",
    },
    "team": {
        "key": "team",
        "name": "Team",
        "price_usd": 149,
        "interval": "month",
        "seats": 5,
        "features": {
            "ai_assist": False,
            "branches": False,
            "custom_domain": False,
            "franchise": False,
            "api_access": False,
            "white_label": True,
            "sms_reminders": True,
        },
        "tagline": "Growing crew of up to 5.",
    },
    "business": {
        "key": "business",
        "name": "Business",
        "price_usd": 299,
        "interval": "month",
        "seats": 15,
        "features": {
            "ai_assist": True,
            "branches": True,
            "custom_domain": False,
            "franchise": False,
            "api_access": True,
            "white_label": True,
            "sms_reminders": True,
        },
        "tagline": "AI tooling + multi-branch operations.",
        "featured": True,
    },
    "pro": {
        "key": "pro",
        "name": "Pro",
        "price_usd": 499,
        "interval": "month",
        "seats": 50,
        "features": {
            "ai_assist": True,
            "branches": True,
            "custom_domain": True,
            "franchise": False,
            "api_access": True,
            "white_label": True,
            "sms_reminders": True,
        },
        "tagline": "Scale to 50 seats with custom domain + API.",
    },
    "enterprise": {
        "key": "enterprise",
        "name": "Enterprise",
        "price_usd": 0,  # 0 = contact us for custom pricing
        "custom_price": True,
        "interval": "month",
        "seats": 0,  # 0 = unlimited
        "features": {
            "ai_assist": True,
            "branches": True,
            "custom_domain": True,
            "franchise": True,
            "api_access": True,
            "white_label": True,
            "sms_reminders": True,
        },
        "tagline": "For franchises and large organizations — custom pricing.",
    },
}

DEFAULT_PLAN = "basic"


def plan(key: Optional[str]) -> dict:
    return PLANS.get((key or DEFAULT_PLAN).lower(), PLANS[DEFAULT_PLAN])


def has_feature(plan_key: Optional[str], feature: str) -> bool:
    return bool(plan(plan_key)["features"].get(feature, False))


def seat_limit(plan_key: Optional[str]) -> int:
    """0 means unlimited."""
    return int(plan(plan_key).get("seats", 0))


# -------------------- Default branding --------------------
DEFAULT_BRANDING = {
    "primary_color": "#1D4ED8",
    "accent_color": "#DC2626",
    "secondary_color": "#0F172A",
    "logo_path": None,
    "favicon_path": None,
    "app_name": None,           # falls back to company.name when None
    "custom_domain": None,
    "support_email": None,
    "support_phone": None,
    "invoice_footer": "Thank you for your business.",
    "email_from_name": None,    # falls back to company.name
    "tagline": "",
}


# -------------------- Default message templates --------------------
# `kind` is "email" or "sms". `event` is the system trigger.
# Variables use $name or ${name} (string.Template).
DEFAULT_TEMPLATES = [
    {
        "key": "welcome_email",
        "kind": "email",
        "event": "customer_welcome",
        "subject": "Welcome to $company_name",
        "body": (
            "Hi $customer_name,\n\n"
            "Thanks for choosing $company_name. We've created your customer portal "
            "so you can track jobs, invoices, and quotes in one place.\n\n"
            "— The $company_name team"
        ),
    },
    {
        "key": "job_scheduled_email",
        "kind": "email",
        "event": "job_scheduled",
        "subject": "Your appointment is booked — $job_title",
        "body": (
            "Hi $customer_name,\n\n"
            "Good news — we've scheduled $job_title on $job_scheduled_at.\n"
            "Address: $job_address\n\n"
            "If you need to reschedule, reply to this email or call $support_phone.\n\n"
            "— $company_name"
        ),
    },
    {
        "key": "invoice_sent_email",
        "kind": "email",
        "event": "invoice_sent",
        "subject": "Invoice $invoice_number from $company_name",
        "body": (
            "Hi $customer_name,\n\n"
            "Your invoice for $job_title is ready. Total due: $invoice_total.\n\n"
            "Pay securely: $invoice_url\n\n"
            "— $company_name"
        ),
    },
    {
        "key": "estimate_sent_email",
        "kind": "email",
        "event": "estimate_sent",
        "subject": "Your proposal from $company_name",
        "body": (
            "Hi $customer_name,\n\n"
            "Your proposal $estimate_number is ready for review.\n"
            "View, compare options, and approve online: $estimate_url\n\n"
            "Questions? Reply to this email or call $support_phone.\n\n"
            "— $company_name"
        ),
    },
    {
        "key": "job_reminder_sms",
        "kind": "sms",
        "event": "job_reminder",
        "subject": "",
        "body": "$company_name: Reminder — $job_title on $job_scheduled_at. Reply STOP to unsubscribe.",
    },
    {
        "key": "tech_otw_sms",
        "kind": "sms",
        "event": "tech_on_the_way",
        "subject": "",
        "body": "$company_name: Your technician is on the way — ETA $eta_minutes min. Track: $tracking_url",
    },
    {
        "key": "invoice_due_sms",
        "kind": "sms",
        "event": "invoice_due",
        "subject": "",
        "body": "$company_name: Invoice $invoice_number for $invoice_total is due. Pay: $invoice_url",
    },
]


# Variables the template editor exposes (for the variable-picker UI).
TEMPLATE_VARIABLES = [
    "company_name", "company_phone", "support_email", "support_phone",
    "customer_name", "customer_email", "customer_phone",
    "job_title", "job_scheduled_at", "job_address", "job_url",
    "invoice_number", "invoice_total", "invoice_url",
    "estimate_number", "estimate_url",
    "eta_minutes", "tracking_url", "branch_name",
]


_VAR_RE = re.compile(r"\$\{?([a-z_][a-z0-9_]*)\}?", re.IGNORECASE)


def render_template(body: str, ctx: dict) -> str:
    """Substitute $var / ${var}. Missing variables are left as `[missing]`."""
    if not body:
        return ""
    safe = {k: ("" if v is None else str(v)) for k, v in (ctx or {}).items()}
    try:
        return Template(body).safe_substitute(safe)
    except Exception:
        return body


def find_variables(body: str) -> list:
    """Return list of variables referenced in template body (for editor hints)."""
    if not body:
        return []
    seen = []
    for m in _VAR_RE.finditer(body):
        v = m.group(1).lower()
        if v not in seen:
            seen.append(v)
    return seen
