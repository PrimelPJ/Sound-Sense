"""Live updates to every open dashboard over WebSocket."""

import json
import logging

from fastapi import WebSocket

log = logging.getLogger("soundsense.live")


class LiveHub:
    def __init__(self) -> None:
        self.clients: set[WebSocket] = set()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self.clients.add(ws)

    def disconnect(self, ws: WebSocket) -> None:
        self.clients.discard(ws)

    async def broadcast(self, message: dict) -> None:
        text = json.dumps(message, default=str)
        dead = []
        for ws in list(self.clients):
            try:
                await ws.send_text(text)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)
        log.info("live -> %s (%d clients)", message.get("type"), len(self.clients))


hub = LiveHub()
