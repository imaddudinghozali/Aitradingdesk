"""Schemas for live market data ingestion."""

from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field, field_validator

from app.schemas.market import TIMEFRAME_ALIASES, VALID_SYMBOLS, VALID_TIMEFRAMES


class IngestionRunRequest(BaseModel):
    provider: str | None = Field(
        default=None,
        description="Provider name override. Defaults to MARKET_DATA_PROVIDER env.",
    )
    symbols: list[str] = Field(default_factory=list)
    timeframes: list[str] = Field(default_factory=list)
    start_utc: datetime | None = Field(default=None)
    end_utc: datetime | None = Field(default=None)
    limit: int | None = Field(default=None, ge=1, le=5000)

    @field_validator("symbols")
    @classmethod
    def _normalize_symbols(cls, value: list[str]) -> list[str]:
        normalized = []
        for raw in value:
            up = raw.upper()
            if up not in VALID_SYMBOLS:
                raise ValueError(f"Symbol must be one of {VALID_SYMBOLS}")
            normalized.append(up)
        return normalized

    @field_validator("timeframes")
    @classmethod
    def _normalize_timeframes(cls, value: list[str]) -> list[str]:
        normalized = []
        for raw in value:
            up = TIMEFRAME_ALIASES.get(raw.upper(), raw.upper())
            if up not in VALID_TIMEFRAMES:
                raise ValueError(f"Timeframe must be one of {VALID_TIMEFRAMES}")
            normalized.append(up)
        return normalized


class IngestionRunResult(BaseModel):
    provider: str
    symbol: str
    timeframe: str
    status: str
    candles_fetched: int
    candles_inserted: int
    candles_skipped: int
    first_candle_utc: datetime | None
    last_candle_utc: datetime | None
    started_at_utc: datetime
    finished_at_utc: datetime
    error_message: str | None

    class Config:
        from_attributes = True


class SchedulerControlRequest(BaseModel):
    interval_seconds: int | None = Field(default=None, ge=30, le=86400)
    provider: str | None = None
    symbols: list[str] = Field(default_factory=list)
    timeframes: list[str] = Field(default_factory=list)


class SchedulerStatus(BaseModel):
    running: bool
    provider: str | None
    symbols: list[str]
    timeframes: list[str]
    interval_seconds: int | None
    last_tick_utc: datetime | None
    last_error: str | None
    next_tick_utc: datetime | None
