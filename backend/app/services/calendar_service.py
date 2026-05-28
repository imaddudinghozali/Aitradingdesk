"""Economic-calendar ingestion + sync-to-catalyst orchestrator.

Pulls events from a `CalendarProvider`, upserts them into `economic_events`,
flags relevant events (CPI/NFP/FOMC/PCE/Rate/Unemployment) by configurable
keyword list, and optionally syncs each relevant high-impact event into the
existing `NewsCatalystService` so the FR-13 gate is auto-armed.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.dol_assessment import DolAssessment
from app.models.economic_event import EconomicEvent
from app.schemas.news import NewsCatalystEvaluateRequest
from app.services.calendar_providers.base import (
    CalendarEvent,
    CalendarProvider,
    CalendarProviderError,
)
from app.services.news_service import NewsCatalystService

logger = logging.getLogger(__name__)


DEFAULT_RELEVANT_KEYWORDS = (
    "CPI",
    "Consumer Price Index",
    "PCE",
    "Core PCE",
    "Personal Consumption",
    "Non-Farm Payrolls",
    "Nonfarm Payrolls",
    "NFP",
    "Unemployment Rate",
    "FOMC",
    "Federal Funds Rate",
    "Fed Interest Rate",
    "Rate Decision",
    "Fed Chair",
    "Powell Speech",
)

DEFAULT_RELEVANT_COUNTRIES = ("United States",)


@dataclass
class CalendarRefreshOutcome:
    provider: str
    fetched: int
    inserted: int
    updated: int
    skipped: int
    relevant: int
    window_start_utc: datetime
    window_end_utc: datetime


@dataclass
class CalendarSyncOutcome:
    evaluated: int
    skipped_missing_dol: int
    skipped_other: int


class CalendarService:
    @staticmethod
    def refresh(
        db: Session,
        provider: CalendarProvider,
        start_utc: datetime | None = None,
        end_utc: datetime | None = None,
        countries: list[str] | None = None,
        relevant_keywords: list[str] | None = None,
    ) -> CalendarRefreshOutcome:
        now = datetime.now(tz=UTC)
        window_start = start_utc or (now - timedelta(days=1))
        window_end = end_utc or (now + timedelta(days=14))

        settings = get_settings()
        country_filter = countries or _csv(settings.calendar_relevant_countries) or list(
            DEFAULT_RELEVANT_COUNTRIES
        )
        keywords = relevant_keywords or _csv(settings.calendar_relevant_events) or list(
            DEFAULT_RELEVANT_KEYWORDS
        )
        keyword_lower = [k.lower() for k in keywords]

        try:
            events = provider.fetch_events(window_start, window_end, country_filter)
        except CalendarProviderError:
            raise
        except Exception as exc:  # pragma: no cover - defensive
            raise CalendarProviderError(f"calendar provider error: {exc}") from exc

        inserted = 0
        updated = 0
        skipped = 0
        relevant_count = 0

        for event in events:
            is_relevant = _is_relevant(event, keyword_lower)
            if is_relevant:
                relevant_count += 1

            existing = (
                db.query(EconomicEvent)
                .filter(
                    EconomicEvent.country == event.country,
                    EconomicEvent.event_name == event.event_name,
                    EconomicEvent.scheduled_at_utc == event.scheduled_at_utc,
                )
                .first()
            )
            if existing is None:
                row = EconomicEvent(
                    provider=provider.name,
                    source_id=event.source_id,
                    event_name=event.event_name,
                    country=event.country,
                    impact=event.impact,
                    scheduled_at_utc=event.scheduled_at_utc,
                    actual=event.actual,
                    forecast=event.forecast,
                    previous=event.previous,
                    is_relevant=is_relevant,
                    last_synced_at_utc=now,
                )
                db.add(row)
                inserted += 1
            else:
                changed = False
                for field, value in (
                    ("impact", event.impact),
                    ("actual", event.actual),
                    ("forecast", event.forecast),
                    ("previous", event.previous),
                    ("source_id", event.source_id),
                    ("provider", provider.name),
                    ("is_relevant", is_relevant),
                ):
                    if getattr(existing, field) != value:
                        setattr(existing, field, value)
                        changed = True
                existing.last_synced_at_utc = now
                if changed:
                    updated += 1
                else:
                    skipped += 1

        db.commit()

        return CalendarRefreshOutcome(
            provider=provider.name,
            fetched=len(events),
            inserted=inserted,
            updated=updated,
            skipped=skipped,
            relevant=relevant_count,
            window_start_utc=window_start,
            window_end_utc=window_end,
        )

    @staticmethod
    def sync_to_catalyst(
        db: Session,
        symbol: str = "XAUUSD",
        lookahead_hours: int = 48,
    ) -> CalendarSyncOutcome:
        now = datetime.now(tz=UTC)
        horizon = now + timedelta(hours=max(lookahead_hours, 1))

        symbol_up = symbol.upper()
        dol = db.query(DolAssessment).filter(DolAssessment.symbol == symbol_up).first()
        if dol is None:
            relevant_events = (
                db.query(EconomicEvent)
                .filter(
                    EconomicEvent.is_relevant.is_(True),
                    EconomicEvent.impact == "high",
                    EconomicEvent.scheduled_at_utc >= now,
                    EconomicEvent.scheduled_at_utc <= horizon,
                )
                .count()
            )
            return CalendarSyncOutcome(
                evaluated=0,
                skipped_missing_dol=relevant_events,
                skipped_other=0,
            )

        events = (
            db.query(EconomicEvent)
            .filter(
                EconomicEvent.is_relevant.is_(True),
                EconomicEvent.impact == "high",
                EconomicEvent.scheduled_at_utc >= now,
                EconomicEvent.scheduled_at_utc <= horizon,
            )
            .order_by(EconomicEvent.scheduled_at_utc.asc())
            .all()
        )

        evaluated = 0
        skipped_other = 0
        for event in events:
            try:
                NewsCatalystService.evaluate(
                    db,
                    NewsCatalystEvaluateRequest(
                        symbol=symbol_up,
                        event_name=_short_event_name(event.event_name),
                        impact=event.impact,
                        scheduled_at_utc=event.scheduled_at_utc,
                    ),
                )
                evaluated += 1
            except Exception as exc:
                logger.warning(
                    "Skipping calendar->catalyst sync for %s @ %s: %s",
                    event.event_name,
                    event.scheduled_at_utc.isoformat(),
                    exc,
                )
                skipped_other += 1

        return CalendarSyncOutcome(
            evaluated=evaluated,
            skipped_missing_dol=0,
            skipped_other=skipped_other,
        )

    @staticmethod
    def upcoming(
        db: Session,
        hours: int = 48,
        impact: str | None = None,
        relevant_only: bool = True,
    ) -> list[EconomicEvent]:
        now = datetime.now(tz=UTC)
        horizon = now + timedelta(hours=max(hours, 1))
        query = db.query(EconomicEvent).filter(
            EconomicEvent.scheduled_at_utc >= now,
            EconomicEvent.scheduled_at_utc <= horizon,
        )
        if relevant_only:
            query = query.filter(EconomicEvent.is_relevant.is_(True))
        if impact:
            query = query.filter(EconomicEvent.impact == impact.lower())
        return query.order_by(EconomicEvent.scheduled_at_utc.asc()).all()


def _is_relevant(event: CalendarEvent, keywords_lower: list[str]) -> bool:
    name_lower = event.event_name.lower()
    return any(kw in name_lower for kw in keywords_lower)


def _csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _short_event_name(name: str) -> str:
    upper = name.upper()
    for tag in ("CPI", "PCE", "NFP", "FOMC", "RATE DECISION", "UNEMPLOYMENT"):
        if tag in upper:
            return tag
    return name[:80]
