"""Calendar / economic-event schemas."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class CalendarRefreshRequest(BaseModel):
    provider: str | None = None
    start_utc: datetime | None = None
    end_utc: datetime | None = None
    countries: list[str] = Field(default_factory=list)
    relevant_keywords: list[str] = Field(default_factory=list)


class CalendarRefreshResponse(BaseModel):
    provider: str
    fetched: int
    inserted: int
    updated: int
    skipped: int
    relevant: int
    window_start_utc: datetime
    window_end_utc: datetime


class CalendarSyncRequest(BaseModel):
    symbol: str = Field(default="XAUUSD")
    lookahead_hours: int = Field(default=48, ge=1, le=720)


class CalendarSyncResponse(BaseModel):
    evaluated: int
    skipped_missing_dol: int
    skipped_other: int


class EconomicEventResponse(BaseModel):
    id: int
    provider: str
    source_id: str | None
    event_name: str
    country: str
    impact: str
    scheduled_at_utc: datetime
    actual: Decimal | None
    forecast: Decimal | None
    previous: Decimal | None
    is_relevant: bool
    last_synced_at_utc: datetime

    class Config:
        from_attributes = True
