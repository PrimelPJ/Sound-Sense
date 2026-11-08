"""SMS helper: writes the alert text and sends it.

Writing the text:
  - A fixed template, so a text always goes out and never invents anything.

Sending the text:
  - If Twilio keys are set it sends a real text.
  - If not, it "mock sends" (prints it and shows it on the dashboard) so the demo still works.

Environment variables:
  TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM  real texts (optional)
"""
import os
from datetime import datetime

sent_messages = []

FRIENDLY_SOUND = {
    "smoke alarm": "smoke alarm",
    "fire alarm": "fire alarm",
    "carbon monoxide alarm": "carbon monoxide alarm",
    "baby crying": "baby crying",
    "doorbell": "doorbell",
    "knocking": "someone knocking",
    "kettle": "kettle whistling",
}

def _facts(event, home_name, wait_seconds):
    return {
        "home_name": home_name,
        "sound": FRIENDLY_SOUND.get(event["sound"], event["sound"]),
        "time": datetime.fromisoformat(event["detected_at"]).strftime("%I:%M %p").lstrip("0"),
        "wait": wait_seconds,
        "urgent": event["urgent"],
    }


def template_message(event, home_name, wait_seconds):
    """Fixed wording. Always works and never invents anything."""
    f = _facts(event, home_name, wait_seconds)
    if f["urgent"]:
        return (f"SoundSense ALERT: {f['home_name']}'s {f['sound']} went off at {f['time']} and they "
                f"haven't responded in {f['wait']} seconds. Please check on them now. "
                f"If you see smoke or fire, call 911.")
    return (f"SoundSense: {f['home_name']}'s home detected a {f['sound']} at {f['time']} and they "
            f"haven't responded in {f['wait']} seconds. You may want to check in.")


def compose_alert_message(event, home_name, wait_seconds):
    """Returns (text, source)."""
    return template_message(event, home_name, wait_seconds), "template"


def send_sms(to, body, written_by=None):
    sid = os.environ.get("TWILIO_ACCOUNT_SID")
    token = os.environ.get("TWILIO_AUTH_TOKEN")
    sender = os.environ.get("TWILIO_FROM")
    record = {"to": to, "body": body, "at": datetime.now().isoformat(timespec="seconds"),
              "written_by": written_by}

    if sid and token and sender:
        try:
            from twilio.rest import Client  # pip install twilio
            msg = Client(sid, token).messages.create(to=to, from_=sender, body=body)
            record.update(mode="twilio", ok=True, sid=msg.sid)
        except Exception as exc:  # keep the demo alive even if a text fails
            record.update(mode="twilio", ok=False, error=str(exc))
    else:
        print(f"[MOCK SMS to {to}] {body}")
        record.update(mode="mock", ok=True)

    sent_messages.append(record)
    return {"mode": record["mode"], "ok": record["ok"], "error": record.get("error")}