"""Tests for detection rules, sound mapping and the controller. No mic, model or board needed.

Run from the listener folder:  python -m pytest -q
"""

import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from controller import Controller  # noqa: E402
from detector import Detector  # noqa: E402
from model import group_indices, sound_scores  # noqa: E402
from serial_link import NoArduino  # noqa: E402


class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


def test_needs_hits_in_a_row():
    d = Detector({"smoke_alarm": 0.3}, hits_needed=2, cooldown=10, clock=Clock())
    assert d.update({"smoke_alarm": 0.9}) == []
    assert d.update({"smoke_alarm": 0.1}) == []  # streak broken
    assert d.update({"smoke_alarm": 0.9}) == []
    assert d.update({"smoke_alarm": 0.8}) == [("smoke_alarm", 0.8)]


def test_cooldown_and_reset():
    clock = Clock()
    d = Detector({"smoke_alarm": 0.3}, hits_needed=1, cooldown=10, clock=clock)
    assert d.update({"smoke_alarm": 0.9})
    clock.t = 5
    assert d.update({"smoke_alarm": 0.9}) == []  # still cooling down
    d.reset("smoke_alarm")
    assert d.update({"smoke_alarm": 0.9})  # caught again after "I'm OK"
    clock.t = 30
    assert d.update({"smoke_alarm": 0.9})


def test_group_mapping_takes_max_and_skips_unknown_names():
    names = ["Speech", "Smoke detector, smoke alarm", "Fire alarm", "Doorbell", "Baby cry, infant cry"]
    groups = group_indices(names)
    assert groups["smoke_alarm"] == [1, 2]
    assert groups["kettle"] == []  # none of its names are in this fake list
    scores = sound_scores(np.array([0.9, 0.2, 0.6, 0.1, 0.0]), groups)
    assert scores["smoke_alarm"] == 0.6 and scores["kettle"] == 0.0


class FakeApi:
    def __init__(self):
        self.events = {}
        self.next_id = 1

    def post_event(self, device_id, sound, confidence):
        escalates = sound in ("smoke_alarm", "baby_cry")
        ev = {"id": self.next_id, "sound": sound, "status": "active" if escalates else "info"}
        self.events[self.next_id] = ev
        self.next_id += 1
        return dict(ev)

    def ack(self, event_id, by="device"):
        self.events[event_id].update(status="acked", acked_by=by)
        return self.events[event_id]

    def get_event(self, event_id):
        return dict(self.events[event_id])


class RecordingLink(NoArduino):
    def __init__(self):
        super().__init__()
        self.sent = []

    def send(self, line):
        self.sent.append(line)


def test_button_acks_open_alerts_and_clears():
    api, link = FakeApi(), RecordingLink()
    c = Controller(api, link, "home-01")
    c.on_detect("smoke_alarm", 0.9)
    c.on_detect("doorbell", 0.8)  # heads up only, not tracked
    assert c.active == {1: "smoke_alarm"}
    link.press_button()
    c.tick()
    assert api.events[1]["status"] == "acked" and c.active == {}
    assert link.sent == ["ALERT smoke_alarm", "ALERT doorbell", "CLEAR"]


def test_dashboard_ok_clears_device_and_shows_next_alert():
    api, link = FakeApi(), RecordingLink()
    c = Controller(api, link, "home-01", poll_every=0)
    c.on_detect("smoke_alarm", 0.9)
    c.on_detect("baby_cry", 0.9)
    api.ack(1, by="dashboard")  # someone pressed OK on the dashboard
    c.tick()
    assert c.active == {2: "baby_cry"}
    assert link.sent[-2:] == ["CLEAR", "ALERT baby_cry"]


def test_api_down_still_alerts_locally():
    class DownApi(FakeApi):
        def post_event(self, *a):
            return None

    link = RecordingLink()
    c = Controller(DownApi(), link, "home-01")
    assert c.on_detect("smoke_alarm", 0.9) is None
    assert link.sent == ["ALERT smoke_alarm"]


def test_help_button_texts_open_alert_now():
    class EscApi(FakeApi):
        escalated = []

        def escalate(self, event_id):
            self.escalated.append(event_id)
            self.events[event_id]["status"] = "escalating"
            return dict(self.events[event_id])

    api, link = EscApi(), RecordingLink()
    c = Controller(api, link, "home-01")
    c.on_detect("smoke_alarm", 0.9)
    link.press_help()
    c.tick()
    assert api.escalated == [1] and len(api.events) == 1  # no extra help request


def test_help_button_with_nothing_going_makes_help_request():
    class EscApi(FakeApi):
        escalated = []

        def escalate(self, event_id):
            self.escalated.append(event_id)
            return dict(self.events[event_id])

    api, link = EscApi(), RecordingLink()
    c = Controller(api, link, "home-01")
    link.press_help()
    c.tick()
    assert api.events[1]["sound"] == "help" and api.escalated == [1]
    assert c.active == {1: "help"}
    link.press_button()  # "I'm OK" clears it
    c.tick()
    assert c.active == {} and link.sent == ["CLEAR"]
