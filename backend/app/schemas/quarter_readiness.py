from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, field_validator

from app.schemas.market import VALID_SYMBOLS


class QuarterStatus(str, Enum):
    FORMING = "Forming"
    MANIPULATION_PHASE = "Manipulation Phase"
    EXPANSION_READY = "Expansion Ready"
    EXPANSION_ACTIVE = "Expansion Active"
    FAILURE_RISK = "Failure Risk"
    CLOSED_LATE_ENTRY = "Closed / Late Entry"


class QuarterEvaluateRequest(BaseModel):
    symbol: str = Field(default="XAUUSD", description="XAUUSD or XAGUSD")
    as_of_utc: datetime | None = None

    @field_validator("symbol")
    @classmethod
    def validate_symbol(cls, value: str) -> str:
        value = value.upper()
        if value not in VALID_SYMBOLS:
            raise ValueError(f"Symbol must be one of {VALID_SYMBOLS}")
        return value


class QuarterReadinessResponse(BaseModel):
    id: int
    symbol: str
    daily_quarter: str
    micro_quarter_90m: str
    session: str
    quarter_status: QuarterStatus
    quarter_intent: str
    manipulation_status: str
    expansion_status: str
    quarter_execution_allowed: bool
    gate_decision: str
    status_reason: str
    next_valid_window: str
    source_sweep_event_id: int | None
    as_of_utc: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
