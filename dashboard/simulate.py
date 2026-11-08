"""Pretend to be the laptop listener + Arduino button, so the dashboard can be tested alone.

Start the server first (python app.py), then in a second terminal:
  python simulate.py

Keys:  s = smoke alarm   d = doorbell   b = baby crying   k = knocking
       o = press "I'm OK"   q = quit
"""
import json
import os
import urllib.error
import urllib.request

SERVER = os.environ.get("SOUNDSENSE_URL", "http://localhost:5000")
SOUNDS = {"s": ("smoke alarm", 0.94), "d": ("doorbell", 0.88), "b": ("baby crying", 0.81), "k": ("knocking", 0.77)}


def post(path, body=None):
    req = urllib.request.Request(SERVER + path, data=json.dumps(body or {}).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as err:
        return err.code, json.loads(err.read() or b"{}")
    except urllib.error.URLError:
        return None, {"error": f"Can't reach {SERVER}. Is app.py running?"}


def main():
    print(__doc__)
    while True:
        key = input("> ").strip().lower()[:1]
        if key == "q":
            break
        if key in SOUNDS:
            sound, conf = SOUNDS[key]
            status, data = post("/api/events", {"sound": sound, "confidence": conf, "source": "simulator"})
            print(f"Sent {sound} ({int(conf * 100)}%) -> {status} {data.get('error', '')}")
        elif key == "o":
            status, data = post("/api/events/latest/ack")
            print("I'm OK pressed ->", "acknowledged" if status == 200 else data.get("error"))
        else:
            print("Use s, d, b, k, o or q")


if __name__ == "__main__":
    main()
    