import os          # lets us read settings like ESCALATE_AFTER
import threading   # lets us use a "lock" so two requests don't clash
import time        # gives us the current time in seconds
import uuid        # makes a random ID for each alert
from datetime import datetime   # gives us the date and time as text

from flask import Flask, jsonify, request   # request = the data someone sent us

# Create the web server
app = Flask(__name__)

# How many seconds someone has to press "I'm OK" (60 unless we change it)
ESCALATE_AFTER_SECONDS = int(os.environ.get("ESCALATE_AFTER", "60"))
# Sounds that are dangerous (these get texted if nobody responds)
URGENT_SOUNDS = {"smoke alarm", "fire alarm", "carbon monoxide alarm", "baby crying"}

# A lock: only one request can change the alerts list at a time
lock = threading.Lock()

# The list of all alerts. Newest one goes first.
events = []
# Gives the time right now as text, like "2026-11-07T16:35:05"
def now_iso(): 
    return datetime.now().isoformat(timespec="seconds") 
# Finds one alert by its ID. "latest" means the newest alert still waiting for a response.
def find_event(event_id):
    if event_id == "latest":
        return next((e for e in events if e["status"] == "alerting"), None)
    return next((e for e in events if e["id"] == event_id), None)


# Home page: just shows the server is on
@app.get("/")
def home():
    return "SoundSense is running"


# Shows the list of alerts (the dashboard and Marwan's listener read this)
@app.get("/api/events")
def list_events():
    with lock:                      # lock the list while we read it
        out = []
        for e in events[:50]:       # only the 50 newest alerts
            item = dict(e)          # make a copy so we don't change the real one
            # how many seconds are left before a text goes out (0 if it's already done)
            if e["status"] == "alerting":
                item["seconds_left"] = max(0, int(e["deadline"] - time.time()))
            else:
                item["seconds_left"] = 0
            out.append(item)
    # send the list back as JSON
    return jsonify(events=out, escalate_after=ESCALATE_AFTER_SECONDS)

# Receives a new alert from the listener, like {"sound": "smoke alarm", "confidence": 0.94}
@app.post("/api/events")
def create_event():
    data = request.get_json(silent=True) or {}          # what was sent (empty if nothing)
    sound = str(data.get("sound", "")).strip().lower()  # the sound name, cleaned up

    # Check the input so bad data can't crash the server
    if not sound:
        return jsonify(error="'sound' is required"), 400   # 400 = "you sent something wrong"
    try:
        confidence = float(data.get("confidence", 0))      # how sure the AI is (0 to 1)
    except (TypeError, ValueError):
        return jsonify(error="'confidence' must be a number between 0 and 1"), 400
    confidence = round(max(0.0, min(confidence, 1.0)), 2)  # keep it between 0 and 1

    with lock:  # lock the list while we change it
        # Same sound still waiting? Don't make a duplicate (an alarm beeps for minutes)
        open_alert = next((e for e in events if e["status"] == "alerting" and e["sound"] == sound), None)
        if open_alert:
            open_alert["confidence"] = max(open_alert["confidence"], confidence)
            open_alert["repeats"] += 1
            return jsonify(open_alert), 200

        # Build the new alert
        event = {
            "id": uuid.uuid4().hex[:8],                 # random 8-letter ID
            "sound": sound,
            "confidence": confidence,
            "urgent": sound in URGENT_SOUNDS,           # True if it's dangerous
            "source": data.get("source", "laptop"),     # who sent it
            "status": "alerting",                       # alerting -> acknowledged or escalated
            "detected_at": now_iso(),                   # when it happened
            "deadline": time.time() + ESCALATE_AFTER_SECONDS,  # when the text goes out
            "acknowledged_at": None,                    # filled in when "I'm OK" is pressed
            "escalated_at": None,                       # filled in when the text goes out
            "repeats": 0,                               # times the same sound came again
            "notified": [],                             # who got texted
            "message_source": None,                     # where the text came from
        }
        events.insert(0, event)  # put the new alert at the front
    return jsonify(event), 201   # 201 = "created"

# Shows one alert. The listener checks this so "I'm OK" on the dashboard turns the Arduino off.
@app.get("/api/events/<event_id>")
def get_event(event_id):
    with lock:
        event = find_event(event_id)
        if not event:
            return jsonify(error="No matching alert"), 404   # 404 = "not found"
        item = dict(event)
        if event["status"] == "alerting":
            item["seconds_left"] = max(0, int(event["deadline"] - time.time()))
        else:
            item["seconds_left"] = 0
        return jsonify(item)


# "I'm OK" was pressed (the Arduino button or the dashboard button)
@app.post("/api/events/<event_id>/ack")
def acknowledge(event_id):
    with lock:
        event = find_event(event_id)
        if not event:
            return jsonify(error="No matching alert"), 404
        if event["status"] == "alerting":            # only if it's still waiting
            event["status"] = "acknowledged"         # mark it as answered
            event["acknowledged_at"] = now_iso()     # remember when
        return jsonify(event)

# Start the server when we run "python app.py"
if __name__ == "__main__":
    # host="0.0.0.0" lets other laptops (Marwan's) connect, port 5000 is the address
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")))  

