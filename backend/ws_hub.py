"""Company-scoped WebSocket pub/sub for the dispatch board.

All staff in a company subscribe to ws://<host>/api/ws?token=<jwt>.
Backend broadcasts JSON events: {type, data, ts} when jobs/users/locations change.
"""
import asyncio
import json
import logging
from typing import Dict, Set
from fastapi import WebSocket

logger = logging.getLogger("a1fieldpro.ws")


class WSHub:
    def __init__(self) -> None:
        # company_id -> set of connected sockets
        self._rooms: Dict[str, Set[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def join(self, company_id: str, ws: WebSocket) -> None:
        async with self._lock:
            self._rooms.setdefault(company_id, set()).add(ws)

    async def leave(self, company_id: str, ws: WebSocket) -> None:
        async with self._lock:
            self._rooms.get(company_id, set()).discard(ws)
            if not self._rooms.get(company_id):
                self._rooms.pop(company_id, None)

    async def broadcast(self, company_id: str, event_type: str, data: dict) -> None:
        payload = json.dumps({"type": event_type, "data": data})
        sockets = list(self._rooms.get(company_id, set()))
        dead = []
        for ws in sockets:
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)
        if dead:
            async with self._lock:
                for ws in dead:
                    self._rooms.get(company_id, set()).discard(ws)


hub = WSHub()
