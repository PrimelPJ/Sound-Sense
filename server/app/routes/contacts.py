"""Contacts for escalation.

OWNER: Alisha.

Add here (uses the Contact table in models.py):
  GET    /contacts         -> all contacts, ordered by role then position
  PUT    /contacts         -> replace the whole list in one go (easiest for the
                              contacts screen: save button sends everything)
  POST   /contacts         -> add one (optional)
  DELETE /contacts/{id}    -> remove one (optional)

role must be "family", "neighbour" or "building" (see config.ESCALATION_ORDER).
position sets the order inside a role, lowest first.

The escalation engine reads this table every time it sends texts, so edits
take effect straight away, even in the middle of an alert.
"""

from fastapi import APIRouter

router = APIRouter(tags=["contacts"])
