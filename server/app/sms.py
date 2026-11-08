"""Sends SMS messages through Twilio.

If the Twilio settings are not in server/.env, the text is only printed, so the
whole system can still be tested without an SMS account.
"""

import logging
import os

from twilio.rest import Client

log = logging.getLogger("soundsense.sms")


def send_sms(to: str, body: str) -> dict:
    """Send one text. Return {"ok": True/False, "note": "..."}. Must not raise."""

    try:
        account_sid = os.getenv("TWILIO_ACCOUNT_SID")
        api_key = os.getenv("TWILIO_API_KEY")
        api_secret = os.getenv("TWILIO_API_SECRET")
        auth_token = os.getenv("TWILIO_AUTH_TOKEN")  # the dashboard's setting, works here too
        from_number = os.getenv("TWILIO_PHONE_NUMBER") or os.getenv("TWILIO_FROM")

        if api_key and api_secret:
            login = (api_key, api_secret)
        elif auth_token:
            login = (account_sid, auth_token)
        else:
            login = None

        if not (account_sid and login and from_number):
            log.warning("SMS (not really sent) to %s: %s", to, body)
            return {"ok": True, "note": "printed only, Twilio settings not set"}

        client = Client(
            *login,
            account_sid=account_sid,
        )

        message = client.messages.create(
            body=body,
            from_=from_number,
            to=to,
        )

        log.info(
            "Twilio accepted SMS to %s. SID: %s, status: %s",
            to,
            message.sid,
            message.status,
        )

        return {
            "ok": True,
            "note": (
                f"Twilio accepted the SMS. "
                f"SID: {message.sid}, status: {message.status}"
            ),
        }

    except Exception:
        log.exception("SMS request failed for %s", to)

        return {
            "ok": False,
            "note": "Twilio failed to accept the SMS request. Check server logs.",
        }
