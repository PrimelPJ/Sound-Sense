"""Escalation engine.

When a serious sound (smoke alarm, baby crying) is heard, a timer starts.
If nobody presses "I'm OK" in time, SoundSense texts family, then a neighbour,
then the building, waiting between each group. Pressing "I'm OK" at any point
stops it.

Each event runs as its own asyncio task, so many homes can escalate at once.
"""

import asyncio
import logging
from typing import Awaitable, Callable, Optional

from sqlmodel import Session, select

from . import config
from .models import Contact, EscalationStep, Event, now

log = logging.getLogger("soundsense.escalation")

Broadcast = Callable[[dict], Awaitable[None]]
SendSms = Callable[[str, str], dict]


class EscalationEngine:
    def __init__(self, engine, broadcast: Broadcast, send_sms: SendSms) -> None:
        self.engine = engine  # SQLAlchemy engine
        self.broadcast = broadcast
        self.send_sms = send_sms
        self.tasks: dict[int, asyncio.Task] = {}

    # ---- public ----------------------------------------------------------

    def start(self, event_id: int, sound: str) -> bool:
        """Start the timer for an event. Returns False if this sound never escalates."""
        first_wait = config.SOUNDS.get(sound, {}).get("first_wait")
        if first_wait is None or event_id in self.tasks:
            return False
        task = asyncio.create_task(self._run(event_id, sound, first_wait))
        self.tasks[event_id] = task
        task.add_done_callback(lambda _t, eid=event_id: self.tasks.pop(eid, None))
        return True

    def stop(self, event_id: int) -> bool:
        """Stop the timer for an event (someone pressed "I'm OK")."""
        task = self.tasks.pop(event_id, None)
        if task is None:
            return False
        task.cancel()
        return True

    def stop_all(self) -> None:
        for event_id in list(self.tasks):
            self.stop(event_id)

    # ---- internals -------------------------------------------------------

    async def _sleep(self, seconds: float) -> None:
        await asyncio.sleep(seconds * config.TIME_SCALE)

    def _is_acked(self, event_id: int) -> bool:
        with Session(self.engine) as s:
            event = s.get(Event, event_id)
            return event is None or event.status == "acked"

    async def _run(self, event_id: int, sound: str, first_wait: int) -> None:
        label = config.SOUNDS[sound]["label"]
        try:
            await self.broadcast({
                "type": "escalation_timer",
                "event_id": event_id,
                "next_role": config.ESCALATION_ORDER[0],
                "seconds": first_wait * config.TIME_SCALE,
            })
            await self._sleep(first_wait)

            levels = config.ESCALATION_ORDER
            for level, role in enumerate(levels, start=1):
                if self._is_acked(event_id):
                    return

                minutes = max(1, round((first_wait + (level - 1) * config.STEP_WAIT) / 60))
                body = (
                    f"SoundSense: {label} at {config.HOME_NAME} and nobody has "
                    f"responded for about {minutes} min. Please check on them."
                )
                steps = await self._text_role(event_id, level, role, body)

                with Session(self.engine) as s:
                    event = s.get(Event, event_id)
                    if event is None or event.status == "acked":
                        return
                    event.status = "escalating"
                    event.escalation_level = level
                    s.add(event)
                    s.commit()

                is_last = level == len(levels)
                await self.broadcast({
                    "type": "escalation_step",
                    "event_id": event_id,
                    "level": level,
                    "role": role,
                    "contacts": steps,
                    "next_role": None if is_last else levels[level],
                    "seconds": None if is_last else config.STEP_WAIT * config.TIME_SCALE,
                })

                # No one in this group: move straight to the next one.
                if not is_last and any(st["sent"] for st in steps):
                    await self._sleep(config.STEP_WAIT)

            with Session(self.engine) as s:
                event = s.get(Event, event_id)
                if event is not None and event.status != "acked":
                    event.status = "unanswered"
                    s.add(event)
                    s.commit()
                    await self.broadcast({"type": "escalation_done", "event_id": event_id})
        except asyncio.CancelledError:
            log.info("escalation stopped for event %s", event_id)
            raise
        except Exception:
            log.exception("escalation failed for event %s", event_id)

    async def _text_role(self, event_id: int, level: int, role: str, body: str) -> list[dict]:
        with Session(self.engine) as s:
            contacts = s.exec(
                select(Contact).where(Contact.role == role).order_by(Contact.position, Contact.id)
            ).all()
            contacts = [(c.name, c.phone) for c in contacts]

        results = []
        if not contacts:
            with Session(self.engine) as s:
                s.add(EscalationStep(event_id=event_id, level=level, role=role,
                                     ok=False, note="no contacts in this group"))
                s.commit()
            return [{"name": None, "sent": False, "note": "no contacts in this group"}]

        for name, phone in contacts:
            # SMS clients are usually blocking, so run them off the event loop.
            result = await asyncio.to_thread(self._safe_send, phone, body)
            with Session(self.engine) as s:
                s.add(EscalationStep(event_id=event_id, level=level, role=role,
                                     contact_name=name, phone=phone,
                                     ok=result["ok"], note=result.get("note"), sent_at=now()))
                s.commit()
            results.append({"name": name, "sent": result["ok"], "note": result.get("note")})
        return results

    def _safe_send(self, phone: str, body: str) -> dict:
        try:
            result = self.send_sms(phone, body)
            return {"ok": bool(result.get("ok")), "note": result.get("note")}
        except Exception as exc:  # never let one failed text stop the chain
            log.exception("SMS to %s failed", phone)
            return {"ok": False, "note": f"error: {exc}"}
