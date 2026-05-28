"""Abstract economic-calendar provider."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


class CalendarProviderError(RuntimeError):
    """Raised when the calendar provider fails."""


@dataclass(frozen=True)
class CalendarEvent:
    """Normalized economic-calendar event."""

    event_name: str
    country: str
    impact: str  # "high" | "medium" | "low"
    scheduled_at_utc: datetime
    actual: Decimal | None = None
    forecast: Decimal | None = None
    previous: Decimal | None = None
    source_id: str | None = None  # provider-side unique id for upsert tracking


class CalendarProvider(ABC):
    name: str = "base"

    @abstractmethod
    def fetch_events(
        self,
        start_utc: datetime,
        end_utc: datetime,
        countries: list[str] | None = None,
    ) -> list[CalendarEvent]:
        """Return calendar events within [start_utc, end_utc]."""
