"""Event log for the dashboard.

OWNER: Alisha.

Add here:
  GET /events  -> list of past events, newest first (use routes.events.to_out
                  so each item has the same shape as the live alerts)
                  Nice extras: ?limit=50, ?sound=smoke_alarm, ?device_id=home-01

Note: GET /events/{id}, POST /events and POST /events/{id}/ack already live in
routes/events.py. Define this route as @router.get("/events") here.
"""

from fastapi import APIRouter

router = APIRouter(tags=["log"])
