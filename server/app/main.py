"""SoundSense API server.

Run locally:  uvicorn app.main:app --reload
Docs:         http://localhost:8000/docs
"""

import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session, select

from . import config
from .db import create_tables, engine
from .escalation import EscalationEngine
from .live import hub
from .models import Contact, Event
from .routes import contacts, events, log
from .routes.events import to_out
from .sms import send_sms

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")


def seed_contacts() -> None:
    """Load demo contacts if the table is empty, so escalation works on first run."""
    path = Path(config.SEED_CONTACTS_FILE)
    if not path.exists():
        return
    with Session(engine) as s:
        if s.exec(select(Contact)).first() is not None:
            return
        for i, row in enumerate(json.loads(path.read_text())):
            s.add(Contact(position=row.get("position", i), **{k: row[k] for k in ("name", "phone", "role")}))
        s.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_tables()
    seed_contacts()
    app.state.escalation = EscalationEngine(engine, hub.broadcast, send_sms)
    yield
    app.state.escalation.stop_all()


app = FastAPI(title="SoundSense API", version="1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(events.router)
app.include_router(log.router)
app.include_router(contacts.router)


@app.get("/health")
def health():
    return {"ok": True, "sounds": list(config.SOUNDS), "time_scale": config.TIME_SCALE}


@app.get("/sounds")
def sounds():
    """Sound names, labels and whether they escalate. Handy for the dashboard."""
    return [
        {"sound": key, "label": v["label"], "escalates": v["first_wait"] is not None,
         "first_wait": v["first_wait"]}
        for key, v in config.SOUNDS.items()
    ]


@app.websocket("/live")
async def live(ws: WebSocket):
    """Dashboard connects here. Gets a snapshot first, then every change as it happens."""
    await hub.connect(ws)
    try:
        with Session(engine) as s:
            open_events = s.exec(
                select(Event).where(Event.status.in_(["active", "escalating", "unanswered"]))
                .order_by(Event.id.desc())
            ).all()
            snapshot = [to_out(e, s).model_dump(mode="json") for e in open_events]
        await ws.send_text(json.dumps({"type": "snapshot", "open_events": snapshot}))
        while True:
            await ws.receive_text()  # keep the socket open; clients don't need to send anything
    except WebSocketDisconnect:
        pass
    finally:
        hub.disconnect(ws)
