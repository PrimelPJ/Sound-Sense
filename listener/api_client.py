"""Talks to the SoundSense API. Retries when Wi-Fi is flaky."""

import logging
import time
from datetime import datetime, timezone

import requests

log = logging.getLogger("soundsense.api")


class Api:
    def __init__(self, base_url: str, retries: int = 4, timeout: float = 5.0) -> None:
        self.base = base_url.rstrip("/")
        self.retries = retries
        self.timeout = timeout
        self.session = requests.Session()

    def _call(self, method: str, path: str, **kwargs):
        delay = 0.5
        for attempt in range(1, self.retries + 1):
            try:
                r = self.session.request(method, self.base + path, timeout=self.timeout, **kwargs)
                if r.status_code < 500:
                    r.raise_for_status()
                    return r.json()
                log.warning("%s %s -> %s (try %d)", method, path, r.status_code, attempt)
            except requests.HTTPError:
                raise
            except requests.RequestException as exc:
                log.warning("%s %s failed: %s (try %d)", method, path, exc, attempt)
            if attempt < self.retries:
                time.sleep(delay)
                delay *= 2
        return None

    def health(self) -> bool:
        try:
            return bool(self._call("GET", "/health"))
        except Exception:
            return False

    def post_event(self, device_id: str, sound: str, confidence: float) -> dict | None:
        body = {
            "device_id": device_id,
            "sound": sound,
            "confidence": confidence,
            "ts": datetime.now(timezone.utc).isoformat(),
        }
        return self._call("POST", "/events", json=body)

    def ack(self, event_id: int, by: str = "device") -> dict | None:
        return self._call("POST", f"/events/{event_id}/ack", json={"by": by})

    def get_event(self, event_id: int) -> dict | None:
        return self._call("GET", f"/events/{event_id}")


# Names Alisha's API expects. Change the right-hand side if hers differ.
ALISHA_NAMES = {
    "smoke_alarm": "smoke alarm",
    "baby_cry": "baby crying",
    "doorbell": "doorbell",
    "kettle": "kettle",
}


class AlishaApi(Api):
    """Talks to Alisha's dashboard API.

    POST /api/events             {"sound": "smoke alarm", "confidence": 0.94}
    POST /api/events/latest/ack  when the button is pressed
    """

    def health(self) -> bool:
        try:
            r = self.session.get(self.base + "/", timeout=self.timeout)
            return r.status_code < 500
        except Exception:
            return False

    def post_event(self, device_id: str, sound: str, confidence: float) -> dict | None:
        body = {"sound": ALISHA_NAMES.get(sound, sound), "confidence": confidence}
        resp = self._call("POST", "/api/events", json=body)
        if resp is None:
            return None
        resp = resp if isinstance(resp, dict) else {}
        # Her API acks "latest", so we don't need her event id.
        return {"id": resp.get("id", "latest"), "status": "active", **resp}

    def ack(self, event_id, by: str = "device") -> dict | None:
        return self._call("POST", "/api/events/latest/ack")

    def get_event(self, event_id) -> dict | None:
        # No status endpoint yet, so a dashboard "I'm OK" can't clear the Arduino.
        return None
