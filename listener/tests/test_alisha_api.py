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


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(length) or b"null")
        received.append((self.path, body))
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"ok": true}')

    def do_GET(self):
        self.send_response(200)
        self.end_headers()

    def log_message(self, *a):
        pass


def test_matches_alisha_contract():
    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
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
            ("/api/events/latest/ack", None),
        ]
    finally:
        server.shutdown()
