"""Sends SMS messages through Twilio."""

import logging
import os

from twilio.rest import Client

log = logging.getLogger("soundsense.sms")


def send_sms(to: str, body: str) -> dict:
    """Send an SMS using Twilio's predefined trial Event Notifications template."""

    try:
        account_sid = os.getenv("TWILIO_ACCOUNT_SID")
        api_key = os.getenv("TWILIO_API_KEY")
        api_secret = os.getenv("TWILIO_API_SECRET")
        from_number = os.getenv("TWILIO_PHONE_NUMBER")

        if not all([account_sid, api_key, api_secret, from_number]):
            return {
                "ok": False,
                "note": "Twilio credentials are missing.",
            }

        client = Client(
            api_key,
            api_secret,
            account_sid=account_sid,
        )

        message = client.messages.create(
            body="sms_event_notifications",
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
                f"Twilio accepted Event Notifications template. "
                f"SID: {message.sid}, status: {message.status}"
            ),
        }

    except Exception:
        log.exception("SMS request failed for %s", to)

        return {
            "ok": False,
            "note": "Twilio failed to accept the SMS request. Check server logs.",
        }