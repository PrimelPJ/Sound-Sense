"""End-to-end tests for events, "I'm OK", escalation and live updates.

Waits are sped up 100x (TIME_SCALE=0.01), so a 60 second wait takes 0.6 seconds.
Run from the server folder:  python -m pytest -q
"""

import os
import tempfile
import time

DB_DIR = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{DB_DIR}/test.db"
os.environ["TIME_SCALE"] = "0.01"
os.environ["SEED_CONTACTS_FILE"] = os.path.join(os.path.dirname(__file__), "..", "seed_contacts.json")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

FIRST = 60 * 0.01  # smoke alarm first wait, scaled
STEP = 60 * 0.01


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def post_event(client, device, sound, conf=0.9):
    return client.post("/events", json={"device_id": device, "sound": sound, "confidence": conf})


def wait_for(client, event_id, check, timeout=5.0):
    end = time.time() + timeout
    while time.time() < end:
        data = client.get(f"/events/{event_id}").json()
        if check(data):
            return data
        time.sleep(0.05)
    return client.get(f"/events/{event_id}").json()


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["ok"]


def test_unknown_sound_rejected(client):
    assert post_event(client, "t-bad", "car_horn").status_code == 422


def test_doorbell_never_escalates(client):
    r = post_event(client, "t-door", "doorbell")
    assert r.status_code == 201
    ev = r.json()
    assert ev["status"] == "info" and ev["escalates"] is False
    time.sleep(FIRST + 0.3)
    assert client.get(f"/events/{ev['id']}").json()["steps"] == []


def test_ack_before_timer_sends_nothing(client):
    ev = post_event(client, "t-ack", "smoke_alarm").json()
    assert ev["status"] == "active"
    r = client.post(f"/events/{ev['id']}/ack", json={"by": "device"})
    assert r.json()["status"] == "acked" and r.json()["acked_by"] == "device"
    time.sleep(FIRST + STEP + 0.3)
    data = client.get(f"/events/{ev['id']}").json()
    assert data["status"] == "acked" and data["steps"] == []


def test_no_response_texts_everyone_in_order(client):
    ev = post_event(client, "t-full", "smoke_alarm").json()
    data = wait_for(client, ev["id"], lambda d: d["status"] == "unanswered")
    assert data["status"] == "unanswered"
    assert [s["role"] for s in data["steps"]] == ["family", "neighbour", "building"]
    assert data["escalation_level"] == 3


def test_ack_mid_escalation_stops_chain(client):
    ev = post_event(client, "t-mid", "smoke_alarm").json()
    data = wait_for(client, ev["id"], lambda d: d["escalation_level"] >= 1)
    assert data["escalation_level"] == 1
    client.post(f"/events/{ev['id']}/ack", json={"by": "dashboard"})
    time.sleep(STEP * 3)
    data = client.get(f"/events/{ev['id']}").json()
    assert data["status"] == "acked"
    assert [s["role"] for s in data["steps"]] == ["family"]


def test_duplicate_returns_same_event(client):
    a = post_event(client, "t-dup", "baby_cry").json()
    b = post_event(client, "t-dup", "baby_cry").json()
    assert a["id"] == b["id"] and b["duplicate"] is True
    client.post(f"/events/{a['id']}/ack", json={"by": "device"})


def test_failed_sms_does_not_stop_chain(client):
    engine = client.app.state.escalation
    original = engine.send_sms

    def broken(to, body):
        raise RuntimeError("provider down")

    engine.send_sms = broken
    try:
        ev = post_event(client, "t-fail", "smoke_alarm").json()
        data = wait_for(client, ev["id"], lambda d: d["status"] == "unanswered")
        assert data["status"] == "unanswered"
        assert len(data["steps"]) == 3 and not any(s["ok"] for s in data["steps"])
    finally:
        engine.send_sms = original


def test_live_feed(client):
    with client.websocket_connect("/live") as ws:
        first = ws.receive_json()
        assert first["type"] == "snapshot"
        ev = post_event(client, "t-live", "smoke_alarm").json()
        seen = []
        while "event_created" not in seen:
            seen.append(ws.receive_json()["type"])
        client.post(f"/events/{ev['id']}/ack", json={"by": "dashboard"})
        while "event_acked" not in seen:
            seen.append(ws.receive_json()["type"])
        assert "escalation_timer" in seen or seen.index("event_acked") > 0
