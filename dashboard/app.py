# Tools we need
import os          # lets us read settings like ESCALATE_AFTER
import threading   # lets us use a "lock" so two requests don't clash
import time        # gives us the current time in seconds

from flask import Flask, jsonify   # Flask = web server, jsonify = sends data back as JSON

# Create the web server
app = Flask(__name__)

# How many seconds someone has to press "I'm OK" (60 unless we change it)
ESCALATE_AFTER_SECONDS = int(os.environ.get("ESCALATE_AFTER", "60"))

# A lock: only one request can change the alerts list at a time
lock = threading.Lock()

# The list of all alerts. Newest one goes first.
events = []


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


# Start the server when we run "python app.py"
if __name__ == "__main__":
    # host="0.0.0.0" lets other laptops (Marwan's) connect, port 5000 is the address
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000"))) 

    