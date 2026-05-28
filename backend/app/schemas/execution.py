from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator

from app.schemas.market import VALID_SYMBOLS


class PoiScanRequest(BaseModel):
    symbol: str = Field(default="XAUUSD")
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
            raise ValueError("POI detection supports M5, M15, or H1 execution timeframes.")
        return value


class PoiZoneResponse(BaseModel):
    id: int
    symbol: str
    timeframe: str
    poi_type: str
    direction: str
    price_low: Decimal
    price_high: Decimal
    status: str
    touched_at_utc: datetime | None
    reaction_confirmed: bool
    invalidated_at_utc: datetime | None
    status_reason: str
    as_of_utc: datetime

    class Config:
        from_attributes = True


class ExecutionEvaluateRequest(PoiScanRequest):
    minimum_rr: Decimal = Field(..., gt=0, description="Trader-required minimum RR policy.")
    poi_id: int | None = None


class ExecutionAssessmentResponse(BaseModel):
    id: int
    symbol: str
    timeframe: str
    delivery_direction: str
    setup_context: str
    poi_confirmation: str
    mss_confirmed: bool
    cisd_confirmed: bool
    trigger_confirmation: str
    entry_reference: Decimal | None
    invalidation_price: Decimal
    target_price: Decimal | None
    risk_points: Decimal | None
    reward_points: Decimal | None
    rr_ratio: Decimal | None
    minimum_rr: Decimal
    risk_status: str
    execution_status: str
    no_trade_reason: str
    validation_required: str
    as_of_utc: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
