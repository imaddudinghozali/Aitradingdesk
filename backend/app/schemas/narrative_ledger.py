from datetime import datetime
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, Field, field_validator

from app.schemas.market import VALID_SYMBOLS


class NarrativeContinuationStatus(str, Enum):
    ACTIVE = "active"
    CONTINUING = "continuing"
    WEAKENING = "weakening"
    FAILED = "failed"
    REVERSED = "reversed"
    REDISTRIBUTED = "redistributed"


class NarrativeLedgerEvaluateRequest(BaseModel):
    symbol: str = Field(default="XAUUSD", description="XAUUSD or XAGUSD")
    timeframe: str = Field(default="M15")
    as_of_utc: datetime | None = None

    @field_validator("symbol")
    @classmethod
    def validate_symbol(cls, value: str) -> str:
        value = value.upper()
        if value not in VALID_SYMBOLS:
            raise ValueError(f"Symbol must be one of {VALID_SYMBOLS}")
        return value

    @field_validator("timeframe")
    @classmethod
    def validate_timeframe(cls, value: str) -> str:
        value = value.upper()
        if value not in {"M5", "M15", "H1"}:
            raise ValueError("Invalidation evaluation timeframe must be M5, M15, or H1.")
        return value


class NarrativeLedgerResponse(BaseModel):
    id: int
    symbol: str
    active_dol: str
    delivery_direction: str
    target_liquidity: str
    invalidation_level: str
    invalidation_price: Decimal
    invalidation_condition: str
    next_decision_if_invalidated: str
    reset_required: bool
    continuation_status: NarrativeContinuationStatus
    breach_status: str
    status_reason: str
    invalidated_at_utc: datetime | None
    activated_at_utc: datetime
    as_of_utc: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
