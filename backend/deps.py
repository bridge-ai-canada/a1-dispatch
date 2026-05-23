"""Shared infrastructure for A1 Field Pro: env, DB, helpers, models, dependencies."""
from dotenv import load_dotenv
from pathlib import Path
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

import os
import asyncio
import logging
import uuid
import bcrypt
import jwt
import requests
import resend
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Literal

from fastapi import HTTPException, Request, Response, Depends
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, EmailStr, Field, field_validator

from roles import has_perm

# -------------------- Env / clients --------------------
mongo_url = os.environ["MONGO_URL"]
db_name = os.environ["DB_NAME"]
JWT_SECRET = os.environ["JWT_SECRET"]
JWT_ALGORITHM = "HS256"

STRIPE_API_KEY = os.environ.get("STRIPE_API_KEY", "sk_test_emergent")
RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "onboarding@resend.dev")
FRONTEND_URL = os.environ.get("FRONTEND_URL", "")
SUPERADMIN_EMAIL = os.environ.get("SUPERADMIN_EMAIL", "")
SUPERADMIN_PASSWORD = os.environ.get("SUPERADMIN_PASSWORD", "")
EMERGENT_KEY = os.environ.get("EMERGENT_LLM_KEY", "")
APP_NAME = os.environ.get("APP_NAME", "a1fieldpro")
STORAGE_URL = "https://integrations.emergentagent.com/objstore/api/v1/storage"

VAPID_PRIVATE_KEY = os.environ.get("VAPID_PRIVATE_KEY", "").replace("\\n", "\n")
VAPID_PUBLIC_KEY = os.environ.get("VAPID_PUBLIC_KEY", "")
VAPID_SUBJECT = os.environ.get("VAPID_SUBJECT", "mailto:admin@a1fieldpro.com")

if RESEND_API_KEY:
    resend.api_key = RESEND_API_KEY

client = AsyncIOMotorClient(mongo_url)
db = client[db_name]

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("a1fieldpro")

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

# -------------------- Storage --------------------
_storage_key: Optional[str] = None

def init_storage() -> Optional[str]:
    global _storage_key
    if _storage_key:
        return _storage_key
    if not EMERGENT_KEY:
        return None
    try:
        r = requests.post(f"{STORAGE_URL}/init", json={"emergent_key": EMERGENT_KEY}, timeout=30)
        r.raise_for_status()
        _storage_key = r.json()["storage_key"]
        return _storage_key
    except Exception as e:
        logger.error(f"Storage init failed: {e}")
        return None

def put_object(path: str, data: bytes, content_type: str) -> dict:
    key = init_storage()
    if not key:
        raise HTTPException(status_code=500, detail="Storage unavailable")
    r = requests.put(f"{STORAGE_URL}/objects/{path}",
        headers={"X-Storage-Key": key, "Content-Type": content_type}, data=data, timeout=120)
    r.raise_for_status()
    return r.json()

def delete_object(path: str) -> bool:
    key = init_storage()
    if not key or not path:
        return False
    try:
        r = requests.delete(f"{STORAGE_URL}/objects/{path}",
            headers={"X-Storage-Key": key}, timeout=30)
        return r.status_code in (200, 204, 404)
    except Exception as e:
        logger.error(f"Storage delete failed for {path}: {e}")
        return False

def get_object(path: str):
    key = init_storage()
    if not key:
        raise HTTPException(status_code=500, detail="Storage unavailable")
    r = requests.get(f"{STORAGE_URL}/objects/{path}",
        headers={"X-Storage-Key": key}, timeout=60)
    r.raise_for_status()
    return r.content, r.headers.get("Content-Type", "application/octet-stream")

# -------------------- Crypto / Tokens --------------------
def hash_password(pw: str) -> str:
    return bcrypt.hashpw(pw.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

def verify_password(pw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False

def create_access_token(user_id: str, company_id: Optional[str], role: str, session_id: str) -> str:
    return jwt.encode({"sub": user_id, "company_id": company_id, "role": role, "sid": session_id,
        "type": "access", "exp": datetime.now(timezone.utc) + timedelta(days=7)},
        JWT_SECRET, algorithm=JWT_ALGORITHM)

def create_pw_reset_token(user_id: str) -> str:
    return jwt.encode({"sub": user_id, "type": "pw_reset",
        "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
        JWT_SECRET, algorithm=JWT_ALGORITHM)

def create_invite_token(user_id: str) -> str:
    return jwt.encode({"sub": user_id, "type": "invite",
        "exp": datetime.now(timezone.utc) + timedelta(days=7)},
        JWT_SECRET, algorithm=JWT_ALGORITHM)

def create_verify_token(user_id: str) -> str:
    return jwt.encode({"sub": user_id, "type": "email_verify",
        "exp": datetime.now(timezone.utc) + timedelta(days=7)},
        JWT_SECRET, algorithm=JWT_ALGORITHM)

def set_auth_cookie(response: Response, token: str):
    response.set_cookie(key="access_token", value=token, httponly=True, secure=True,
        samesite="none", max_age=60 * 60 * 24 * 7, path="/")

def clear_auth_cookie(response: Response):
    response.delete_cookie("access_token", path="/")

# -------------------- Auth dependencies --------------------
async def get_current_user(request: Request) -> dict:
    token = request.cookies.get("access_token")
    if not token:
        ah = request.headers.get("Authorization", "")
        if ah.startswith("Bearer "):
            token = ah[7:]
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Invalid token type")
        user = await db.users.find_one({"id": payload["sub"]},
            {"_id": 0, "password_hash": 0, "mfa_secret": 0})
        if not user or not user.get("active", True):
            raise HTTPException(status_code=401, detail="User not found or inactive")
        sid = payload.get("sid")
        if sid:
            sess = await db.sessions.find_one({"id": sid, "revoked": {"$ne": True}}, {"_id": 0})
            if not sess:
                raise HTTPException(status_code=401, detail="Session revoked")
            user["_session_id"] = sid
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

def require_role(*roles: str):
    async def checker(user: dict = Depends(get_current_user)):
        if user.get("role") not in roles:
            raise HTTPException(status_code=403, detail="Forbidden")
        return user
    return checker

def require_perm(perm: str):
    async def checker(user: dict = Depends(get_current_user)):
        if not has_perm(user.get("role", ""), perm):
            raise HTTPException(status_code=403, detail=f"Missing permission: {perm}")
        return user
    return checker

# -------------------- Email --------------------
async def send_email(to: str, subject: str, html: str, *,
                     actor: Optional[dict] = None, purpose: str = "") -> Optional[str]:
    """Send an email via Resend and (optionally) emit an activity event with delivery status.
    Returns the Resend email id on success, None on failure or when Resend isn't configured.
    """
    email_id: Optional[str] = None
    status: str = "skipped"
    error: str = ""
    if not RESEND_API_KEY:
        logger.warning(f"Resend not configured — skipped email to {to}: {subject}")
    else:
        try:
            params = {"from": SENDER_EMAIL, "to": [to], "subject": subject, "html": html}
            res = await asyncio.to_thread(resend.Emails.send, params)
            email_id = res.get("id") if isinstance(res, dict) else None
            status = "sent" if email_id else "no_id"
        except Exception as e:
            logger.error(f"Email send failed: {e}")
            status = "failed"
            error = f"{type(e).__name__}: {e}"

    if actor is not None:
        meta = {"to": to, "subject": subject, "purpose": purpose, "status": status}
        if email_id:
            meta["email_id"] = email_id
        if error:
            meta["error"] = error[:200]
        try:
            await log_activity(actor, "email.sent", "email", email_id or "", meta)
        except Exception as e:
            logger.error(f"Activity log for email failed: {e}")
    return email_id

def email_layout(title: str, body_html: str, cta_label: str = "", cta_url: str = "") -> str:
    cta = f"""
        <tr><td style="padding:24px 0">
            <a href="{cta_url}" style="background:#DC2626;color:#fff;text-decoration:none;
            padding:14px 28px;font-weight:700;font-family:Helvetica,Arial,sans-serif;
            display:inline-block;letter-spacing:0.02em">{cta_label}</a>
        </td></tr>
    """ if cta_label else ""
    return f"""
    <table cellpadding="0" cellspacing="0" border="0" width="100%" style="background:#f8fafc;padding:32px 0;font-family:Helvetica,Arial,sans-serif;color:#0f172a">
      <tr><td align="center">
        <table cellpadding="0" cellspacing="0" border="0" width="560" style="background:#ffffff;border:1px solid #e2e8f0">
          <tr><td style="background:#1D4ED8;color:#fff;padding:20px 24px;font-size:22px;font-weight:800;letter-spacing:-0.02em">
            A1 Field Pro
          </td></tr>
          <tr><td style="padding:32px 24px">
            <h1 style="margin:0 0 12px;font-size:24px;font-weight:800;letter-spacing:-0.02em">{title}</h1>
            <div style="font-size:15px;line-height:1.6;color:#334155">{body_html}</div>
            {cta}
            <p style="margin-top:24px;font-size:12px;color:#94a3b8">If you didn't expect this email, you can ignore it.</p>
          </td></tr>
          <tr><td style="background:#f1f5f9;padding:14px 24px;font-size:11px;color:#64748b;letter-spacing:0.1em;text-transform:uppercase">
            A1 HVAC N DE-GO · A1 Field Pro
          </td></tr>
        </table>
      </td></tr>
    </table>
    """

# -------------------- Activity / Sessions --------------------
async def log_activity(actor: dict, action: str, target_type: str = "",
                       target_id: str = "", meta: Optional[dict] = None):
    await db.activity.insert_one({
        "id": str(uuid.uuid4()),
        "company_id": actor.get("company_id"),
        "actor_id": actor.get("id"),
        "actor_name": actor.get("name"),
        "actor_role": actor.get("role"),
        "action": action,
        "target_type": target_type,
        "target_id": target_id,
        "meta": meta or {},
        "created_at": now_iso(),
    })

async def create_session(user: dict, request: Request) -> str:
    sid = str(uuid.uuid4())
    await db.sessions.insert_one({
        "id": sid,
        "user_id": user["id"],
        "company_id": user.get("company_id"),
        "user_agent": request.headers.get("User-Agent", ""),
        "ip": request.client.host if request.client else "",
        "created_at": now_iso(),
        "last_seen_at": now_iso(),
        "revoked": False,
    })
    return sid

# -------------------- Pydantic models --------------------
class RegisterIn(BaseModel):
    company_name: str
    industry: str = "HVAC"
    name: str
    email: EmailStr
    password: str

    @field_validator("password")
    @classmethod
    def _strong_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        if not any(c.isalpha() for c in v):
            raise ValueError("Password must contain at least one letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one number")
        return v

class LoginIn(BaseModel):
    email: EmailStr
    password: str
    mfa_code: Optional[str] = None

class ForgotIn(BaseModel):
    email: EmailStr

class ResetIn(BaseModel):
    token: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def _strong_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        if not any(c.isalpha() for c in v):
            raise ValueError("Password must contain at least one letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one number")
        return v

class InviteIn(BaseModel):
    name: str
    email: EmailStr
    role: str

class UserUpdateIn(BaseModel):
    role: Optional[str] = None
    active: Optional[bool] = None
    name: Optional[str] = None

class MfaEnableIn(BaseModel):
    code: str

class MfaDisableIn(BaseModel):
    password: str

class TeamCreateIn(BaseModel):
    name: str
    email: EmailStr
    password: str
    role: Literal["dispatcher", "technician"] = "technician"

class CustomerIn(BaseModel):
    name: str
    phone: Optional[str] = ""
    email: Optional[str] = ""
    address: Optional[str] = ""
    status: Optional[Literal["lead","prospect","active","churned"]] = "active"
    tags: Optional[List[str]] = None
    source: Optional[str] = ""
    notes: Optional[str] = ""

class CustomerUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    status: Optional[Literal["lead","prospect","active","churned"]] = None
    tags: Optional[List[str]] = None
    source: Optional[str] = None
    notes: Optional[str] = None

class PropertyIn(BaseModel):
    address: str
    nickname: Optional[str] = ""
    property_type: Optional[str] = "residential"
    sq_ft: Optional[int] = 0
    year_built: Optional[int] = 0
    notes: Optional[str] = ""

class EquipmentIn(BaseModel):
    property_id: str
    kind: str
    brand: Optional[str] = ""
    model: Optional[str] = ""
    serial: Optional[str] = ""
    install_date: Optional[str] = ""
    warranty_until: Optional[str] = ""
    notes: Optional[str] = ""

class CommunicationIn(BaseModel):
    channel: Literal["call","email","sms","note","system"] = "note"
    direction: Optional[Literal["in","out","internal"]] = "internal"
    summary: str
    body: Optional[str] = ""

_HEX_COLOR_RE = r"^#[0-9A-Fa-f]{6}$"

class BrandingIn(BaseModel):
    primary_color: Optional[str] = Field(default=None, pattern=_HEX_COLOR_RE)
    accent_color: Optional[str] = Field(default=None, pattern=_HEX_COLOR_RE)
    secondary_color: Optional[str] = Field(default=None, pattern=_HEX_COLOR_RE)
    logo_path: Optional[str] = None
    favicon_path: Optional[str] = None
    app_name: Optional[str] = None  # white-label product name
    custom_domain: Optional[str] = None
    support_email: Optional[str] = None
    support_phone: Optional[str] = None
    invoice_footer: Optional[str] = None
    email_from_name: Optional[str] = None
    tagline: Optional[str] = None

    @field_validator("custom_domain")
    @classmethod
    def _norm_domain(cls, v):
        if not v:
            return v
        v = v.strip().lower()
        if v.startswith("http://"):
            v = v[7:]
        if v.startswith("https://"):
            v = v[8:]
        return v.split("/")[0] or None

class JobIn(BaseModel):
    title: str
    description: Optional[str] = ""
    customer_id: Optional[str] = None
    customer_name: Optional[str] = ""
    customer_phone: Optional[str] = ""
    customer_email: Optional[str] = ""
    address: Optional[str] = ""
    job_type: str = "HVAC"
    assigned_to: Optional[str] = None
    scheduled_at: Optional[str] = None
    duration_min: int = 60
    price: float = 0.0
    status: Literal["new_lead", "contacted", "qualified", "quote_sent", "won_bid", "lost_bid", "scheduled_installation", "unscheduled", "on_hold", "in_progress", "completed", "cancelled"] = "unscheduled"
    priority: Literal["low", "normal", "high", "emergency"] = "normal"

class JobUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    assigned_to: Optional[str] = None
    scheduled_at: Optional[str] = None
    duration_min: Optional[int] = None
    price: Optional[float] = None
    status: Optional[Literal["new_lead", "contacted", "qualified", "quote_sent", "won_bid", "lost_bid", "scheduled_installation", "unscheduled", "on_hold", "in_progress", "completed", "cancelled"]] = None
    address: Optional[str] = None
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    priority: Optional[Literal["low", "normal", "high", "emergency"]] = None

_CADENCE_DAYS = {
    "weekly": 7,
    "biweekly": 14,
    "monthly": 30,
    "quarterly": 90,
    "annually": 365,
}

class RecurringJobIn(BaseModel):
    title: str
    description: Optional[str] = ""
    customer_id: Optional[str] = None
    customer_name: Optional[str] = ""
    customer_phone: Optional[str] = ""
    customer_email: Optional[str] = ""
    address: Optional[str] = ""
    job_type: str = "HVAC"
    assigned_to: Optional[str] = None
    duration_min: int = 60
    price: float = 0.0
    cadence: Literal["weekly", "biweekly", "monthly", "quarterly", "annually", "custom"] = "monthly"
    interval_days: Optional[int] = None  # used only when cadence == "custom"
    start_at: Optional[str] = None  # ISO; default = now
    active: bool = True

class RecurringJobUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    customer_id: Optional[str] = None
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    customer_email: Optional[str] = None
    address: Optional[str] = None
    job_type: Optional[str] = None
    assigned_to: Optional[str] = None
    duration_min: Optional[int] = None
    price: Optional[float] = None
    cadence: Optional[Literal["weekly", "biweekly", "monthly", "quarterly", "annually", "custom"]] = None
    interval_days: Optional[int] = None
    active: Optional[bool] = None

class GoogleExchangeIn(BaseModel):
    session_id: str

class CheckoutIn(BaseModel):
    job_id: str
    origin_url: str
