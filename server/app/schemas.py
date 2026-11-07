"""Request and response shapes."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class EventIn(BaseModel):
    device_id: str = Field(examples=["home-01"])
    sound: str = Field(examples=["smoke_alarm"])
    confidence: float = Field(ge=0, le=1, examples=[0.91])
    ts: Optional[datetime] = None


class AckIn(BaseModel):
    by: str = Field(default="dashboard", examples=["device", "dashboard"])


class StepOut(BaseModel):
    level: int
    role: str
    contact_name: Optional[str]
    sent_at: datetime
    ok: bool
    note: Optional[str]


class EventOut(BaseModel):
    id: int
    device_id: str
    sound: str
    label: str
    confidence: float
    ts: datetime
    status: str
    escalates: bool
    escalation_level: int
    acked_by: Optional[str]
    acked_at: Optional[datetime]
    steps: list[StepOut] = []
    duplicate: bool = False
