from datetime import datetime
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, Field, field_validator

from app.schemas.market import VALID_SYMBOLS


class DolLifecycle(str, Enum):
    ACTIVE = "Active"
    WEAKENING = "Weakening"
    SHIFT_PENDING = "Shift Pending"
    SHIFT_CONFIRMED = "Shift Confirmed"
    COMPLETED = "Completed"
    INVALIDATED = "Invalidated"


class DeliveryDirection(str, Enum):
    UP = "delivery_up"
    DOWN = "delivery_down"


class DolEvaluateRequest(BaseModel):
    symbol: str = Field(default="XAUUSD", description="XAUUSD or XAGUSD")
    as_of_utc: datetime | None = Field(default=None)

    @field_validator("symbol")
    @classmethod
    def validate_symbol(cls, value: str) -> str:
        value = value.upper()
        if value not in VALID_SYMBOLS:
            raise ValueError(f"Symbol must be one of {VALID_SYMBOLS}")
        return value


class DolObjectiveResponse(BaseModel):
    level_id: int
    level_type: str
    liquidity_side: str
    price: Decimal
    liquidity_status: str


class DolAssessmentResponse(BaseModel):
    id: int
    symbol: str
    lifecycle_status: DolLifecycle
    delivery_direction: DeliveryDirection | None
    primary_dol: DolObjectiveResponse | None
    secondary_dol: DolObjectiveResponse | None
    htf_objective: DolObjectiveResponse | None
    intraday_objective: DolObjectiveResponse | None
    engineered_liquidity: DolObjectiveResponse | None
    source_sweep_event_id: int | None
    objective_quality: str | None
    status_reason: str
    old_objective_resolved: bool
    displacement_confirmed: bool
    timing_confirmed: bool
    prior_narrative_resolved: bool
    execution_status: str
    as_of_utc: datetime
    updated_at: datetime
