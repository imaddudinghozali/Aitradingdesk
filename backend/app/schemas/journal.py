from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator

from app.schemas.market import VALID_SYMBOLS

VALID_RESULTS = {"pending", "win", "loss", "breakeven", "no_trade", "cancelled"}


class JournalCreateRequest(BaseModel):
    symbol: str = Field(default="XAUUSD")
    narrative_snapshot_id: int | None = None
    execution_assessment_id: int | None = None
    setup_context: str = Field(min_length=1)
    entry_reason: str = Field(min_length=1)
    execution_confirmation: str = Field(min_length=1)
    invalidation: str = Field(min_length=1)
    risk: str = Field(min_length=1)
    result: str = "pending"
    realized_rr: Decimal | None = None
    mistake_review: str | None = None
    narrative_review: str | None = None
    screenshot_path: str | None = None
    notes: str | None = None

    @field_validator("symbol")
    @classmethod
    def validate_symbol(cls, value: str) -> str:
        value = value.upper()
        if value not in VALID_SYMBOLS:
            raise ValueError(f"Symbol must be one of {VALID_SYMBOLS}")
        return value

    @field_validator("result")
    @classmethod
    def validate_result(cls, value: str) -> str:
        value = value.lower()
        if value not in VALID_RESULTS:
            raise ValueError(f"Result must be one of {sorted(VALID_RESULTS)}")
        return value


class JournalUpdateRequest(BaseModel):
    entry_reason: str | None = None
    execution_confirmation: str | None = None
    invalidation: str | None = None
    risk: str | None = None
    result: str | None = None
    realized_rr: Decimal | None = None
    mistake_review: str | None = None
    narrative_review: str | None = None
    screenshot_path: str | None = None
    notes: str | None = None

    @field_validator("result")
    @classmethod
    def validate_result(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.lower()
        if value not in VALID_RESULTS:
            raise ValueError(f"Result must be one of {sorted(VALID_RESULTS)}")
        return value


class JournalEntryResponse(BaseModel):
    id: int
    symbol: str
    narrative_snapshot_id: int | None
    execution_assessment_id: int | None
    session: str | None
    daily_quarter: str | None
    setup_context: str
    ai_narrative: str | None
    entry_reason: str
    execution_confirmation: str
    invalidation: str
    risk: str
    result: str
    realized_rr: Decimal | None
    mistake_review: str | None
    narrative_review: str | None
    screenshot_path: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ReviewBucket(BaseModel):
    name: str
    trades: int
    wins: int
    average_rr: Decimal | None


class JournalPerformanceResponse(BaseModel):
    symbol: str | None
    total_entries: int
    completed_trades: int
    no_trade_reviews: int
    wins: int
    losses: int
    winrate: Decimal | None
    average_rr: Decimal | None
    cumulative_rr: Decimal | None
    max_drawdown_rr: Decimal | None
    by_session: list[ReviewBucket]
    by_quarter: list[ReviewBucket]
