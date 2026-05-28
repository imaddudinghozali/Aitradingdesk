from datetime import datetime
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, Field, field_validator

from app.schemas.market import VALID_SYMBOLS


class SweepStatus(str, Enum):
    FALSE_TOUCH = "False Touch"
    LIQUIDITY_TAP = "Liquidity Tap"
    VALID_SWEEP = "Valid Sweep"
    TURTLE_SOUP = "Turtle Soup"
    MANIPULATION_SWEEP = "Manipulation Sweep"
    TRUE_BREAKOUT_BREAKDOWN = "True Breakout / Breakdown"


class NarrativeAlignment(str, Enum):
    UNKNOWN = "unknown"
    ALIGNED = "aligned"
    CONFLICT = "conflict"


class SweepScanRequest(BaseModel):
    symbol: str = Field(default="XAUUSD", description="XAUUSD or XAGUSD")
    timeframe: str = Field(default="M15", description="M5, M15, or H1")
    as_of_utc: datetime | None = Field(default=None)
    narrative_alignment: NarrativeAlignment = NarrativeAlignment.UNKNOWN

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
            raise ValueError("Sweep scan timeframe must be M5, M15, or H1")
        return value


class SweepEventResponse(BaseModel):
    id: int
    liquidity_level_id: int
    interaction_snapshot_id: int
    confirmation_snapshot_id: int | None
    symbol: str
    level_type: str
    liquidity_side: str
    level_price: Decimal
    session: str
    session_anchor: str
    daily_quarter: str
    micro_quarter_90m: str
    sweep_status: SweepStatus
    confirmation_status: str
    displacement_detected: bool
    relevant_timing: bool
    narrative_alignment: NarrativeAlignment
    reason: str
    target_liquidity: str | None
    detected_at_utc: datetime
    created_at: datetime

    class Config:
        from_attributes = True


class SweepScanResponse(BaseModel):
    symbol: str
    timeframe: str
    as_of_utc: datetime
    events: list[SweepEventResponse]
    no_trade_required: bool
    waiting_reasons: list[str]
