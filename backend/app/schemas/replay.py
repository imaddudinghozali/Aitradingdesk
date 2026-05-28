"""Hypothetical raw-candle replay schemas."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator

from app.schemas.market import TIMEFRAME_ALIASES, VALID_SYMBOLS, VALID_TIMEFRAMES


class ReplayRunRequest(BaseModel):
    symbol: str = Field(default="XAUUSD")
    timeframe: str = Field(default="M15")
    start_utc: datetime
    end_utc: datetime
    policy: str = Field(default="basic")
    step_bars: int = Field(default=1, ge=1, le=200)
    horizon_bars: int = Field(default=24, ge=1, le=500)
    secondary_symbol: str | None = Field(default="XAGUSD")

    @field_validator("symbol")
    @classmethod
    def validate_symbol(cls, v: str) -> str:
        v = v.upper()
        if v not in VALID_SYMBOLS:
            raise ValueError(f"Symbol must be one of {VALID_SYMBOLS}")
        return v

    @field_validator("secondary_symbol")
    @classmethod
    def validate_secondary(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.upper()
        if v not in VALID_SYMBOLS:
            raise ValueError(f"Secondary symbol must be one of {VALID_SYMBOLS}")
        return v

    @field_validator("timeframe")
    @classmethod
    def validate_timeframe(cls, v: str) -> str:
        v = TIMEFRAME_ALIASES.get(v.upper(), v.upper())
        if v not in VALID_TIMEFRAMES:
            raise ValueError(f"Timeframe must be one of {VALID_TIMEFRAMES}")
        return v


class ReplayRunResponse(BaseModel):
    id: int
    symbol: str
    timeframe: str
    policy_name: str
    start_utc: datetime
    end_utc: datetime
    step_bars: int
    horizon_bars: int
    status: str
    methodology: str
    evaluation_points: int
    valid_setups: int
    no_trades: int
    setup_wins: int
    setup_losses: int
    setup_unresolved: int
    winrate: Decimal | None
    average_rr: Decimal | None
    max_drawdown_rr: Decimal | None
    completed_at_utc: datetime | None
    created_at: datetime

    class Config:
        from_attributes = True


class ReplayDecisionResponse(BaseModel):
    id: int
    replay_run_id: int
    as_of_utc: datetime
    daily_quarter: str
    session: str
    decision: str
    direction: str
    entry_reference: Decimal | None
    target_price: Decimal | None
    invalidation_price: Decimal | None
    expected_rr: Decimal | None
    bars_observed: int
    outcome: str
    realized_rr: Decimal | None
    outcome_reason: str
    reason: str

    class Config:
        from_attributes = True
