"""Deterministic mock calendar provider for tests."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from app.services.calendar_providers.base import CalendarEvent, CalendarProvider


class MockCalendarProvider(CalendarProvider):
    name = "mock"

    def __init__(self, events: list[CalendarEvent] | None = None) -> None:
        self._events = list(events or [])

    def seed(self, events: list[CalendarEvent]) -> None:
        self._events.extend(events)

    def fetch_events(
        self,
        start_utc: datetime,
        end_utc: datetime,
        countries: list[str] | None = None,
    ) -> list[CalendarEvent]:
        country_set = {c.lower() for c in (countries or [])}
        out = []
        for event in self._events:
            if not (start_utc <= event.scheduled_at_utc <= end_utc):
                continue
            if country_set and event.country.lower() not in country_set:
                continue
            out.append(event)
        out.sort(key=lambda e: e.scheduled_at_utc)
        return out


def make_event(
    event_name: str,
    country: str,
    impact: str,
    scheduled_at_utc: datetime,
    actual: float | None = None,
    forecast: float | None = None,
    previous: float | None = None,
    source_id: str | None = None,
) -> CalendarEvent:
    def _dec(v: float | None) -> Decimal | None:
        return Decimal(str(v)) if v is not None else None

    return CalendarEvent(
        event_name=event_name,
        country=country,
        impact=impact.lower(),
        scheduled_at_utc=scheduled_at_utc,
        actual=_dec(actual),
        forecast=_dec(forecast),
        previous=_dec(previous),
        source_id=source_id,
    )
