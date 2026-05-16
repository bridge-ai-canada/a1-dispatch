from dotenv import load_dotenv
from pathlib import Path
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

import os
import io
import uuid
import base64
import asyncio
import logging
import secrets as pysecrets
import bcrypt
import jwt
import pyotp
import qrcode
import requests
import resend
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Literal

from fastapi import FastAPI, APIRouter, HTTPException, Request, Response, Depends, UploadFile, File, Query
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field, EmailStr
from emergentintegrations.payments.stripe.checkout import (
    StripeCheckout, CheckoutSessionRequest,
)
from roles import ROLES, ROLE_LABELS, PERMISSIONS, INVITE_ALLOWED, has_perm

# -------------------- Storage --------------------
STORAGE_URL = "https://integrations.emergentagent.com/objstore/api/v1/storage"
EMERGENT_KEY = os.environ.get("EMERGENT_LLM_KEY", "")
APP_NAME = os.environ.get("APP_NAME", "a1fieldpro")
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
        logging.error(f"Storage init failed: {e}")
        return None

def put_object(path: str, data: bytes, content_type: str) -> dict:
    key = init_storage()
    if not key:
        raise HTTPException(status_code=500, detail="Storage unavailable")
    r = requests.put(
        f"{STORAGE_URL}/objects/{path}",
        headers={"X-Storage-Key": key, "Content-Type": content_type},
        data=data, timeout=120,
    )
    r.raise_for_status()
    return r.json()

def get_object(path: str):
    key = init_storage()
    if not key:
        raise HTTPException(status_code=500, detail="Storage unavailable")
    r = requests.get(
        f"{STORAGE_URL}/objects/{path}",
        headers={"X-Storage-Key": key}, timeout=60,
    )
    r.raise_for_status()
    return r.content, r.headers.get("Content-Type", "application/octet-stream")

# -------------------- Config --------------------
mongo_url = os.environ["MONGO_URL"]
db_name = os.environ["DB_NAME"]
JWT_SECRET = os.environ["JWT_SECRET"]
STRIPE_API_KEY = os.environ.get("STRIPE_API_KEY", "sk_test_emergent")
RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "onboarding@resend.dev")
FRONTEND_URL = os.environ.get("FRONTEND_URL", "")
SUPERADMIN_EMAIL = os.environ.get("SUPERADMIN_EMAIL", "")
SUPERADMIN_PASSWORD = os.environ.get("SUPERADMIN_PASSWORD", "")
JWT_ALGORITHM = "HS256"

if RESEND_API_KEY:
    resend.api_key = RESEND_API_KEY

client = AsyncIOMotorClient(mongo_url)
db = client[db_name]

app = FastAPI(title="A1 Field Pro API")
api = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("a1fieldpro")

# -------------------- Helpers --------------------
def hash_password(pw: str) -> str:
    return bcrypt.hashpw(pw.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

def verify_password(pw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False

def create_access_token(user_id: str, company_id: Optional[str], role: str, session_id: str) -> str:
    payload = {
        "sub": user_id,
        "company_id": company_id,
        "role": role,
        "sid": session_id,
        "type": "access",
        "exp": datetime.now(timezone.utc) + timedelta(days=7),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def create_pw_reset_token(user_id: str) -> str:
    return jwt.encode({
        "sub": user_id, "type": "pw_reset",
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
    }, JWT_SECRET, algorithm=JWT_ALGORITHM)

def create_invite_token(user_id: str) -> str:
    return jwt.encode({
        "sub": user_id, "type": "invite",
        "exp": datetime.now(timezone.utc) + timedelta(days=7),
    }, JWT_SECRET, algorithm=JWT_ALGORITHM)

def create_verify_token(user_id: str) -> str:
    return jwt.encode({
        "sub": user_id, "type": "email_verify",
        "exp": datetime.now(timezone.utc) + timedelta(days=7),
    }, JWT_SECRET, algorithm=JWT_ALGORITHM)

def set_auth_cookie(response: Response, token: str):
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=True,
        samesite="none",
        max_age=60 * 60 * 24 * 7,
        path="/",
    )

def clear_auth_cookie(response: Response):
    response.delete_cookie("access_token", path="/")

async def get_current_user(request: Request) -> dict:
    token = request.cookies.get("access_token")
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Invalid token type")
        user = await db.users.find_one({"id": payload["sub"]}, {"_id": 0, "password_hash": 0, "mfa_secret": 0})
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
async def send_email(to: str, subject: str, html: str) -> Optional[str]:
    if not RESEND_API_KEY:
        logger.warning(f"Resend not configured — skipped email to {to}: {subject}")
        return None
    try:
        params = {"from": SENDER_EMAIL, "to": [to], "subject": subject, "html": html}
        res = await asyncio.to_thread(resend.Emails.send, params)
        return res.get("id") if isinstance(res, dict) else None
    except Exception as e:
        logger.error(f"Email send failed: {e}")
        return None

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

# -------------------- Activity & Sessions --------------------
async def log_activity(actor: dict, action: str, target_type: str = "", target_id: str = "", meta: Optional[dict] = None):
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

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

# -------------------- Models --------------------
class RegisterIn(BaseModel):
    company_name: str
    industry: str = "HVAC"
    name: str
    email: EmailStr
    password: str

class LoginIn(BaseModel):
    email: EmailStr
    password: str
    mfa_code: Optional[str] = None

class ForgotIn(BaseModel):
    email: EmailStr

class ResetIn(BaseModel):
    token: str
    new_password: str

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

class UserOut(BaseModel):
    id: str
    company_id: str
    name: str
    email: EmailStr
    role: str
    created_at: str

class CompanyOut(BaseModel):
    id: str
    name: str
    industry: str
    created_at: str

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

class BrandingIn(BaseModel):
    primary_color: Optional[str] = None
    accent_color: Optional[str] = None
    logo_path: Optional[str] = None


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
    scheduled_at: Optional[str] = None  # ISO
    duration_min: int = 60
    price: float = 0.0
    status: Literal["unscheduled", "scheduled", "in_progress", "completed", "cancelled"] = "unscheduled"

class GoogleExchangeIn(BaseModel):
    session_id: str

class JobUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    assigned_to: Optional[str] = None
    scheduled_at: Optional[str] = None
    duration_min: Optional[int] = None
    price: Optional[float] = None
    status: Optional[str] = None
    address: Optional[str] = None
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None

class CheckoutIn(BaseModel):
    job_id: str
    origin_url: str

# -------------------- Auth Routes --------------------
@api.post("/auth/register")
async def register(body: RegisterIn, request: Request, response: Response):
    email = body.email.lower().strip()
    existing = await db.users.find_one({"email": email})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    company_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    now = now_iso()
    await db.companies.insert_one({
        "id": company_id,
        "name": body.company_name,
        "industry": body.industry,
        "owner_id": user_id,
        "created_at": now,
    })
    user_doc = {
        "id": user_id,
        "company_id": company_id,
        "name": body.name,
        "email": email,
        "password_hash": hash_password(body.password),
        "role": "owner",
        "active": True,
        "mfa_enabled": False,
        "mfa_secret": None,
        "email_verified": False,
        "created_at": now,
    }
    await db.users.insert_one(user_doc)
    sid = await create_session(user_doc, request)
    token = create_access_token(user_id, company_id, "owner", sid)
    set_auth_cookie(response, token)
    user_out = {k: v for k, v in user_doc.items() if k not in {"password_hash", "mfa_secret", "_id"}}
    await log_activity(user_out, "company.created", "company", company_id)
    return {"user": user_out, "token": token}

@api.post("/auth/login")
async def login(body: LoginIn, request: Request, response: Response):
    email = body.email.lower().strip()
    user = await db.users.find_one({"email": email})
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not user.get("active", True):
        raise HTTPException(status_code=403, detail="Account deactivated")
    if user.get("mfa_enabled"):
        code = (body.mfa_code or "").strip()
        if not code:
            raise HTTPException(status_code=401, detail="mfa_required")
        if not pyotp.TOTP(user["mfa_secret"]).verify(code, valid_window=1):
            raise HTTPException(status_code=401, detail="Invalid MFA code")
    sid = await create_session(user, request)
    token = create_access_token(user["id"], user.get("company_id"), user["role"], sid)
    set_auth_cookie(response, token)
    user.pop("password_hash", None); user.pop("mfa_secret", None); user.pop("_id", None)
    await log_activity(user, "auth.login")
    return {"user": user, "token": token}

@api.post("/auth/logout")
async def logout(request: Request, response: Response):
    token = request.cookies.get("access_token")
    if token:
        try:
            p = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            sid = p.get("sid")
            if sid:
                await db.sessions.update_one({"id": sid}, {"$set": {"revoked": True, "revoked_at": now_iso()}})
        except Exception:
            pass
    clear_auth_cookie(response)
    return {"ok": True}

@api.get("/auth/me")
async def me(user: dict = Depends(get_current_user)):
    company = await db.companies.find_one({"id": user["company_id"]}, {"_id": 0}) if user.get("company_id") else None
    return {"user": user, "company": company, "permissions": PERMISSIONS.get(user["role"], [])}

@api.post("/auth/verify")
async def verify_email(token: str = Query(...)):
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "email_verify":
            raise HTTPException(status_code=400, detail="Invalid token")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=400, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=400, detail="Invalid token")
    res = await db.users.update_one({"id": payload["sub"]}, {"$set": {"email_verified": True}})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    return {"ok": True}

@api.post("/auth/verify/resend")
async def verify_resend(user: dict = Depends(get_current_user)):
    if user.get("email_verified"):
        return {"ok": True, "already_verified": True}
    verify_url = f"{FRONTEND_URL}/verify?token={create_verify_token(user['id'])}"
    email_id = await send_email(
        user["email"], "Verify your A1 Field Pro email",
        email_layout("Verify your email",
            f"<p>Hi {user['name']}, please verify this email so you can receive invoices and booking confirmations.</p>",
            "Verify email", verify_url),
    )
    return {"ok": True, "verify_url": verify_url, "email_sent": bool(email_id)}

@api.post("/auth/google/exchange")
async def google_exchange(body: GoogleExchangeIn, request: Request, response: Response):
    try:
        r = requests.get(
            "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data",
            headers={"X-Session-ID": body.session_id}, timeout=15,
        )
        r.raise_for_status()
        info = r.json()
    except Exception as e:
        logger.error(f"Google session-data failed: {e}")
        raise HTTPException(status_code=400, detail="Could not verify Google session")
    email = (info.get("email") or "").lower().strip()
    if not email:
        raise HTTPException(status_code=400, detail="Google did not return an email")
    user = await db.users.find_one({"email": email})
    now = now_iso()
    if not user:
        # New Google sign-up — create as customer with no company.
        uid = str(uuid.uuid4())
        new_user = {
            "id": uid, "company_id": None,
            "name": info.get("name") or email.split("@")[0],
            "email": email,
            "password_hash": hash_password(pysecrets.token_urlsafe(16)),  # random; user uses Google
            "role": "customer", "active": True,
            "mfa_enabled": False, "mfa_secret": None,
            "email_verified": True, "google_linked": True,
            "picture": info.get("picture") or "",
            "created_at": now,
        }
        await db.users.insert_one(new_user)
        new_user.pop("_id", None)
        user = new_user
        await log_activity(user, "auth.google.signup")
    else:
        await db.users.update_one(
            {"id": user["id"]},
            {"$set": {"google_linked": True, "email_verified": True,
                      "picture": info.get("picture") or user.get("picture", "")}},
        )
        user = await db.users.find_one({"id": user["id"]})
    if not user.get("active", True):
        raise HTTPException(status_code=403, detail="Account deactivated")
    # MFA still applies for non-customer roles
    if user.get("mfa_enabled"):
        # Sign them in without a fresh-cookie until they verify the TOTP step on /login
        raise HTTPException(status_code=401, detail="mfa_required")
    sid = await create_session(user, request)
    token = create_access_token(user["id"], user.get("company_id"), user["role"], sid)
    set_auth_cookie(response, token)
    user.pop("password_hash", None); user.pop("mfa_secret", None); user.pop("_id", None)
    await log_activity(user, "auth.google.login")
    return {"user": user, "token": token}

# -------------------- Password reset --------------------
@api.post("/auth/forgot")
async def forgot(body: ForgotIn):
    email = body.email.lower().strip()
    user = await db.users.find_one({"email": email}, {"_id": 0})
    if user:
        token = create_pw_reset_token(user["id"])
        reset_url = f"{FRONTEND_URL}/reset?token={token}"
        await send_email(
            email,
            "Reset your A1 Field Pro password",
            email_layout(
                "Reset your password",
                f"<p>Hi {user.get('name','there')}, we received a request to reset your password. This link expires in 1 hour.</p>",
                "Reset password", reset_url,
            ),
        )
        return {"ok": True, "reset_url": reset_url}  # url shown in response for owner-driven flow
    return {"ok": True}  # do not reveal

@api.post("/auth/reset")
async def reset(body: ResetIn):
    try:
        payload = jwt.decode(body.token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "pw_reset":
            raise HTTPException(status_code=400, detail="Invalid token")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=400, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=400, detail="Invalid token")
    if len(body.new_password) < 6:
        raise HTTPException(status_code=400, detail="Password too short")
    result = await db.users.update_one(
        {"id": payload["sub"]}, {"$set": {"password_hash": hash_password(body.new_password)}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=400, detail="User not found")
    # invalidate all sessions
    await db.sessions.update_many({"user_id": payload["sub"]}, {"$set": {"revoked": True}})
    return {"ok": True}

# -------------------- MFA --------------------
def _qr_data_url(otpauth_url: str) -> str:
    img = qrcode.make(otpauth_url)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")

@api.post("/auth/mfa/setup")
async def mfa_setup(user: dict = Depends(get_current_user)):
    secret = pyotp.random_base32()
    otpauth = pyotp.totp.TOTP(secret).provisioning_uri(name=user["email"], issuer_name="A1 Field Pro")
    await db.users.update_one(
        {"id": user["id"]}, {"$set": {"mfa_secret": secret, "mfa_enabled": False}}
    )
    return {"secret": secret, "otpauth_url": otpauth, "qr_data_url": _qr_data_url(otpauth)}

@api.post("/auth/mfa/enable")
async def mfa_enable(body: MfaEnableIn, user: dict = Depends(get_current_user)):
    u = await db.users.find_one({"id": user["id"]})
    if not u or not u.get("mfa_secret"):
        raise HTTPException(status_code=400, detail="MFA setup not started")
    if not pyotp.TOTP(u["mfa_secret"]).verify(body.code.strip(), valid_window=1):
        raise HTTPException(status_code=400, detail="Invalid code")
    await db.users.update_one({"id": user["id"]}, {"$set": {"mfa_enabled": True}})
    await log_activity(user, "mfa.enabled")
    return {"ok": True}

@api.post("/auth/mfa/disable")
async def mfa_disable(body: MfaDisableIn, user: dict = Depends(get_current_user)):
    u = await db.users.find_one({"id": user["id"]})
    if not verify_password(body.password, u["password_hash"]):
        raise HTTPException(status_code=401, detail="Wrong password")
    await db.users.update_one(
        {"id": user["id"]}, {"$set": {"mfa_enabled": False, "mfa_secret": None}}
    )
    await log_activity(user, "mfa.disabled")
    return {"ok": True}

# -------------------- Sessions --------------------
@api.get("/sessions")
async def list_sessions(user: dict = Depends(get_current_user)):
    items = await db.sessions.find(
        {"user_id": user["id"], "revoked": {"$ne": True}}, {"_id": 0}
    ).sort("created_at", -1).to_list(50)
    for s in items:
        s["current"] = s["id"] == user.get("_session_id")
    return items

@api.delete("/sessions/{session_id}")
async def revoke_session(session_id: str, user: dict = Depends(get_current_user)):
    await db.sessions.update_one(
        {"id": session_id, "user_id": user["id"]},
        {"$set": {"revoked": True, "revoked_at": now_iso()}},
    )
    return {"ok": True}

# -------------------- Activity --------------------
@api.get("/activity")
async def activity_feed(
    user: dict = Depends(require_perm("activity.read")),
    limit: int = 50, skip: int = 0, action: Optional[str] = None,
):
    q = {}
    if user["role"] != "super_admin":
        q["company_id"] = user["company_id"]
    if action:
        q["action"] = action
    items = await db.activity.find(q, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    return items

# -------------------- Admin: Users --------------------
@api.get("/users")
async def list_users(user: dict = Depends(get_current_user), all_tenants: bool = False):
    if user["role"] == "super_admin" and all_tenants:
        q = {}
    else:
        q = {"company_id": user["company_id"]}
    items = await db.users.find(q, {"_id": 0, "password_hash": 0, "mfa_secret": 0}).to_list(500)
    return items

@api.patch("/users/{user_id}")
async def update_user(user_id: str, body: UserUpdateIn, actor: dict = Depends(get_current_user)):
    if actor["role"] not in ("super_admin", "owner"):
        raise HTTPException(status_code=403, detail="Forbidden")
    target = await db.users.find_one({"id": user_id}, {"_id": 0, "password_hash": 0, "mfa_secret": 0})
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    if actor["role"] != "super_admin" and target.get("company_id") != actor["company_id"]:
        raise HTTPException(status_code=403, detail="Cross-tenant edit forbidden")
    if target.get("role") == "owner" and actor["id"] != target["id"]:
        raise HTTPException(status_code=400, detail="Cannot modify the company owner")
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if "role" in updates:
        if updates["role"] not in ROLES:
            raise HTTPException(status_code=400, detail="Invalid role")
        if updates["role"] == "super_admin" and actor["role"] != "super_admin":
            raise HTTPException(status_code=403, detail="Cannot grant super_admin")
        if updates["role"] == "owner" and actor["role"] != "super_admin":
            raise HTTPException(status_code=403, detail="Cannot grant owner role")
    if updates:
        await db.users.update_one({"id": user_id}, {"$set": updates})
        await log_activity(actor, "user.updated", "user", user_id, updates)
    return await db.users.find_one({"id": user_id}, {"_id": 0, "password_hash": 0, "mfa_secret": 0})

@api.post("/users/invite")
async def invite_user(body: InviteIn, actor: dict = Depends(get_current_user)):
    allowed = INVITE_ALLOWED.get(actor["role"], set())
    if body.role not in allowed:
        raise HTTPException(status_code=403, detail=f"Cannot invite role '{body.role}'")
    email = body.email.lower().strip()
    if await db.users.find_one({"email": email}):
        raise HTTPException(status_code=400, detail="Email already registered")
    temp_password = pysecrets.token_urlsafe(10)
    uid = str(uuid.uuid4())
    user = {
        "id": uid,
        "company_id": actor["company_id"],
        "name": body.name,
        "email": email,
        "password_hash": hash_password(temp_password),
        "role": body.role,
        "active": True,
        "mfa_enabled": False,
        "mfa_secret": None,
        "email_verified": False,
        "invited_by": actor["id"],
        "created_at": now_iso(),
    }
    await db.users.insert_one(user)
    user.pop("_id", None)
    token = create_invite_token(uid)
    setup_url = f"{FRONTEND_URL}/reset?token={create_pw_reset_token(uid)}&invited=1"
    company = await db.companies.find_one({"id": actor["company_id"]}, {"_id": 0}) or {}
    email_id = await send_email(
        email,
        f"You're invited to {company.get('name','A1 Field Pro')}",
        email_layout(
            f"You're invited to {company.get('name','A1 Field Pro')}",
            f"<p>{actor['name']} invited you as a <strong>{ROLE_LABELS.get(body.role, body.role)}</strong>. Click the button to set your password and sign in.</p>",
            "Set my password", setup_url,
        ),
    )
    await log_activity(actor, "user.invited", "user", uid, {"role": body.role, "email": email})
    out = {k: v for k, v in user.items() if k not in {"password_hash", "mfa_secret"}}
    out["setup_url"] = setup_url
    out["temp_password"] = temp_password
    out["email_sent"] = bool(email_id)
    return out

# -------------------- Company / Team --------------------
@api.get("/companies/me")
async def my_company(user: dict = Depends(get_current_user)):
    company = await db.companies.find_one({"id": user["company_id"]}, {"_id": 0})
    return company

@api.patch("/companies/me")
async def update_company(body: BrandingIn, user: dict = Depends(require_role("owner"))):
    updates = {f"branding.{k}": v for k, v in body.model_dump().items() if v is not None}
    if updates:
        await db.companies.update_one({"id": user["company_id"]}, {"$set": updates})
    return await db.companies.find_one({"id": user["company_id"]}, {"_id": 0})

@api.post("/companies/me/logo")
async def upload_logo(file: UploadFile = File(...), user: dict = Depends(require_role("owner"))):
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Only images allowed")
    ext = (file.filename or "logo").rsplit(".", 1)[-1].lower() if "." in (file.filename or "") else "png"
    path = f"{APP_NAME}/{user['company_id']}/branding/logo-{uuid.uuid4()}.{ext}"
    data = await file.read()
    result = put_object(path, data, file.content_type)
    await db.companies.update_one(
        {"id": user["company_id"]}, {"$set": {"branding.logo_path": result["path"]}}
    )
    return {"path": result["path"]}

@api.get("/team")
async def list_team(user: dict = Depends(get_current_user)):
    members = await db.users.find(
        {"company_id": user["company_id"]},
        {"_id": 0, "password_hash": 0},
    ).to_list(500)
    return members

@api.post("/team")
async def create_team_member(body: TeamCreateIn, user: dict = Depends(require_role("owner", "dispatcher"))):
    email = body.email.lower().strip()
    if await db.users.find_one({"email": email}):
        raise HTTPException(status_code=400, detail="Email already in use")
    uid = str(uuid.uuid4())
    await db.users.insert_one({
        "id": uid,
        "company_id": user["company_id"],
        "name": body.name,
        "email": email,
        "password_hash": hash_password(body.password),
        "role": body.role,
        "created_at": now_iso(),
    })
    new_user = await db.users.find_one({"id": uid}, {"_id": 0, "password_hash": 0})
    return new_user

@api.delete("/team/{user_id}")
async def remove_team_member(user_id: str, user: dict = Depends(require_role("owner"))):
    if user_id == user["id"]:
        raise HTTPException(status_code=400, detail="Cannot remove yourself")
    result = await db.users.delete_one({"id": user_id, "company_id": user["company_id"]})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Member not found")
    return {"ok": True}

# -------------------- Customers --------------------
@api.get("/customers")
async def list_customers(user: dict = Depends(get_current_user)):
    items = await db.customers.find(
        {"company_id": user["company_id"]}, {"_id": 0}
    ).sort("created_at", -1).to_list(500)
    return items

@api.post("/customers")
async def create_customer(body: CustomerIn, user: dict = Depends(get_current_user)):
    doc = {
        "id": str(uuid.uuid4()),
        "company_id": user["company_id"],
        "created_at": now_iso(),
        **body.model_dump(),
    }
    await db.customers.insert_one(doc)
    doc.pop("_id", None)
    return doc

# -------------------- Jobs --------------------
@api.get("/jobs")
async def list_jobs(
    user: dict = Depends(get_current_user),
    status: Optional[str] = None,
    assigned_to: Optional[str] = None,
    mine: bool = False,
):
    q = {"company_id": user["company_id"]}
    if status:
        q["status"] = status
    if assigned_to:
        q["assigned_to"] = assigned_to
    if mine:
        q["assigned_to"] = user["id"]
    items = await db.jobs.find(q, {"_id": 0}).sort("created_at", -1).to_list(1000)
    return items

@api.post("/jobs")
async def create_job(body: JobIn, user: dict = Depends(get_current_user)):
    data = body.model_dump()
    if data.get("scheduled_at") and data["status"] == "unscheduled":
        data["status"] = "scheduled"
    doc = {
        "id": str(uuid.uuid4()),
        "company_id": user["company_id"],
        "created_by": user["id"],
        "created_at": now_iso(),
        "paid": False,
        **data,
    }
    await db.jobs.insert_one(doc)
    doc.pop("_id", None)
    return doc

@api.get("/jobs/{job_id}")
async def get_job(job_id: str, user: dict = Depends(get_current_user)):
    job = await db.jobs.find_one({"id": job_id, "company_id": user["company_id"]}, {"_id": 0})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job

@api.patch("/jobs/{job_id}")
async def update_job(job_id: str, body: JobUpdate, user: dict = Depends(get_current_user)):
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    if updates.get("scheduled_at") and updates.get("status") is None:
        existing = await db.jobs.find_one(
            {"id": job_id, "company_id": user["company_id"]}, {"status": 1, "_id": 0}
        )
        if existing and existing.get("status") == "unscheduled":
            updates["status"] = "scheduled"
    updates["updated_at"] = now_iso()
    result = await db.jobs.update_one(
        {"id": job_id, "company_id": user["company_id"]}, {"$set": updates}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Job not found")
    job = await db.jobs.find_one({"id": job_id}, {"_id": 0})
    return job

@api.delete("/jobs/{job_id}")
async def delete_job(job_id: str, user: dict = Depends(require_role("owner", "dispatcher"))):
    result = await db.jobs.delete_one({"id": job_id, "company_id": user["company_id"]})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"ok": True}

# -------------------- Dashboard --------------------
@api.get("/dashboard/stats")
async def dashboard_stats(user: dict = Depends(get_current_user)):
    company_id = user["company_id"]
    today = datetime.now(timezone.utc).date().isoformat()
    all_jobs = await db.jobs.find({"company_id": company_id}, {"_id": 0}).to_list(2000)
    technicians = await db.users.count_documents({"company_id": company_id, "role": "technician"})

    jobs_today = 0
    revenue_today = 0.0
    revenue_total = 0.0
    completed = 0
    in_progress = 0
    scheduled = 0
    unscheduled = 0
    for j in all_jobs:
        s = j.get("scheduled_at") or ""
        if s.startswith(today):
            jobs_today += 1
        if j.get("status") == "completed":
            completed += 1
            revenue_total += float(j.get("price") or 0)
            if s.startswith(today):
                revenue_today += float(j.get("price") or 0)
        elif j.get("status") == "in_progress":
            in_progress += 1
        elif j.get("status") == "scheduled":
            scheduled += 1
        elif j.get("status") == "unscheduled":
            unscheduled += 1

    total = len(all_jobs)
    completion_rate = round((completed / total) * 100, 1) if total else 0.0

    return {
        "jobs_today": jobs_today,
        "revenue_today": revenue_today,
        "revenue_total": revenue_total,
        "active_technicians": technicians,
        "completion_rate": completion_rate,
        "totals": {
            "total": total,
            "completed": completed,
            "in_progress": in_progress,
            "scheduled": scheduled,
            "unscheduled": unscheduled,
        },
    }

# -------------------- Payments (Stripe) --------------------
@api.post("/payments/checkout")
async def create_checkout(body: CheckoutIn, request: Request, user: dict = Depends(get_current_user)):
    job = await db.jobs.find_one({"id": body.job_id, "company_id": user["company_id"]}, {"_id": 0})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    amount = float(job.get("price") or 0)
    if amount <= 0:
        raise HTTPException(status_code=400, detail="Job has no price to charge")
    if job.get("paid"):
        raise HTTPException(status_code=400, detail="Job already paid")

    host_url = str(request.base_url)
    webhook_url = f"{host_url}api/webhook/stripe"
    stripe_checkout = StripeCheckout(api_key=STRIPE_API_KEY, webhook_url=webhook_url)

    success_url = f"{body.origin_url}/payment/result?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{body.origin_url}/app/jobs"
    req = CheckoutSessionRequest(
        amount=amount,
        currency="usd",
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={
            "job_id": body.job_id,
            "company_id": user["company_id"],
            "user_id": user["id"],
        },
    )
    session = await stripe_checkout.create_checkout_session(req)
    await db.payment_transactions.insert_one({
        "id": str(uuid.uuid4()),
        "session_id": session.session_id,
        "job_id": body.job_id,
        "company_id": user["company_id"],
        "user_id": user["id"],
        "amount": amount,
        "currency": "usd",
        "payment_status": "initiated",
        "status": "open",
        "metadata": {"job_id": body.job_id},
        "created_at": now_iso(),
    })
    return {"url": session.url, "session_id": session.session_id}

@api.get("/payments/status/{session_id}")
async def payment_status(session_id: str, request: Request, user: dict = Depends(get_current_user)):
    tx = await db.payment_transactions.find_one(
        {"session_id": session_id, "company_id": user["company_id"]}, {"_id": 0}
    )
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")
    if tx.get("payment_status") == "paid":
        return tx

    host_url = str(request.base_url)
    webhook_url = f"{host_url}api/webhook/stripe"
    stripe_checkout = StripeCheckout(api_key=STRIPE_API_KEY, webhook_url=webhook_url)
    status = await stripe_checkout.get_checkout_status(session_id)
    updates = {
        "payment_status": status.payment_status,
        "status": status.status,
        "updated_at": now_iso(),
    }
    await db.payment_transactions.update_one({"session_id": session_id}, {"$set": updates})
    if status.payment_status == "paid" and not tx.get("processed"):
        await db.jobs.update_one(
            {"id": tx["job_id"], "company_id": user["company_id"]},
            {"$set": {"paid": True, "status": "completed", "paid_at": now_iso()}},
        )
        await db.payment_transactions.update_one(
            {"session_id": session_id}, {"$set": {"processed": True}}
        )
    tx = await db.payment_transactions.find_one({"session_id": session_id}, {"_id": 0})
    return tx

@api.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    body = await request.body()
    sig = request.headers.get("Stripe-Signature", "")
    host_url = str(request.base_url)
    webhook_url = f"{host_url}api/webhook/stripe"
    stripe_checkout = StripeCheckout(api_key=STRIPE_API_KEY, webhook_url=webhook_url)
    try:
        evt = await stripe_checkout.handle_webhook(body, sig)
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        raise HTTPException(status_code=400, detail="Webhook handling failed")
    if evt.session_id:
        await db.payment_transactions.update_one(
            {"session_id": evt.session_id},
            {"$set": {"payment_status": evt.payment_status, "updated_at": now_iso()}},
        )
        if evt.payment_status == "paid":
            tx = await db.payment_transactions.find_one({"session_id": evt.session_id})
            if tx and not tx.get("processed"):
                await db.jobs.update_one(
                    {"id": tx["job_id"]},
                    {"$set": {"paid": True, "status": "completed", "paid_at": now_iso()}},
                )
                await db.payment_transactions.update_one(
                    {"session_id": evt.session_id}, {"$set": {"processed": True}}
                )
    return {"received": True}

# -------------------- Files / Photos / Signatures --------------------
class SignatureIn(BaseModel):
    image_base64: str  # data URL or raw base64
    signer_name: Optional[str] = ""

@api.post("/jobs/{job_id}/photos")
async def upload_job_photo(job_id: str, file: UploadFile = File(...), user: dict = Depends(get_current_user)):
    job = await db.jobs.find_one({"id": job_id, "company_id": user["company_id"]}, {"_id": 0})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Only images allowed")
    ext = (file.filename or "img").rsplit(".", 1)[-1].lower() if "." in (file.filename or "") else "jpg"
    if ext not in {"jpg", "jpeg", "png", "webp", "gif"}:
        ext = "jpg"
    path = f"{APP_NAME}/{user['company_id']}/jobs/{job_id}/{uuid.uuid4()}.{ext}"
    data = await file.read()
    result = put_object(path, data, file.content_type)
    photo = {
        "id": str(uuid.uuid4()),
        "path": result["path"],
        "content_type": file.content_type,
        "size": result.get("size", len(data)),
        "uploaded_by": user["id"],
        "uploaded_at": now_iso(),
    }
    await db.jobs.update_one(
        {"id": job_id, "company_id": user["company_id"]},
        {"$push": {"photos": photo}},
    )
    return photo

@api.delete("/jobs/{job_id}/photos/{photo_id}")
async def delete_job_photo(job_id: str, photo_id: str, user: dict = Depends(get_current_user)):
    result = await db.jobs.update_one(
        {"id": job_id, "company_id": user["company_id"]},
        {"$pull": {"photos": {"id": photo_id}}},
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Photo not found")
    return {"ok": True}

@api.post("/jobs/{job_id}/signature")
async def save_signature(job_id: str, body: SignatureIn, user: dict = Depends(get_current_user)):
    job = await db.jobs.find_one({"id": job_id, "company_id": user["company_id"]}, {"_id": 0})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    raw = body.image_base64
    if "," in raw:
        raw = raw.split(",", 1)[1]
    try:
        data = base64.b64decode(raw)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid base64 image")
    path = f"{APP_NAME}/{user['company_id']}/jobs/{job_id}/sig-{uuid.uuid4()}.png"
    result = put_object(path, data, "image/png")
    sig = {
        "path": result["path"],
        "signer_name": body.signer_name or "",
        "signed_at": now_iso(),
    }
    await db.jobs.update_one(
        {"id": job_id, "company_id": user["company_id"]},
        {"$set": {"signature": sig}},
    )
    return sig

@api.get("/files/{path:path}")
async def get_file(path: str, request: Request, auth: Optional[str] = Query(None)):
    # Accept token from cookie, Authorization header, or ?auth=
    token = request.cookies.get("access_token") or auth
    if not token:
        ah = request.headers.get("Authorization", "")
        if ah.startswith("Bearer "):
            token = ah[7:]
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        company_id = payload.get("company_id")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
    expected_prefix = f"{APP_NAME}/{company_id}/"
    if not path.startswith(expected_prefix):
        raise HTTPException(status_code=403, detail="Forbidden")
    data, ctype = get_object(path)
    return Response(content=data, media_type=ctype)

# -------------------- Public Booking Widget --------------------
class BookingIn(BaseModel):
    name: str
    phone: str
    email: Optional[str] = ""
    address: str
    job_type: str = "HVAC"
    description: str = ""
    preferred_date: Optional[str] = None  # ISO

@api.get("/public/companies/{company_id}")
async def public_company(company_id: str):
    company = await db.companies.find_one({"id": company_id}, {"_id": 0, "owner_id": 0})
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    return company

# -------------------- Customer Portal --------------------
@api.get("/portal/jobs")
async def portal_jobs(user: dict = Depends(get_current_user)):
    if user["role"] != "customer":
        raise HTTPException(status_code=403, detail="Customer-only")
    items = await db.jobs.find(
        {"customer_email": user["email"]}, {"_id": 0}
    ).sort("created_at", -1).to_list(200)
    return items

@api.get("/portal/companies")
async def portal_companies(user: dict = Depends(get_current_user)):
    if user["role"] != "customer":
        raise HTTPException(status_code=403, detail="Customer-only")
    # Distinct company ids from this customer's jobs
    company_ids = await db.jobs.distinct("company_id", {"customer_email": user["email"]})
    items = await db.companies.find({"id": {"$in": company_ids}}, {"_id": 0, "owner_id": 0}).to_list(50)
    return items

@api.post("/public/companies/{company_id}/bookings")
async def public_booking(company_id: str, body: BookingIn):
    company = await db.companies.find_one({"id": company_id}, {"_id": 0})
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    # Create or reuse customer
    cust = await db.customers.find_one({"company_id": company_id, "phone": body.phone}, {"_id": 0})
    if not cust:
        cust = {
            "id": str(uuid.uuid4()),
            "company_id": company_id,
            "name": body.name, "phone": body.phone, "email": body.email,
            "address": body.address, "created_at": now_iso(),
        }
        await db.customers.insert_one(dict(cust))
    job = {
        "id": str(uuid.uuid4()),
        "company_id": company_id,
        "title": f"{body.job_type} — {body.name}",
        "description": body.description,
        "customer_id": cust["id"],
        "customer_name": body.name,
        "customer_phone": body.phone,
        "customer_email": body.email,
        "address": body.address,
        "job_type": body.job_type,
        "assigned_to": None,
        "scheduled_at": body.preferred_date,
        "duration_min": 60,
        "price": 0.0,
        "status": "unscheduled",
        "paid": False,
        "source": "booking_widget",
        "created_at": now_iso(),
    }
    await db.jobs.insert_one(dict(job))
    return {"ok": True, "job_id": job["id"], "company_name": company["name"]}

@api.get("/jobs/{job_id}/invoice.pdf")
async def invoice_pdf(job_id: str, user: dict = Depends(get_current_user)):
    from io import BytesIO
    from reportlab.lib.pagesizes import LETTER
    from reportlab.lib.units import inch
    from reportlab.pdfgen import canvas as pdfcanvas
    from reportlab.lib.colors import HexColor

    job = await db.jobs.find_one({"id": job_id, "company_id": user["company_id"]}, {"_id": 0})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    company = await db.companies.find_one({"id": user["company_id"]}, {"_id": 0}) or {}
    primary = (company.get("branding") or {}).get("primary_color") or "#1D4ED8"
    accent  = (company.get("branding") or {}).get("accent_color") or "#DC2626"

    buf = BytesIO()
    c = pdfcanvas.Canvas(buf, pagesize=LETTER)
    W, H = LETTER

    # Header bar
    c.setFillColor(HexColor(primary))
    c.rect(0, H - 0.9*inch, W, 0.9*inch, fill=1, stroke=0)
    c.setFillColor(HexColor("#FFFFFF"))
    c.setFont("Helvetica-Bold", 22)
    c.drawString(0.6*inch, H - 0.55*inch, company.get("name", "A1 Field Pro"))
    c.setFont("Helvetica", 10)
    c.drawString(0.6*inch, H - 0.75*inch, f"{company.get('industry','')} · INVOICE")

    # Invoice meta
    c.setFillColor(HexColor("#0F172A"))
    c.setFont("Helvetica-Bold", 14)
    c.drawString(0.6*inch, H - 1.4*inch, "INVOICE")
    c.setFont("Helvetica", 10)
    c.drawString(0.6*inch, H - 1.6*inch, f"Job #: {job['id'][:8].upper()}")
    c.drawString(0.6*inch, H - 1.75*inch, f"Date: {datetime.now(timezone.utc).strftime('%b %d, %Y')}")

    # Bill to
    c.setFont("Helvetica-Bold", 11)
    c.drawString(0.6*inch, H - 2.2*inch, "BILL TO")
    c.setFont("Helvetica", 10)
    c.drawString(0.6*inch, H - 2.4*inch, job.get("customer_name") or "Customer")
    if job.get("address"):  c.drawString(0.6*inch, H - 2.55*inch, job["address"])
    if job.get("customer_phone"): c.drawString(0.6*inch, H - 2.70*inch, job["customer_phone"])

    # Line item table header
    y = H - 3.4*inch
    c.setFillColor(HexColor("#F1F5F9"))
    c.rect(0.6*inch, y - 0.05*inch, W - 1.2*inch, 0.3*inch, fill=1, stroke=0)
    c.setFillColor(HexColor("#0F172A"))
    c.setFont("Helvetica-Bold", 10)
    c.drawString(0.7*inch, y + 0.05*inch, "DESCRIPTION")
    c.drawRightString(W - 0.7*inch, y + 0.05*inch, "AMOUNT")

    # Line item
    y -= 0.45*inch
    c.setFont("Helvetica", 11)
    c.drawString(0.7*inch, y, job.get("title", "Service"))
    c.drawRightString(W - 0.7*inch, y, f"${(job.get('price') or 0):.2f}")
    if job.get("description"):
        y -= 0.2*inch
        c.setFont("Helvetica-Oblique", 9)
        c.setFillColor(HexColor("#475569"))
        for line in (job["description"] or "")[:400].split("\n")[:4]:
            c.drawString(0.7*inch, y, line[:90])
            y -= 0.15*inch
        c.setFillColor(HexColor("#0F172A"))

    # Total
    y = 2.0*inch
    c.setStrokeColor(HexColor("#E2E8F0"))
    c.line(0.6*inch, y + 0.4*inch, W - 0.6*inch, y + 0.4*inch)
    c.setFont("Helvetica-Bold", 14)
    c.drawRightString(W - 1.8*inch, y, "TOTAL")
    c.setFillColor(HexColor(accent))
    c.drawRightString(W - 0.7*inch, y, f"${(job.get('price') or 0):.2f}")
    c.setFillColor(HexColor("#0F172A"))

    # Status stamp
    if job.get("paid"):
        c.setFillColor(HexColor("#16A34A"))
        c.setFont("Helvetica-Bold", 22)
        c.drawString(0.7*inch, y - 0.2*inch, "PAID")
        c.setFillColor(HexColor("#0F172A"))

    # Footer
    c.setFont("Helvetica", 8)
    c.setFillColor(HexColor("#94A3B8"))
    c.drawString(0.6*inch, 0.6*inch, f"Thank you for your business — {company.get('name','')}")
    c.drawRightString(W - 0.6*inch, 0.6*inch, "Powered by A1 Field Pro")

    c.showPage()
    c.save()
    pdf = buf.getvalue()
    return Response(content=pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="invoice-{job["id"][:8]}.pdf"'})

@api.get("/config/roles")
async def get_roles_config(user: dict = Depends(get_current_user)):
    return {"roles": ROLES, "labels": ROLE_LABELS, "permissions": PERMISSIONS,
            "invite_allowed": {k: list(v) for k, v in INVITE_ALLOWED.items()}}

# -------------------- Health --------------------
@api.get("/")
async def root():
    return {"service": "A1 Field Pro API", "status": "ok"}

# -------------------- Startup --------------------
@app.on_event("startup")
async def startup():
    init_storage()
    await db.users.create_index("email", unique=True)
    await db.users.create_index("company_id")
    await db.jobs.create_index([("company_id", 1), ("status", 1)])
    await db.jobs.create_index([("company_id", 1), ("assigned_to", 1)])
    await db.customers.create_index("company_id")
    await db.payment_transactions.create_index("session_id", unique=True)
    await seed_demo()

async def seed_demo():
    """Seed super_admin + demo company + sample data."""
    # Super admin (platform-level, no company_id)
    if SUPERADMIN_EMAIL and SUPERADMIN_PASSWORD:
        sa = await db.users.find_one({"email": SUPERADMIN_EMAIL.lower()})
        if not sa:
            await db.users.insert_one({
                "id": str(uuid.uuid4()),
                "company_id": None,
                "name": "Platform Super Admin",
                "email": SUPERADMIN_EMAIL.lower(),
                "password_hash": hash_password(SUPERADMIN_PASSWORD),
                "role": "super_admin",
                "active": True,
                "mfa_enabled": False,
                "mfa_secret": None,
                "email_verified": True,
                "created_at": now_iso(),
            })
        elif not verify_password(SUPERADMIN_PASSWORD, sa["password_hash"]):
            await db.users.update_one(
                {"email": SUPERADMIN_EMAIL.lower()},
                {"$set": {"password_hash": hash_password(SUPERADMIN_PASSWORD)}},
            )

    demo_email = os.environ.get("ADMIN_EMAIL", "demo@a1fieldpro.com")
    demo_password = os.environ.get("ADMIN_PASSWORD", "Demo1234!")
    existing = await db.users.find_one({"email": demo_email})
    if existing:
        if not verify_password(demo_password, existing["password_hash"]):
            await db.users.update_one(
                {"email": demo_email}, {"$set": {"password_hash": hash_password(demo_password)}}
            )
        return

    company_id = str(uuid.uuid4())
    owner_id = str(uuid.uuid4())
    tech_id = str(uuid.uuid4())
    disp_id = str(uuid.uuid4())
    now = now_iso()
    await db.companies.insert_one({
        "id": company_id, "name": "A1 HVAC N DE-GO", "industry": "HVAC",
        "owner_id": owner_id, "created_at": now,
    })
    await db.users.insert_many([
        {"id": owner_id, "company_id": company_id, "name": "Demo Owner",
         "email": demo_email, "password_hash": hash_password(demo_password),
         "role": "owner", "active": True, "mfa_enabled": False, "mfa_secret": None,
         "email_verified": True, "created_at": now},
        {"id": disp_id, "company_id": company_id, "name": "Dana Dispatcher",
         "email": "dispatcher@a1fieldpro.com", "password_hash": hash_password("Demo1234!"),
         "role": "dispatcher", "active": True, "mfa_enabled": False, "mfa_secret": None,
         "email_verified": True, "created_at": now},
        {"id": tech_id, "company_id": company_id, "name": "Tom Technician",
         "email": "tech@a1fieldpro.com", "password_hash": hash_password("Demo1234!"),
         "role": "technician", "active": True, "mfa_enabled": False, "mfa_secret": None,
         "email_verified": True, "created_at": now},
    ])
    today = datetime.now(timezone.utc).replace(hour=14, minute=0, second=0, microsecond=0)
    sample_jobs = [
        {
            "id": str(uuid.uuid4()), "company_id": company_id, "created_by": owner_id,
            "title": "AC Unit Tune-up", "description": "Annual maintenance",
            "customer_name": "Sarah Johnson", "customer_phone": "(555) 234-1122",
            "address": "1421 Oak St, Austin TX", "job_type": "HVAC",
            "assigned_to": tech_id, "scheduled_at": today.isoformat(),
            "duration_min": 90, "price": 189.0, "status": "scheduled",
            "paid": False, "created_at": now,
        },
        {
            "id": str(uuid.uuid4()), "company_id": company_id, "created_by": owner_id,
            "title": "Garage Door Spring Replacement",
            "customer_name": "Mike Patel", "customer_phone": "(555) 902-7788",
            "address": "88 Maple Ave, Round Rock TX", "job_type": "Garage Doors",
            "assigned_to": tech_id, "scheduled_at": (today + timedelta(hours=3)).isoformat(),
            "duration_min": 120, "price": 320.0, "status": "scheduled",
            "paid": False, "created_at": now,
        },
        {
            "id": str(uuid.uuid4()), "company_id": company_id, "created_by": owner_id,
            "title": "Water Heater Install",
            "customer_name": "Linda Tran", "customer_phone": "(555) 311-4501",
            "address": "300 Cedar Ln, Austin TX", "job_type": "Plumbing",
            "assigned_to": None, "scheduled_at": None,
            "duration_min": 180, "price": 1450.0, "status": "unscheduled",
            "paid": False, "created_at": now,
        },
        {
            "id": str(uuid.uuid4()), "company_id": company_id, "created_by": owner_id,
            "title": "Panel Upgrade",
            "customer_name": "Greg Hopkins", "customer_phone": "(555) 711-9912",
            "address": "21 Birch Rd, Cedar Park TX", "job_type": "Electrical",
            "assigned_to": tech_id, "scheduled_at": (today - timedelta(days=1)).isoformat(),
            "duration_min": 240, "price": 2200.0, "status": "completed",
            "paid": True, "created_at": now,
        },
    ]
    await db.jobs.insert_many(sample_jobs)
    logger.info("Seeded demo company and sample jobs")

app.include_router(api)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in os.environ.get("CORS_ORIGINS", "*").split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
