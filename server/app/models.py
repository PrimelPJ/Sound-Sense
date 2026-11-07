"""Database tables."""

from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


def now() -> datetime:
    return datetime.now(timezone.utc)


class Event(SQLModel, table=True):
    """One sound the listener heard."""

    id: Optional[int] = Field(default=None, primary_key=True)
    device_id: str = Field(index=True)
    sound: str
    confidence: float
    ts: datetime  # when the sound was heard
    received_at: datetime = Field(default_factory=now)
    # info: heads up only, never escalates (doorbell, kettle)
    # active: alert is on, waiting for "I'm OK"
    # escalating: at least one contact has been texted
    # unanswered: every contact group was texted and nobody pressed "I'm OK"
    # acked: someone pressed "I'm OK"
    status: str = Field(default="active", index=True)
    escalation_level: int = 0
    acked_by: Optional[str] = None
    acked_at: Optional[datetime] = None


class Contact(SQLModel, table=True):
    """Someone to text when nobody responds. Alisha's contacts screen edits these."""

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    phone: str
    role: str = Field(index=True)  # family, neighbour or building
    position: int = 0  # order inside the role, lowest first


class EscalationStep(SQLModel, table=True):
    """A record of each text that went out (or was skipped)."""

    id: Optional[int] = Field(default=None, primary_key=True)
    event_id: int = Field(index=True, foreign_key="event.id")
    level: int
    role: str
    contact_name: Optional[str] = None
    phone: Optional[str] = None
    sent_at: datetime = Field(default_factory=now)
    ok: bool = True
    note: Optional[str] = None
