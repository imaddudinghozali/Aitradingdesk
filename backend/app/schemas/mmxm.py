from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator

from app.schemas.market import VALID_SYMBOLS


class MmxmEvaluateRequest(BaseModel):
    symbol: str = Field(default="XAUUSD", description="XAUUSD or XAGUSD")
    timeframe: str = Field(default="H4")
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
        if value.upper() != "H4":
            raise ValueError("Stage 11 MMXM MVP supports H4 model grading.")
        return "H4"


class MmxmAssessmentResponse(BaseModel):
    id: int
    symbol: str
    active_model: str
    model_status: str
    candle_delivery: str
    htf_delivery_leg: str
    timing_probability: str
    timing_conflict: str
    mmxm_phase: str
    quadrant: str
    quadrant_position: Decimal | None
    range_low: Decimal | None
    range_high: Decimal | None
    current_price: Decimal
    terminus: str
    hrlr_status: str
    lrlr_status: str
    opr_status: str
    judas_status: str
    judas_reason: str
    nine_am_context: str
    status_reason: str
    as_of_utc: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
