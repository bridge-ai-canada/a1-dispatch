"""Dispatch realtime: WebSocket, tech status, GPS location, priority field for jobs."""
import jwt
from typing import Optional, Literal
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, Query, Depends
from pydantic import BaseModel, Field

from deps import db, JWT_SECRET, JWT_ALGORITHM, now_iso, get_current_user
from ws_hub import hub

router = APIRouter()


# ---------- WebSocket endpoint ----------
@router.websocket("/ws")
async def ws_endpoint(websocket: WebSocket, token: str = Query(...)):
    """Long-lived connection. Authenticates via the same JWT used for HTTP."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id = payload.get("sub")
        company_id = payload.get("company_id")
    except jwt.InvalidTokenError:
        await websocket.accept()
        await websocket.close(code=4401, reason="invalid token")
        return
    if not user_id or not company_id:
        await websocket.accept()
        await websocket.close(code=4401, reason="missing claims")
        return
    await websocket.accept()
    await hub.join(company_id, websocket)
    try:
        # Send a hello so clients can confirm connection
        await websocket.send_json({"type": "hello", "data": {"user_id": user_id, "company_id": company_id}})
        # Heartbeat loop: server pings every 25s; if recv() times out we send ping
        import asyncio
        while True:
            try:
                msg = await asyncio.wait_for(websocket.receive_text(), timeout=25.0)
                # Client can send {"type":"pong"} or anything — we just keep the loop alive
            except asyncio.TimeoutError:
                try:
                    await websocket.send_json({"type": "ping", "data": {"ts": now_iso()}})
                except Exception:
                    break
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        await hub.leave(company_id, websocket)


# ---------- Tech status ----------
TechStatus = Literal["available", "on_route", "on_site", "break", "off_duty"]


class StatusIn(BaseModel):
    status: TechStatus


@router.post("/me/status")
async def update_my_status(body: StatusIn, user: dict = Depends(get_current_user)):
    await db.users.update_one(
        {"id": user["id"]},
        {"$set": {"tech_status": body.status, "tech_status_at": now_iso()}},
    )
    await hub.broadcast(user["company_id"], "user.status", {
        "user_id": user["id"], "status": body.status, "ts": now_iso(),
    })
    return {"ok": True, "status": body.status}


# ---------- GPS location ----------
class LocationIn(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    accuracy_m: Optional[float] = None


@router.post("/me/location")
async def update_my_location(body: LocationIn, user: dict = Depends(get_current_user)):
    loc = {
        "lat": body.latitude,
        "lng": body.longitude,
        "accuracy_m": body.accuracy_m,
        "ts": now_iso(),
    }
    await db.users.update_one({"id": user["id"]}, {"$set": {"last_location": loc}})
    await hub.broadcast(user["company_id"], "user.location", {
        "user_id": user["id"], **loc,
    })
    return {"ok": True}


@router.get("/team/locations")
async def team_locations(user: dict = Depends(get_current_user)):
    """All teammates' last-known location + status — for the dispatcher map."""
    items = await db.users.find(
        {"company_id": user["company_id"]},
        {"id": 1, "name": 1, "role": 1, "tech_status": 1, "tech_status_at": 1, "last_location": 1},
    ).to_list(500)
    out = []
    for u in items:
        u.pop("_id", None)
        out.append(u)
    return out


# ---------- Job priority (lightweight stand-alone update) ----------
class PriorityIn(BaseModel):
    priority: Literal["low", "normal", "high", "emergency"]


@router.patch("/jobs/{job_id}/priority")
async def set_priority(job_id: str, body: PriorityIn, user: dict = Depends(get_current_user)):
    res = await db.jobs.update_one(
        {"id": job_id, "company_id": user["company_id"]},
        {"$set": {"priority": body.priority, "updated_at": now_iso()}},
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Job not found")
    job = await db.jobs.find_one({"id": job_id}, {"_id": 0})
    await hub.broadcast(user["company_id"], "job.updated", job)
    return job
