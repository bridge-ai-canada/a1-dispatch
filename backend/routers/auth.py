"""Auth, sessions, MFA, password reset, Google OAuth."""
import io
import uuid
import base64
import secrets as pysecrets
import jwt
import pyotp
import qrcode
import requests
from fastapi import APIRouter, HTTPException, Request, Response, Depends, Query

from deps import (
    db, logger, now_iso,
    JWT_SECRET, JWT_ALGORITHM, FRONTEND_URL,
    hash_password, verify_password,
    create_access_token, create_pw_reset_token, create_verify_token,
    set_auth_cookie, clear_auth_cookie,
    get_current_user, send_email, email_layout,
    log_activity, create_session,
    RegisterIn, LoginIn, ForgotIn, ResetIn,
    MfaEnableIn, MfaDisableIn, GoogleExchangeIn,
)

router = APIRouter()


@router.post("/auth/register")
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


@router.post("/auth/login")
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


@router.post("/auth/logout")
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


@router.get("/auth/me")
async def me(user: dict = Depends(get_current_user)):
    from roles import PERMISSIONS
    company = await db.companies.find_one({"id": user["company_id"]}, {"_id": 0}) if user.get("company_id") else None
    return {"user": user, "company": company, "permissions": PERMISSIONS.get(user["role"], [])}


@router.post("/auth/verify")
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


@router.post("/auth/verify/resend")
async def verify_resend(user: dict = Depends(get_current_user)):
    if user.get("email_verified"):
        return {"ok": True, "already_verified": True}
    verify_url = f"{FRONTEND_URL}/verify?token={create_verify_token(user['id'])}"
    email_id = await send_email(
        user["email"], "Verify your A1 Field Pro email",
        email_layout("Verify your email",
            f"<p>Hi {user['name']}, please verify this email so you can receive invoices and booking confirmations.</p>",
            "Verify email", verify_url),
        actor=user, purpose="auth.verify_resend",
    )
    return {"ok": True, "verify_url": verify_url, "email_sent": bool(email_id)}


@router.post("/auth/google/exchange")
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
        uid = str(uuid.uuid4())
        new_user = {
            "id": uid, "company_id": None,
            "name": info.get("name") or email.split("@")[0],
            "email": email,
            "password_hash": hash_password(pysecrets.token_urlsafe(16)),
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
    if user.get("mfa_enabled"):
        raise HTTPException(status_code=401, detail="mfa_required")
    sid = await create_session(user, request)
    token = create_access_token(user["id"], user.get("company_id"), user["role"], sid)
    set_auth_cookie(response, token)
    user.pop("password_hash", None); user.pop("mfa_secret", None); user.pop("_id", None)
    await log_activity(user, "auth.google.login")
    return {"user": user, "token": token}


@router.post("/auth/forgot")
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
            actor=user, purpose="auth.password_reset",
        )
        return {"ok": True, "reset_url": reset_url}
    return {"ok": True}


@router.post("/auth/reset")
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
    await db.sessions.update_many({"user_id": payload["sub"]}, {"$set": {"revoked": True}})
    return {"ok": True}


def _qr_data_url(otpauth_url: str) -> str:
    img = qrcode.make(otpauth_url)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


@router.post("/auth/mfa/setup")
async def mfa_setup(user: dict = Depends(get_current_user)):
    secret = pyotp.random_base32()
    otpauth = pyotp.totp.TOTP(secret).provisioning_uri(name=user["email"], issuer_name="A1 Field Pro")
    await db.users.update_one(
        {"id": user["id"]}, {"$set": {"mfa_secret": secret, "mfa_enabled": False}}
    )
    return {"secret": secret, "otpauth_url": otpauth, "qr_data_url": _qr_data_url(otpauth)}


@router.post("/auth/mfa/enable")
async def mfa_enable(body: MfaEnableIn, user: dict = Depends(get_current_user)):
    u = await db.users.find_one({"id": user["id"]})
    if not u or not u.get("mfa_secret"):
        raise HTTPException(status_code=400, detail="MFA setup not started")
    if not pyotp.TOTP(u["mfa_secret"]).verify(body.code.strip(), valid_window=1):
        raise HTTPException(status_code=400, detail="Invalid code")
    await db.users.update_one({"id": user["id"]}, {"$set": {"mfa_enabled": True}})
    await log_activity(user, "mfa.enabled")
    return {"ok": True}


@router.post("/auth/mfa/disable")
async def mfa_disable(body: MfaDisableIn, user: dict = Depends(get_current_user)):
    u = await db.users.find_one({"id": user["id"]})
    if not verify_password(body.password, u["password_hash"]):
        raise HTTPException(status_code=401, detail="Wrong password")
    await db.users.update_one(
        {"id": user["id"]}, {"$set": {"mfa_enabled": False, "mfa_secret": None}}
    )
    await log_activity(user, "mfa.disabled")
    return {"ok": True}


@router.get("/sessions")
async def list_sessions(user: dict = Depends(get_current_user)):
    items = await db.sessions.find(
        {"user_id": user["id"], "revoked": {"$ne": True}}, {"_id": 0}
    ).sort("created_at", -1).to_list(50)
    for s in items:
        s["current"] = s["id"] == user.get("_session_id")
    return items


@router.delete("/sessions/{session_id}")
async def revoke_session(session_id: str, user: dict = Depends(get_current_user)):
    await db.sessions.update_one(
        {"id": session_id, "user_id": user["id"]},
        {"$set": {"revoked": True, "revoked_at": now_iso()}},
    )
    return {"ok": True}
