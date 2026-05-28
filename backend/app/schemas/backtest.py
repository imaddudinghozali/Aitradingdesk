from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator

from app.schemas.market import VALID_SYMBOLS


class BacktestRunRequest(BaseModel):
    symbol: str = Field(default="XAUUSD")
    timeframe: str = Field(default="M15")
    start_utc: datetime | None = None
    end_utc: datetime | None = None
    horizon_bars: int = Field(default=16, ge=1, le=500)

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
            raise ValueError("Backtest outcome scoring supports M5, M15, or H1.")
        return value


class BacktestObservationResponse(BaseModel):
    id: int
    backtest_run_id: int
    narrative_snapshot_id: int
    execution_assessment_id: int | None
    source_sweep_event_id: int | None
    symbol: str
    timeframe: str
    observed_at_utc: datetime
    session: str
    daily_quarter: str
    htf_dol: str
    direction_liquidity: str
    active_model: str
    ssmt_status: str
    judas_status: str
    opr_status: str
    mmxm_timing_context: str
    execution_status: str
    entry_reference: Decimal | None
    invalidation_price: Decimal | None
    target_price: Decimal | None
    expected_rr: Decimal | None
    bars_observed: int
    outcome: str
    realized_rr: Decimal | None
    outcome_reason: str
    created_at: datetime

    class Config:
        from_attributes = True


class BacktestRunResponse(BaseModel):
    id: int
    symbol: str
    timeframe: str
    start_utc: datetime | None
    end_utc: datetime | None
    horizon_bars: int
    status: str
    methodology: str
    narrative_samples: int
    scored_samples: int
    valid_setup_samples: int
    setup_wins: int
    setup_losses: int
    setup_unresolved: int
    no_trade_samples: int
    no_trade_scored: int
    no_trade_correct: int
    winrate: Decimal | None
    average_rr: Decimal | None
    max_drawdown_rr: Decimal | None
    no_trade_accuracy: Decimal | None
    false_ssmt_rate: Decimal | None
    false_sweep_rate: Decimal | None
    best_session: str | None
    worst_session: str | None
    best_quarter: str | None
    worst_quarter: str | None
    completed_at_utc: datetime | None
    created_at: datetime

    class Config:
        from_attributes = True


class BacktestBreakdownBucket(BaseModel):
    concept: str
    value: str
    setup_samples: int
    resolved_setups: int
    wins: int
    winrate: Decimal | None
    average_rr: Decimal | None
