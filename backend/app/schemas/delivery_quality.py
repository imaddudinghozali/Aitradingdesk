from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.schemas.market import VALID_SYMBOLS


class DeliveryQualityEvaluateRequest(BaseModel):
    symbol: str = Field(default="XAUUSD", description="XAUUSD or XAGUSD")
    timeframe: str = Field(default="M15")
    valid_retracement: bool = Field(
        default=False,
        description="Manual retracement/POI confirmation until OB/FVG/Breaker detection exists.",
    )
    poi_reference: str | None = Field(default=None, max_length=255)
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
        if value.upper() != "M15":
            raise ValueError("Stage 12 Delivery Quality MVP supports M15 delivery grading.")
        return "M15"


class DeliveryQualityAssessmentResponse(BaseModel):
    id: int
    symbol: str
    timeframe: str
    valid_retracement: bool
    poi_reference: str | None
    delivery_tempo: str
    expansion_quality: str
    expansion_status: str
    clean_displacement: bool
    overlap_heavy: bool
    failed_continuation: bool
    terminal_expansion: bool
    engineered_expansion: bool
    target_reached: bool
    status_reason: str
    execution_impact: str
    as_of_utc: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
