"""Companies & team."""
import uuid
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File

from deps import (
    db, now_iso, APP_NAME,
    put_object, hash_password,
    get_current_user, require_role,
    BrandingIn, TeamCreateIn,
)

router = APIRouter()


@router.get("/companies/me")
async def my_company(user: dict = Depends(get_current_user)):
    company = await db.companies.find_one({"id": user["company_id"]}, {"_id": 0})
    return company


@router.patch("/companies/me")
async def update_company(body: BrandingIn, user: dict = Depends(require_role("owner"))):
    updates = {f"branding.{k}": v for k, v in body.model_dump().items() if v is not None}
    if updates:
        await db.companies.update_one({"id": user["company_id"]}, {"$set": updates})
    return await db.companies.find_one({"id": user["company_id"]}, {"_id": 0})


@router.post("/companies/me/logo")
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


@router.get("/team")
async def list_team(user: dict = Depends(get_current_user)):
    members = await db.users.find(
        {"company_id": user["company_id"]},
        {"_id": 0, "password_hash": 0},
    ).to_list(500)
    return members


@router.post("/team")
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


@router.delete("/team/{user_id}")
async def remove_team_member(user_id: str, user: dict = Depends(require_role("owner"))):
    if user_id == user["id"]:
        raise HTTPException(status_code=400, detail="Cannot remove yourself")
    result = await db.users.delete_one({"id": user_id, "company_id": user["company_id"]})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Member not found")
    return {"ok": True}
