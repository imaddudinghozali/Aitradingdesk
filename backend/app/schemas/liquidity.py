from datetime import datetime
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, Field, field_validator

from app.schemas.market import VALID_SYMBOLS


class LiquidityStatus(str, Enum):
    ACTIVE = "active"
    TOUCHED = "touched"
    TAKEN = "taken"
    INVALIDATED = "invalidated"


class LiquidityRefreshRequest(BaseModel):
    symbol: str = Field(default="XAUUSD", description="XAUUSD or XAGUSD")
    as_of_utc: datetime | None = Field(
        default=None,
        description="Calculation cutoff. Defaults to the latest stored snapshot.",
    )

    @field_validator("symbol")
    @classmethod
    def validate_symbol(cls, value: str) -> str:
        value = value.upper()
        if value not in VALID_SYMBOLS:
            raise ValueError(f"Symbol must be one of {VALID_SYMBOLS}")
        return value


class LiquidityStatusUpdate(BaseModel):
    status: LiquidityStatus
    reason: str = Field(min_length=3, max_length=255)


class LiquidityLevelResponse(BaseModel):
    id: int
    symbol: str
    level_type: str
    liquidity_side: str
    price: Decimal
    status: LiquidityStatus
    source_timeframe: str
    source_period_start_ny: datetime
    source_period_end_ny: datetime
    as_of_utc: datetime
    status_reason: str | None
    touched_at_utc: datetime | None
    taken_at_utc: datetime | None
    invalidated_at_utc: datetime | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class LiquidityMapResponse(BaseModel):
    symbol: str
    as_of_utc: datetime
    levels: list[LiquidityLevelResponse]
    missing_level_types: list[str]
