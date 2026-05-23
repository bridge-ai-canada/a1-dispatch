"""Branding: company white-label settings (logo, colors, app name, domain) + public lookup."""
import uuid
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Response

from deps import (
    db, now_iso, APP_NAME,
    put_object, get_object, get_current_user, require_role, log_activity,
    BrandingIn,
)

router = APIRouter()


@router.get("/branding")
async def get_branding(user: dict = Depends(get_current_user)):
    company = await db.companies.find_one({"id": user["company_id"]}, {"_id": 0})
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    return {
        "company_id": company["id"],
        "company_name": company.get("name", ""),
        "branding": company.get("branding") or {},
    }


@router.patch("/branding")
async def update_branding(
    body: BrandingIn,
    user: dict = Depends(require_role("owner", "super_admin")),
):
    payload = body.model_dump(exclude_unset=True, exclude_none=True)
    if not payload:
        return await get_branding(user)
    # Custom-domain uniqueness — collision across companies blocks save.
    if payload.get("custom_domain"):
        existing = await db.companies.find_one(
            {"branding.custom_domain": payload["custom_domain"], "id": {"$ne": user["company_id"]}},
            {"_id": 0, "id": 1},
        )
        if existing:
            raise HTTPException(status_code=409, detail="Custom domain already taken by another tenant")
    updates = {f"branding.{k}": v for k, v in payload.items()}
    await db.companies.update_one({"id": user["company_id"]}, {"$set": updates})
    await db.branding_audit.insert_one({
        "company_id": user["company_id"],
        "actor_id": user["id"],
        "changes": payload,
        "created_at": now_iso(),
    })
    await log_activity(user, "branding.updated",
                       meta={"fields": list(payload.keys())})
    return await get_branding(user)


async def _upload_image(file: UploadFile, kind: str, user: dict) -> dict:
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Only images allowed")
    ext = (file.filename or kind).rsplit(".", 1)[-1].lower() if "." in (file.filename or "") else "png"
    path = f"{APP_NAME}/{user['company_id']}/branding/{kind}-{uuid.uuid4()}.{ext}"
    data = await file.read()
    if len(data) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Image too large (5MB max)")
    result = put_object(path, data, file.content_type)
    return result


@router.post("/branding/upload-logo")
async def upload_logo(
    file: UploadFile = File(...),
    user: dict = Depends(require_role("owner", "super_admin")),
):
    result = await _upload_image(file, "logo", user)
    await db.companies.update_one(
        {"id": user["company_id"]}, {"$set": {"branding.logo_path": result["path"]}},
    )
    return {"path": result["path"]}


@router.post("/branding/upload-favicon")
async def upload_favicon(
    file: UploadFile = File(...),
    user: dict = Depends(require_role("owner", "super_admin")),
):
    result = await _upload_image(file, "favicon", user)
    await db.companies.update_one(
        {"id": user["company_id"]}, {"$set": {"branding.favicon_path": result["path"]}},
    )
    return {"path": result["path"]}


@router.get("/branding/audit")
async def branding_audit(
    user: dict = Depends(require_role("owner", "super_admin")),
    limit: int = 50,
):
    items = await db.branding_audit.find(
        {"company_id": user["company_id"]}, {"_id": 0},
    ).sort("created_at", -1).to_list(min(limit, 200))
    return items


# -------------------- Public lookup (unauthenticated) --------------------
@router.get("/public/branding")
async def public_branding(domain: str = "", company_id: str = ""):
    """Resolve branding by custom_domain or company_id.
    Used by the customer portal, booking widget, and white-label customer apps."""
    q = None
    if domain:
        q = {"branding.custom_domain": domain.strip().lower()}
    elif company_id:
        q = {"id": company_id}
    if not q:
        raise HTTPException(status_code=400, detail="domain or company_id required")
    company = await db.companies.find_one(q, {"_id": 0, "id": 1, "name": 1, "branding": 1})
    if not company:
        raise HTTPException(status_code=404, detail="Not found")
    b = company.get("branding") or {}
    # Build absolute public URLs for branding assets so unauthenticated landing pages can show them.
    logo_url = f"/api/public/branding/asset/{company['id']}/logo" if b.get("logo_path") else None
    favicon_url = f"/api/public/branding/asset/{company['id']}/favicon" if b.get("favicon_path") else None
    return {
        "company_id": company["id"],
        "company_name": company.get("name", ""),
        "app_name": b.get("app_name") or company.get("name", ""),
        "primary_color": b.get("primary_color") or "#1D4ED8",
        "accent_color": b.get("accent_color") or "#DC2626",
        "secondary_color": b.get("secondary_color") or "#0F172A",
        "logo_path": b.get("logo_path"),
        "favicon_path": b.get("favicon_path"),
        "logo_url": logo_url,
        "favicon_url": favicon_url,
        "tagline": b.get("tagline") or "",
        "support_email": b.get("support_email"),
        "support_phone": b.get("support_phone"),
    }


@router.get("/public/branding/asset/{company_id}/{kind}")
async def public_branding_asset(company_id: str, kind: str):
    """Serve a tenant's logo or favicon WITHOUT auth — only the two whitelisted asset kinds."""
    if kind not in ("logo", "favicon"):
        raise HTTPException(status_code=404, detail="Unknown asset")
    company = await db.companies.find_one(
        {"id": company_id}, {"_id": 0, "branding": 1},
    )
    if not company:
        raise HTTPException(status_code=404, detail="Not found")
    path = (company.get("branding") or {}).get(f"{kind}_path")
    if not path:
        raise HTTPException(status_code=404, detail=f"No {kind} set for this tenant")
    # Defense in depth: paths are stored as `${APP_NAME}/<company_id>/branding/<kind>-<uuid>.<ext>`
    # — only serve paths that match this tenant.
    if not path.startswith(f"{APP_NAME}/{company_id}/branding/"):
        raise HTTPException(status_code=403, detail="Asset not eligible for public serving")
    data, ctype = get_object(path)
    return Response(content=data, media_type=ctype, headers={"Cache-Control": "public, max-age=3600"})
