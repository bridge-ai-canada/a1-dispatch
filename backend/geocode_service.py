"""Geocoding with provider fallback.

Primary (when configured): Mapbox or Google Maps via env-gated API key.
Fallback: OpenStreetMap Nominatim with throttling.

All results cached forever in `geocode_cache` (negative results 7d TTL).
The preview environment IP is occasionally rate-limited by Nominatim, so a
paid/managed provider is the recommended path — set MAPBOX_ACCESS_TOKEN or
GOOGLE_MAPS_API_KEY in backend/.env to enable.
"""
import asyncio
import logging
import os
import time
from typing import Optional
import httpx

from deps import db

logger = logging.getLogger("a1fieldpro.geocode")

MAPBOX_TOKEN = os.environ.get("MAPBOX_ACCESS_TOKEN", "").strip()
GOOGLE_KEY = os.environ.get("GOOGLE_MAPS_API_KEY", "").strip()
MAPBOX_URL = "https://api.mapbox.com/geocoding/v5/mapbox.places/{q}.json"
GOOGLE_URL = "https://maps.googleapis.com/maps/api/geocode/json"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "A1FieldPro/1.0 (admin@a1fieldpro.com)"
_last_nominatim_call = {"ts": 0.0}
_lock = asyncio.Lock()


async def _mapbox(client: httpx.AsyncClient, address: str) -> Optional[dict]:
    from urllib.parse import quote
    r = await client.get(
        MAPBOX_URL.format(q=quote(address)),
        params={"access_token": MAPBOX_TOKEN, "limit": 1},
    )
    if r.status_code != 200:
        logger.warning(f"Mapbox {r.status_code} for {address!r}")
        return None
    data = r.json().get("features") or []
    if not data:
        return None
    first = data[0]
    lng, lat = first["center"]
    return {
        "lat": float(lat), "lng": float(lng),
        "display_name": first.get("place_name", ""),
        "source": "mapbox",
    }


async def _google(client: httpx.AsyncClient, address: str) -> Optional[dict]:
    r = await client.get(GOOGLE_URL, params={"address": address, "key": GOOGLE_KEY})
    if r.status_code != 200:
        logger.warning(f"Google geocoding {r.status_code} for {address!r}")
        return None
    j = r.json()
    if j.get("status") != "OK" or not j.get("results"):
        return None
    first = j["results"][0]
    loc = first["geometry"]["location"]
    return {
        "lat": float(loc["lat"]), "lng": float(loc["lng"]),
        "display_name": first.get("formatted_address", ""),
        "source": "google",
    }


async def _nominatim(client: httpx.AsyncClient, address: str) -> Optional[dict]:
    # Throttle: 1 req/sec to be a good Nominatim citizen
    wait = 1.0 - (time.time() - _last_nominatim_call["ts"])
    if wait > 0:
        await asyncio.sleep(wait)
    _last_nominatim_call["ts"] = time.time()
    r = await client.get(
        NOMINATIM_URL,
        headers={"User-Agent": USER_AGENT},
        params={"q": address, "format": "json", "limit": 1, "addressdetails": 0},
    )
    if r.status_code != 200:
        logger.warning(f"Nominatim {r.status_code} for {address!r} (uncached)")
        return None
    data = r.json()
    if not data:
        return None
    first = data[0]
    return {
        "lat": float(first["lat"]), "lng": float(first["lon"]),
        "display_name": first.get("display_name", ""),
        "source": "nominatim",
    }


async def geocode(address: str) -> Optional[dict]:
    """Return {address, lat, lng, source, display_name} or None."""
    if not address or len(address.strip()) < 5:
        return None
    addr_norm = address.strip().lower()
    cached = await db.geocode_cache.find_one({"address": addr_norm}, {"_id": 0})
    if cached:
        if cached.get("lat") is not None:
            return cached
        if (time.time() - (cached.get("cached_at") or 0)) < 7 * 86400:
            return None

    async with _lock:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                result = None
                if MAPBOX_TOKEN:
                    result = await _mapbox(client, address)
                if not result and GOOGLE_KEY:
                    result = await _google(client, address)
                if not result:
                    result = await _nominatim(client, address)

                if not result:
                    # Negative cache (TTL handled on read)
                    await db.geocode_cache.update_one(
                        {"address": addr_norm},
                        {"$set": {"address": addr_norm, "lat": None, "lng": None,
                                  "source": "none", "cached_at": time.time()}},
                        upsert=True,
                    )
                    return None

                doc = {
                    "address": addr_norm,
                    "lat": result["lat"], "lng": result["lng"],
                    "display_name": result.get("display_name", ""),
                    "source": result["source"],
                    "cached_at": time.time(),
                }
                await db.geocode_cache.update_one(
                    {"address": addr_norm}, {"$set": doc}, upsert=True,
                )
                return doc
        except Exception as e:
            logger.error(f"Geocode failed for {address!r}: {e}")
            return None
