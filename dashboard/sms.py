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
    "glass breaking": "glass breaking",
    "baby crying": "baby crying",
    "emergency siren": "emergency siren",
    "doorbell": "doorbell",
    "phone ringing": "phone ringing",
    "kettle": "kettle whistling",
    "help request": "help request",
}

# Extra advice added to urgent texts, so the contact knows what to do.
ADVICE = {
    "smoke alarm": "If you see smoke or fire, call 911.",
    "fire alarm": "If you see smoke or fire, call 911.",
    "carbon monoxide alarm": "Get them out to fresh air and call 911.",
    "glass breaking": "It could be a fall or a break-in. If you can't reach them, call 911.",
}

def _facts(event, home_name, wait_seconds):
    return {
        "home_name": home_name,
        "sound": FRIENDLY_SOUND.get(event["sound"], event["sound"]),
        "time": datetime.fromisoformat(event["detected_at"]).strftime("%I:%M %p").lstrip("0"),
        "wait": wait_seconds,
        "urgent": event["urgent"],
        "advice": ADVICE.get(event["sound"], ""),
    }
            

def template_message(event, home_name, wait_seconds):
    """Fixed wording. Always works and never invents anything."""
    f = _facts(event, home_name, wait_seconds)
    if event["sound"] == "help request" or event.get("escalated_by") == "button":
        when = datetime.fromisoformat(event.get("escalated_at") or event["detected_at"])
        during = "" if event["sound"] == "help request" else f" during a {f['sound']}"
        text = (f"SoundSense ALERT: {f['home_name']} pressed the help button{during} at "
                f"{when.strftime('%I:%M %p').lstrip('0')}. Please check on them now.")
        return f"{text} {f['advice']}".strip()
    if f["urgent"]:
        text = (f"SoundSense ALERT: {f['sound'].capitalize()} at {f['home_name']}'s home at {f['time']}, "
                f"and no response in {f['wait']} seconds. Please check on them now.")
        return f"{text} {f['advice']}".strip()
    return (f"SoundSense: {f['sound'].capitalize()} at {f['home_name']}'s home at {f['time']}, "
            f"and no response in {f['wait']} seconds. You may want to check in.") 


def compose_alert_message(event, home_name, wait_seconds):
    """Returns (text, source)."""
    return template_message(event, home_name, wait_seconds), "template"


def send_sms(to, body, written_by=None):
    sid = os.environ.get("TWILIO_ACCOUNT_SID")
    token = os.environ.get("TWILIO_AUTH_TOKEN")
    api_key = os.environ.get("TWILIO_API_KEY")        # an API key and secret work instead of the token
    api_secret = os.environ.get("TWILIO_API_SECRET")
    sender = os.environ.get("TWILIO_FROM") or os.environ.get("TWILIO_PHONE_NUMBER")
    record = {"to": to, "body": body, "at": datetime.now().isoformat(timespec="seconds"),
              "written_by": written_by}

    if sid and sender and (token or (api_key and api_secret)):
        try:
            from twilio.rest import Client  # pip install twilio
            client = Client(api_key, api_secret, sid) if api_key and api_secret else Client(sid, token)
            try:
                msg = client.messages.create(to=to, from_=sender, body=body)
            except Exception as exc:
                # Trial accounts may only send Twilio's predefined templates, so send that instead.
                if "template" not in str(exc).lower():
                    raise
                template = os.environ.get("TWILIO_TRIAL_TEMPLATE", "sms_event_notifications")
                msg = client.messages.create(to=to, from_=sender, body=template)
                record["note"] = f"trial account, sent Twilio template '{template}' instead of the full text"
            record.update(mode="twilio", ok=True, sid=msg.sid)
        except Exception as exc:  # keep the demo alive even if a text fails
            record.update(mode="twilio", ok=False, error=str(exc))
    else:
        print(f"[MOCK SMS to {to}] {body}")
        record.update(mode="mock", ok=True)

    sent_messages.append(record)
    return {"mode": record["mode"], "ok": record["ok"], "error": record.get("error")}