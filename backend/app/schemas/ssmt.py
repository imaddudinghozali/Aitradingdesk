from datetime import datetime
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, Field, field_validator, model_validator


class SsmtStatus(str, Enum):
    WAITING = "waiting"
    NOISE = "noise"
    VALID_BULLISH = "valid_bullish"
    VALID_BEARISH = "valid_bearish"
    MAGNETO_INVALIDATED = "magneto_invalidated"


# Daye fractal cycles supported for SSMT. Each cycle pairs swings across two
# sequential Daye quarters; the candle timeframe must be small enough to resolve
# swings inside a quarter.
#   daily -> 6h quarters (Q1-Q4), H4 candles.
#   90m   -> 90-minute micro-quarters (Q1.1-Q4.4), M5 (min) or M15 candles.
_CYCLE_TIMEFRAMES = {
    "daily": ("H4", {"H4"}),
    "90m": ("M5", {"M5", "M15"}),
}
_CYCLE_ALIASES = {
    "daily": "daily",
    "6h": "daily",
    "h4": "daily",
    "90m": "90m",
    "90min": "90m",
    "micro": "90m",
}


class SsmtEvaluateRequest(BaseModel):
    trade_asset: str = Field(default="XAUUSD")
    confirmation_symbol: str = Field(default="XAGUSD")
    cycle: str = Field(
        default="daily",
        description="Daye fractal cycle: 'daily' (6h quarters/H4) or '90m' (90-min micro-quarters/M5-M15).",
    )
    timeframe: str | None = Field(
        default=None,
        description="Candle timeframe. Defaults to the cycle's smallest swing timeframe (H4 daily, M5 for 90m).",
    )
    poi_touched: bool = Field(
        default=False,
        description="Manual POI confirmation until an OB/FVG/Breaker detector is available.",
    )
    poi_reference: str | None = Field(default=None, max_length=255)
    as_of_utc: datetime | None = None

    @field_validator("trade_asset")
    @classmethod
    def validate_trade_asset(cls, value: str) -> str:
        if value.upper() != "XAUUSD":
            raise ValueError("Trade asset for SSMT must be XAUUSD.")
        return "XAUUSD"

    @field_validator("confirmation_symbol")
    @classmethod
    def validate_confirmation_symbol(cls, value: str) -> str:
        if value.upper() != "XAGUSD":
            raise ValueError("SSMT confirmation symbol must be XAGUSD.")
        return "XAGUSD"

    @model_validator(mode="after")
    def validate_cycle_timeframe(self) -> "SsmtEvaluateRequest":
        cycle = _CYCLE_ALIASES.get(self.cycle.lower().strip())
        if cycle is None:
            raise ValueError("SSMT cycle must be 'daily' or '90m'.")
        default_tf, allowed = _CYCLE_TIMEFRAMES[cycle]
        timeframe = (self.timeframe or default_tf).upper()
        if timeframe not in allowed:
            allowed_str = " or ".join(sorted(allowed))
            raise ValueError(
                f"SSMT '{cycle}' cycle supports {allowed_str} swings, not {timeframe}."
            )
        self.cycle = cycle
        self.timeframe = timeframe
        return self


class SsmtEventResponse(BaseModel):
    id: int
    trade_asset: str
    confirmation_symbol: str
    timeframe: str
    ssmt_status: SsmtStatus
    direction: str | None
    cic_detected: bool
    quarter_sequence_valid: bool
    first_quarter: str | None
    second_quarter: str | None
    xau_first_swing: Decimal | None
    xau_second_swing: Decimal | None
    xag_first_swing: Decimal | None
    xag_second_swing: Decimal | None
    source_sweep_event_id: int | None
    magneto_status: str
    poi_touched: bool
    poi_reference: str | None
    algorithm_state: str
    algorithm_context_status: str
    ssmt_dol_alignment: str
    ssmt_noise_status: str
    xau_relative_state: str
    confirmation_pair_state: str
    liquidity_context: str
    reason_if_noise: str | None
    status_reason: str
    as_of_utc: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
