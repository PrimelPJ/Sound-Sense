"""Sends text messages.

OWNER: Alisha. Replace the body of send_sms with Twilio or AWS SNS.
Keep the same name, inputs and return value so the escalation engine keeps working.

Until then it only prints the message, so the whole system can be tested without
an SMS account.
"""

import logging

log = logging.getLogger("soundsense.sms")


def send_sms(to: str, body: str) -> dict:
    """Send one text. Return {"ok": True/False, "note": "..."}. Must not raise."""
    log.warning("SMS (not really sent) to %s: %s", to, body)
    return {"ok": True, "note": "printed only, SMS provider not set up yet"}
