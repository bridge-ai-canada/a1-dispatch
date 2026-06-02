"""Catalog of supported third-party integrations.

A single source of truth that drives:
- Integrations Hub UI (cards + connect buttons)
- OAuth start/callback flows (which scopes, which URLs)
- Webhook signature verifier dispatch
- Background sync scheduler
"""
import os
from typing import Literal

AuthMode = Literal["oauth2", "api_key", "server_to_server", "server_key", "api_token"]

# Some providers we already wire elsewhere — listed here so the UI shows status.
PROVIDERS: dict[str, dict] = {
    # Accounting / sync
    "quickbooks": {
        "name": "QuickBooks Online",
        "category": "accounting",
        "auth_mode": "oauth2",
        "description": "Two-way sync customers, invoices & payments.",
        "icon": "qbo",
        "color": "#2CA01C",
        "scopes": "com.intuit.quickbooks.accounting com.intuit.quickbooks.payment openid profile email",
        "auth_url": "https://appcenter.intuit.com/connect/oauth2",
        "token_url": "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer",
        "env_client_id": "QUICKBOOKS_CLIENT_ID",
        "env_client_secret": "QUICKBOOKS_CLIENT_SECRET",
        "env_webhook_secret": "QUICKBOOKS_WEBHOOK_VERIFIER",
        "supports_webhooks": True,
        "supports_sync": True,
        "sync_interval_minutes": 30,
    },
    # Payments
    "helcim": {
        "name": "Helcim",
        "category": "payments",
        "auth_mode": "api_token",
        "description": "Charge cards & process payments with tokenized cards.",
        "icon": "helcim",
        "color": "#001F5C",
        "env_api_key": "HELCIM_API_KEY",
        "env_webhook_secret": "HELCIM_WEBHOOK_VERIFIER",
        "supports_webhooks": True,
        "supports_sync": False,
        "fields": [
            {"key": "api_token", "label": "API Token", "secret": True, "required": True},
            {"key": "environment", "label": "Environment", "type": "select",
             "options": ["sandbox", "production"], "default": "sandbox"},
        ],
    },
    "stripe": {
        "name": "Stripe",
        "category": "payments",
        "auth_mode": "api_key",
        "description": "Subscriptions, one-time charges & customer portal.",
        "icon": "stripe",
        "color": "#635BFF",
        "env_api_key": "STRIPE_API_KEY",
        "env_webhook_secret": "STRIPE_WEBHOOK_SECRET",
        "supports_webhooks": True,
        "supports_sync": False,
        "always_on": True,  # built into platform
        "fields": [
            {"key": "publishable_key", "label": "Publishable key", "required": False},
            {"key": "secret_key", "label": "Secret key (sk_…)", "secret": True, "required": True},
            {"key": "webhook_secret", "label": "Webhook signing secret (whsec_…)", "secret": True},
        ],
    },
    # Messaging
    "twilio": {
        "name": "Twilio",
        "category": "messaging",
        "auth_mode": "api_token",
        "description": "SMS reminders & 'Finance this job' texts.",
        "icon": "twilio",
        "color": "#F22F46",
        "env_api_key": "TWILIO_AUTH_TOKEN",
        "supports_webhooks": True,
        "supports_sync": False,
        "always_on": True,
        "fields": [
            {"key": "account_sid", "label": "Account SID", "required": True},
            {"key": "auth_token", "label": "Auth Token", "secret": True, "required": True},
            {"key": "from_number", "label": "From phone number", "required": True},
        ],
    },
    # Calendars
    "google_calendar": {
        "name": "Google Calendar",
        "category": "calendar",
        "auth_mode": "oauth2",
        "description": "Two-way sync jobs ↔ Calendar events.",
        "icon": "gcal",
        "color": "#4285F4",
        "scopes": "https://www.googleapis.com/auth/calendar.events offline_access openid email",
        "auth_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url": "https://oauth2.googleapis.com/token",
        "env_client_id": "GOOGLE_CLIENT_ID",
        "env_client_secret": "GOOGLE_CLIENT_SECRET",
        "extra_params": {"access_type": "offline", "prompt": "consent",
                         "include_granted_scopes": "true"},
        "supports_webhooks": True,
        "supports_sync": True,
        "sync_interval_minutes": 15,
    },
    "outlook_calendar": {
        "name": "Outlook Calendar",
        "category": "calendar",
        "auth_mode": "oauth2",
        "description": "Sync jobs with Microsoft 365 calendars.",
        "icon": "outlook",
        "color": "#0078D4",
        "scopes": "offline_access Calendars.ReadWrite User.Read",
        "auth_url": "https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
        "token_url": "https://login.microsoftonline.com/common/oauth2/v2.0/token",
        "env_client_id": "MS_GRAPH_CLIENT_ID",
        "env_client_secret": "MS_GRAPH_CLIENT_SECRET",
        "extra_params": {"response_mode": "query"},
        "supports_webhooks": True,
        "supports_sync": True,
        "sync_interval_minutes": 15,
    },
    # Email
    "gmail": {
        "name": "Gmail",
        "category": "email",
        "auth_mode": "oauth2",
        "description": "Send appointment confirmations from your Gmail.",
        "icon": "gmail",
        "color": "#EA4335",
        "scopes": "https://www.googleapis.com/auth/gmail.send openid email",
        "auth_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url": "https://oauth2.googleapis.com/token",
        "env_client_id": "GOOGLE_CLIENT_ID",
        "env_client_secret": "GOOGLE_CLIENT_SECRET",
        "extra_params": {"access_type": "offline", "prompt": "consent"},
        "supports_webhooks": False,
        "supports_sync": False,
    },
    # Video
    "zoom": {
        "name": "Zoom",
        "category": "video",
        "auth_mode": "server_to_server",
        "description": "Auto-create Zoom links for virtual estimates.",
        "icon": "zoom",
        "color": "#2D8CFF",
        "token_url": "https://zoom.us/oauth/token",
        "env_client_id": "ZOOM_CLIENT_ID",
        "env_client_secret": "ZOOM_CLIENT_SECRET",
        "supports_webhooks": True,
        "supports_sync": False,
        "fields": [
            {"key": "account_id", "label": "Zoom Account ID", "required": True},
            {"key": "client_id", "label": "Client ID", "required": True},
            {"key": "client_secret", "label": "Client Secret", "secret": True, "required": True},
        ],
    },
    # Maps
    "google_maps": {
        "name": "Google Maps",
        "category": "maps",
        "auth_mode": "server_key",
        "description": "Distance Matrix + Places autocomplete.",
        "icon": "gmaps",
        "color": "#34A853",
        "env_api_key": "GOOGLE_MAPS_SERVER_KEY",
        "supports_webhooks": False,
        "supports_sync": False,
        "fields": [
            {"key": "server_key", "label": "Server API key", "secret": True, "required": True},
            {"key": "browser_key", "label": "Browser key (for Places autocomplete)"},
        ],
    },
}

ORDER = [
    "quickbooks", "helcim", "stripe", "twilio",
    "google_calendar", "outlook_calendar", "gmail", "zoom", "google_maps",
]


def get(provider: str) -> dict:
    if provider not in PROVIDERS:
        raise KeyError(f"unknown provider: {provider}")
    return PROVIDERS[provider]


def public_catalog() -> list[dict]:
    """Catalog returned to the frontend — strips internal fields like env names."""
    out = []
    for key in ORDER:
        p = PROVIDERS[key]
        out.append({
            "key": key,
            "name": p["name"],
            "category": p["category"],
            "auth_mode": p["auth_mode"],
            "description": p["description"],
            "icon": p["icon"],
            "color": p["color"],
            "supports_webhooks": p.get("supports_webhooks", False),
            "supports_sync": p.get("supports_sync", False),
            "fields": p.get("fields", []),
            "always_on": p.get("always_on", False),
            # Tell the UI whether the global env-level creds are configured so we
            # can pre-flight the OAuth button instead of failing on click.
            "platform_configured": _platform_configured(p),
        })
    return out


def _platform_configured(p: dict) -> bool:
    """Check if the platform-level OAuth client / API key is set in env."""
    if p.get("env_client_id"):
        return bool(os.environ.get(p["env_client_id"]) and
                    os.environ.get(p.get("env_client_secret", "")))
    if p.get("env_api_key"):
        return bool(os.environ.get(p["env_api_key"]))
    return p["auth_mode"] in ("api_token", "api_key", "server_key")  # tenant supplies creds
