"""Core event routes: new sound, "I'm OK", and one event's details.

OWNER: Primel.
"""

from datetime import timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlmodel import Session, select

from .. import config
from ..db import get_session
from ..live import hub
from ..models import EscalationStep, Event, now
from ..schemas import AckIn, EventIn, EventOut, StepOut

router = APIRouter(prefix="/events", tags=["events"])


def to_out(event: Event, session: Session, duplicate: bool = False) -> EventOut:
    steps = session.exec(
        select(EscalationStep).where(EscalationStep.event_id == event.id).order_by(EscalationStep.id)
    ).all()
    info = config.SOUNDS.get(event.sound, {})
    return EventOut(
        id=event.id,
        device_id=event.device_id,
        sound=event.sound,
        label=info.get("label", event.sound),
        confidence=event.confidence,
        ts=event.ts,
        status=event.status,
        escalates=info.get("first_wait") is not None,
        escalation_level=event.escalation_level,
        acked_by=event.acked_by,
        acked_at=event.acked_at,
        steps=[StepOut(**s.model_dump(include=set(StepOut.model_fields))) for s in steps],
        duplicate=duplicate,
    )


def _as_utc(dt):
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


@router.post("", response_model=EventOut, status_code=201)
async def create_event(body: EventIn, request: Request, session: Session = Depends(get_session)):
    if body.sound not in config.SOUNDS:
        raise HTTPException(422, f"unknown sound '{body.sound}', use one of {list(config.SOUNDS)}")

    # Same sound from the same device still open? Return that one instead of a new alert.
    cutoff = now() - timedelta(seconds=config.DUPLICATE_WINDOW)
    open_events = session.exec(
        select(Event)
        .where(Event.device_id == body.device_id, Event.sound == body.sound)
        .where(Event.status.in_(["active", "escalating", "info"]))
        .order_by(Event.id.desc())
    ).all()
    for existing in open_events:
        if _as_utc(existing.received_at) >= cutoff or existing.status == "escalating":
            return to_out(existing, session, duplicate=True)

    escalates = config.SOUNDS[body.sound]["first_wait"] is not None
    event = Event(
        device_id=body.device_id,
        sound=body.sound,
        confidence=body.confidence,
        ts=body.ts or now(),
        status="active" if escalates else "info",
    )
    session.add(event)
    session.commit()
    session.refresh(event)

    out = to_out(event, session)
    await hub.broadcast({"type": "event_created", "event": out.model_dump(mode="json")})
    if escalates:
        request.app.state.escalation.start(event.id, event.sound)
    return out


@router.post("/{event_id}/ack", response_model=EventOut)
async def ack_event(event_id: int, body: AckIn, request: Request, session: Session = Depends(get_session)):
    event = session.get(Event, event_id)
    if event is None:
        raise HTTPException(404, "event not found")
    if event.status != "acked":
        event.status = "acked"
        event.acked_by = body.by
        event.acked_at = now()
        session.add(event)
        session.commit()
        session.refresh(event)
        request.app.state.escalation.stop(event_id)
        out = to_out(event, session)
        await hub.broadcast({"type": "event_acked", "event": out.model_dump(mode="json")})
        return out
    return to_out(event, session)


@router.get("/{event_id}", response_model=EventOut)
def get_event(event_id: int, session: Session = Depends(get_session)):
    event = session.get(Event, event_id)
    if event is None:
        raise HTTPException(404, "event not found")
    return to_out(event, session)
