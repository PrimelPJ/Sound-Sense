import os          # lets us read settings like ESCALATE_AFTER
import threading   # lets us use a "lock" so two requests don't clash
import time        # gives us the current time in seconds
import uuid        # makes a random ID for each alert
from datetime import datetime   # gives us the date and time as text
import json        # saves contacts to a file

# Load settings like Twilio keys from dashboard/.env, if there is one (it is never committed)
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
except ImportError:   # python-dotenv not installed: settings come from the terminal instead
    pass

from flask import Flask, jsonify, render_template, request   # render_template = shows an HTML page
from sms import compose_alert_message, send_sms, sent_messages   # writes and sends the texts

# Create the web server
app = Flask(__name__)

# How many seconds someone has to press "I'm OK" (60 unless we change it)
ESCALATE_AFTER_SECONDS = int(os.environ.get("ESCALATE_AFTER", "60"))
# Sounds that are dangerous (these get texted if nobody responds)
URGENT_SOUNDS = {"smoke alarm", "fire alarm", "carbon monoxide alarm", "glass breaking", "baby crying",
                 "help request"}
# Set AUTO_ESCALATE=0 if the listener should decide when to text instead
AUTO_ESCALATE = os.environ.get("AUTO_ESCALATE", "1") == "1"
# After a text goes out, the same sound within this many seconds counts as the same alert
# (an alarm can keep beeping for minutes, and we don't want to text people again and again)
REPEAT_WINDOW_SECONDS = int(os.environ.get("REPEAT_WINDOW", "300"))
# The person's name used in the texts
HOME_NAME = os.environ.get("HOME_NAME", "Maria")
# Where backup contacts are saved so they survive a restart
CONTACTS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "contacts.json")

# A lock: only one request can change the alerts list at a time
lock = threading.Lock()

# The list of all alerts. Newest one goes first.
events = []
# Loads saved contacts, or starts with one demo neighbour
def load_contacts():
    try:
        with open(CONTACTS_FILE) as fh:
            data = json.load(fh)
            if isinstance(data, list):
                return data
    except (OSError, ValueError):
        pass
    return [{"id": "c1", "name": "Neighbour (demo)", "phone": "+15875550101", "relation": "Neighbour"}]


# Saves contacts to contacts.json (only call this while holding the lock)
def save_contacts():
    try:
        with open(CONTACTS_FILE, "w") as fh:
            json.dump(contacts, fh, indent=2)
    except OSError as exc:
        print(f"[Could not save contacts] {exc}")


contacts = load_contacts()  # the backup contacts
# Gives the time right now as text, like "2026-11-07T16:35:05"
def now_iso(): 
    return datetime.now().isoformat(timespec="seconds") 
# Finds one alert by its ID. "latest" means the newest alert still waiting for a response.
def find_event(event_id):
    if event_id == "latest":
        return next((e for e in events if e["status"] == "alerting"), None)
    return next((e for e in events if e["id"] == event_id), None)
# Marks an alert as escalated so it only gets texted once (only call this while holding the lock)
def claim_for_escalation(event):
    if event["status"] != "alerting":
        return None
    event["status"] = "escalated"
    event["escalated_at"] = now_iso()
    return dict(event), [dict(c) for c in contacts]


# Writes and sends the texts. Runs without the lock because texting can be slow.
def run_escalation(event_snapshot, contact_list):
    body, source = compose_alert_message(event_snapshot, HOME_NAME, ESCALATE_AFTER_SECONDS)
    notified = []
    for c in contact_list:
        result = send_sms(c["phone"], body, written_by=source)
        notified.append({"name": c["name"], "phone": c["phone"], "message": body, "written_by": source, **result})
    with lock:  # save who got texted back onto the alert
        live = find_event(event_snapshot["id"])
        if live:
            live["notified"] = notified
            live["message_source"] = source


# Starts texting in the background so the server doesn't freeze (only call this while holding the lock)
def escalate_in_background(event):
    claimed = claim_for_escalation(event)
    if claimed:
        threading.Thread(target=run_escalation, args=claimed, daemon=True).start()


# Runs forever: every second, checks for alerts whose time ran out
def escalation_loop():
    while True:
        time.sleep(1)
        if not AUTO_ESCALATE:
            continue
        with lock:
            for e in events:
                if e["status"] == "alerting" and time.time() >= e["deadline"]:
                    if e["urgent"]:
                        escalate_in_background(e)
                    else:
                        e["status"] = "info"   # doorbell, kettle: heads up only, nobody gets texted



# The dashboard page (templates/index.html)
@app.get("/")
def dashboard():
    return render_template("index.html", home_name=HOME_NAME)


# Shows the server's settings, so we can check it's set up right
@app.get("/api/health")
def health():
    return jsonify(ok=True, escalate_after=ESCALATE_AFTER_SECONDS, auto_escalate=AUTO_ESCALATE,
                   real_sms=bool(os.environ.get("TWILIO_ACCOUNT_SID") and
                                 (os.environ.get("TWILIO_FROM") or os.environ.get("TWILIO_PHONE_NUMBER"))))


# Shows the list of alerts (the dashboard and the listener read this)
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
        open_alert = next((e for e in events if e["sound"] == sound and (
            e["status"] == "alerting" or
            (e["status"] == "escalated" and e["escalated_at"] and
             time.time() - datetime.fromisoformat(e["escalated_at"]).timestamp() < REPEAT_WINDOW_SECONDS))), None)
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

# Texts the backup contacts right away ("Skip timer" demo button, or the Arduino "Get help" button)
@app.post("/api/events/<event_id>/escalate")
def escalate_now(event_id):
    data = request.get_json(silent=True) or {}
    with lock:
        event = find_event(event_id)
        if not event:
            return jsonify(error="No matching alert"), 404
        if data.get("by") == "button" and event["status"] == "alerting":
            event["escalated_by"] = "button"   # the text says they pressed "Get help"
        escalate_in_background(event)
        return jsonify(event)
# Shows all backup contacts 
@app.get("/api/contacts")
def list_contacts():
    with lock:
        return jsonify(contacts=contacts)
   # Clears the alerts and texts between demo runs (contacts are kept)
@app.post("/api/reset")
def reset():
    with lock:
        events.clear()
        sent_messages.clear()
    return jsonify(ok=True)


# Adds a backup contact, like {"name": "Mom", "phone": "+15875550199", "relation": "Family"}
@app.post("/api/contacts")
def add_contact():
    data = request.get_json(silent=True) or {}
    name = str(data.get("name", "")).strip()
    phone = str(data.get("phone", "")).strip()
    if not name or not phone:   # both are needed
        return jsonify(error="Name and phone are both required"), 400
    contact = {"id": uuid.uuid4().hex[:8], "name": name, "phone": phone,
               "relation": str(data.get("relation", "")).strip()}
    with lock:
        contacts.append(contact)
        save_contacts()          # keep it after a restart
    return jsonify(contact), 201


# Removes a backup contact by its ID
@app.delete("/api/contacts/<contact_id>")
def delete_contact(contact_id):
    with lock:
        before = len(contacts)
        contacts[:] = [c for c in contacts if c["id"] != contact_id]   # keep everyone except this one
        if len(contacts) == before:
            return jsonify(error="Contact not found"), 404
        save_contacts()
    return jsonify(ok=True)


# Shows every text that was sent, for the demo
@app.get("/api/messages")
def list_messages():
    return jsonify(messages=sent_messages[-20:])


# Start the timer that checks for alerts nobody answered
threading.Thread(target=escalation_loop, daemon=True).start()
# Start the server when we run "python app.py"
if __name__ == "__main__":
    # host="0.0.0.0" lets other laptops (the listener) connect, port 5000 is the address
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")))  

