"""Glue between the detector, the Arduino and the API.

- A sound fires -> Arduino shows the alert right away, then the event goes to the API.
  The light still works if the internet is down.
- "I'm OK" button on the Arduino -> every open alert is marked OK on the API,
  which stops escalation, and the Arduino clears.
- "I'm OK" pressed on the dashboard -> we notice by checking the API every couple
  of seconds and clear the Arduino too.
- "Get help" button on the Arduino -> every open alert is texted to backup contacts
  right away. With no alert going, a "help request" is made and texted instead.
"""

import logging
import time

from sounds import ESCALATING, PRIORITY

log = logging.getLogger("soundsense.controller")


class Controller:
    def __init__(self, api, link, device_id: str, detector=None, poll_every: float = 2.0) -> None:
        self.api = api
        self.link = link
        self.device_id = device_id
        self.detector = detector
        self.poll_every = poll_every
        self.active: dict[int, str] = {}  # event id -> sound, for alerts waiting on "I'm OK"
        self._last_poll = 0.0

    # ---- inputs ----------------------------------------------------------

    def on_detect(self, sound: str, confidence: float) -> dict | None:
        log.info("HEARD %s (%.2f)", sound, confidence)
        self.link.send(f"ALERT {sound}")
        try:
            event = self.api.post_event(self.device_id, sound, confidence)
        except Exception as exc:
            log.error("could not send event: %s", exc)
            event = None
        if event is None:
            log.warning("API unreachable, alert shown locally only")
            return None
        if sound in ESCALATING and event["status"] in ("active", "escalating"):
            self.active[event["id"]] = sound
        return event

    def on_button(self) -> None:
        log.info("I'M OK pressed on the device")
        for event_id in list(self.active):
            try:
                self.api.ack(event_id, by="device")
            except Exception as exc:
                log.error("could not mark event %s OK: %s", event_id, exc)
        for sound in set(self.active.values()):
            self._reset(sound)
        self.active.clear()
        self.link.send("CLEAR")

    def on_escalate(self) -> None:
        log.warning("GET HELP pressed on the device")
        sent = False
        for event_id in list(self.active):
            try:
                sent = self.api.escalate(event_id) is not None or sent
            except Exception as exc:
                log.error("could not escalate event %s: %s", event_id, exc)
        if sent:
            return
        # Nothing open (or it could not be texted): make a help request and text it now.
        try:
            event = self.api.post_event(self.device_id, "help", 1.0)
        except Exception as exc:
            log.error("could not send help request: %s", exc)
            event = None
        if event is None:
            log.warning("API unreachable, help shown locally only")
            return
        self.active[event["id"]] = "help"
        try:
            self.api.escalate(event["id"])
        except Exception as exc:
            log.error("could not escalate help request: %s", exc)

    # ---- loop ------------------------------------------------------------

    def tick(self) -> None:
        """Call often. Handles Arduino messages and checks for dashboard "I'm OK"."""
        while (line := self.link.read()) is not None:
            if line == "ACK":
                self.on_button()
            elif line == "ESCALATE":
                self.on_escalate()
            elif line == "READY":
                log.info("Arduino restarted")
                self._show_top()
        if self.active and time.monotonic() - self._last_poll >= self.poll_every:
            self._last_poll = time.monotonic()
            self.poll()

    def poll(self) -> None:
        cleared = False
        for event_id, sound in list(self.active.items()):
            try:
                event = self.api.get_event(event_id)
            except Exception:
                event = None
            if event and event["status"] == "acked":
                log.info("event %s marked OK by %s", event_id, event.get("acked_by") or "the dashboard")
                del self.active[event_id]
                self._reset(sound)
                cleared = True
        if cleared:
            self.link.send("CLEAR")
            self._show_top()

    # ---- helpers ---------------------------------------------------------

    def _show_top(self) -> None:
        """If alerts are still open, put the most important one back on the device."""
        if self.active:
            top = max(self.active.values(), key=lambda s: PRIORITY.get(s, 0))
            self.link.send(f"ALERT {top}")

    def _reset(self, sound: str) -> None:
        if self.detector is not None:
            self.detector.reset(sound)
