"""Free geocoding via OpenStreetMap Nominatim with throttling + DB cache.

Nominatim usage policy: max 1 request per second, no bulk. We add a token-bucket
limiter and cache results forever in `geocode_cache`. Errors are logged not raised.
"""
import asyncio
import logging
import time
from typing import Optional
import httpx

from deps import db

logger = logging.getLogger("a1fieldpro.geocode")

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "A1FieldPro/1.0 (admin@a1fieldpro.com)"
_last_call = {"ts": 0.0}
_lock = asyncio.Lock()


async def geocode(address: str) -> Optional[dict]:
    """Return {lat, lng, source, address_norm} for `address`, or None on failure."""
    if not address or len(address.strip()) < 5:
        return None
    addr_norm = address.strip().lower()
    cached = await db.geocode_cache.find_one({"address": addr_norm}, {"_id": 0})
    if cached:
        if cached.get("lat") is None:
            return None
        return cached

    async with _lock:
        # Throttle: 1 req/sec to be a good Nominatim citizen
        wait = 1.0 - (time.time() - _last_call["ts"])
        if wait > 0:
            await asyncio.sleep(wait)
        _last_call["ts"] = time.time()
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(
                    NOMINATIM_URL,
                    headers={"User-Agent": USER_AGENT},
                    params={"q": address, "format": "json", "limit": 1, "addressdetails": 0},
                )
                if r.status_code != 200:
                    logger.warning(f"Nominatim {r.status_code} for {address!r}")
                    await db.geocode_cache.update_one(
                        {"address": addr_norm},
                        {"$set": {"address": addr_norm, "lat": None, "lng": None,
                                  "source": "nominatim", "cached_at": time.time()}},
                        upsert=True,
                    )
                    return None
                data = r.json()
                if not data:
                    await db.geocode_cache.update_one(
                        {"address": addr_norm},
                        {"$set": {"address": addr_norm, "lat": None, "lng": None,
                                  "source": "nominatim", "cached_at": time.time()}},
                        upsert=True,
                    )
                    return None
                first = data[0]
                result = {
                    "address": addr_norm,
                    "lat": float(first["lat"]),
                    "lng": float(first["lon"]),
                    "display_name": first.get("display_name", ""),
                    "source": "nominatim",
                    "cached_at": time.time(),
                }
                await db.geocode_cache.update_one(
                    {"address": addr_norm}, {"$set": result}, upsert=True,
                )
                return result
        except Exception as e:
            logger.error(f"Geocode failed for {address!r}: {e}")
            return None
