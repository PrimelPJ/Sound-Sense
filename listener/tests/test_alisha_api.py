"""Checks the listener sends exactly what Alisha's API expects, using a fake server."""

import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from api_client import AlishaApi  # noqa: E402
from controller import Controller  # noqa: E402
from serial_link import NoArduino  # noqa: E402

received = []
status = {"abc123": "alerting"}  # what her API says about each alert


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(length) or b"null")
        received.append((self.path, body))
        self._json({"id": "abc123", "status": "alerting"})

    def do_GET(self):
        if self.path.startswith("/api/events/"):
            event_id = self.path.rsplit("/", 1)[1]
            self._json({"id": event_id, "status": status[event_id]})
        else:
            self.send_response(200)
            self.end_headers()

    def _json(self, data):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def log_message(self, *a):
        pass


def run_server():
    received.clear()
    status["abc123"] = "alerting"
    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def test_matches_alisha_contract():
    server = run_server()
    try:
        api = AlishaApi(f"http://127.0.0.1:{server.server_port}")
        assert api.health()
        link = NoArduino()
        ctrl = Controller(api, link, "home-01")
        ctrl.on_detect("smoke_alarm", 0.94)
        link.press_button()
        ctrl.tick()
        assert received == [
            ("/api/events", {"sound": "smoke alarm", "confidence": 0.94}),
            ("/api/events/abc123/ack", None),
        ]
    finally:
        server.shutdown()


def test_dashboard_ok_clears_arduino():
    server = run_server()
    try:
        api = AlishaApi(f"http://127.0.0.1:{server.server_port}")
        link = NoArduino()
        ctrl = Controller(api, link, "home-01", poll_every=0)
        ctrl.on_detect("smoke_alarm", 0.94)
        assert ctrl.active == {"abc123": "smoke_alarm"}
        status["abc123"] = "acknowledged"   # "I'm OK" pressed on the dashboard
        ctrl.tick()
        assert ctrl.active == {}
    finally:
        server.shutdown()
