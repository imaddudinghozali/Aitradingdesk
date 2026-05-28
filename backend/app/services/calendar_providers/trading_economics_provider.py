"""TradingEconomics calendar provider.

Free `guest:guest` API key is allowed for limited access. Set
`TRADING_ECONOMICS_API_KEY` to override.
"""

from __future__ import annotations

import json
import logging
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Callable

from app.services.calendar_providers.base import (
    CalendarEvent,
    CalendarProvider,
    CalendarProviderError,
)

logger = logging.getLogger(__name__)


HttpFetcher = Callable[[str], Any]


def _default_http_fetch(url: str) -> Any:
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=15) as response:
        payload = response.read().decode("utf-8")
    return json.loads(payload)


_IMPORTANCE_MAP = {
    "3": "high",
    "2": "medium",
    "1": "low",
    3: "high",
    2: "medium",
    1: "low",
}


class TradingEconomicsProvider(CalendarProvider):
    name = "trading_economics"
    BASE_URL = "https://api.tradingeconomics.com/calendar"

    def __init__(
        self,
        api_key: str = "guest:guest",
        http_fetch: HttpFetcher | None = None,
    ) -> None:
        self.api_key = api_key or "guest:guest"
        self._http_fetch = http_fetch or _default_http_fetch

    def fetch_events(
        self,
        start_utc: datetime,
        end_utc: datetime,
        countries: list[str] | None = None,
    ) -> list[CalendarEvent]:
        country_path = (
            "/country/" + ",".join(urllib.parse.quote(c) for c in countries)
            if countries
            else ""
        )
        params = {
            "c": self.api_key,
            "d1": start_utc.strftime("%Y-%m-%d"),
            "d2": end_utc.strftime("%Y-%m-%d"),
            "f": "json",
        }
        url = f"{self.BASE_URL}{country_path}?{urllib.parse.urlencode(params)}"

        try:
            payload = self._http_fetch(url)
        except Exception as exc:  # pragma: no cover - network failure path
            raise CalendarProviderError(f"TradingEconomics HTTP error: {exc}") from exc

        if not isinstance(payload, list):
            raise CalendarProviderError(
                f"TradingEconomics unexpected payload: {type(payload).__name__}"
            )

        events: list[CalendarEvent] = []
        for row in payload:
            event = _row_to_event(row)
            if event is None:
                continue
            if not (start_utc <= event.scheduled_at_utc <= end_utc):
                continue
            events.append(event)
        events.sort(key=lambda e: e.scheduled_at_utc)
        return events


def _row_to_event(row: dict) -> CalendarEvent | None:
    try:
        scheduled_raw = row.get("Date") or row.get("date")
        if not scheduled_raw:
            return None
        scheduled = _parse_te_timestamp(scheduled_raw)
        event_name = row.get("Event") or row.get("event") or ""
        country = row.get("Country") or row.get("country") or ""
        importance_raw = row.get("Importance", row.get("importance", ""))
        impact = _IMPORTANCE_MAP.get(importance_raw, "medium")
        return CalendarEvent(
            event_name=str(event_name).strip(),
            country=str(country).strip(),
            impact=impact,
            scheduled_at_utc=scheduled,
            actual=_to_decimal(row.get("Actual")),
            forecast=_to_decimal(row.get("Forecast")),
            previous=_to_decimal(row.get("Previous")),
            source_id=str(row.get("CalendarId") or row.get("Ticker") or "").strip() or None,
        )
    except Exception as exc:
        logger.warning("Skipping malformed TE row: %s", exc)
        return None


def _parse_te_timestamp(value: str) -> datetime:
    cleaned = value.replace("T", " ").replace("Z", "")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(cleaned, fmt).replace(tzinfo=UTC)
        except ValueError:
            continue
    raise ValueError(value)


def _to_decimal(value: Any) -> Decimal | None:
    if value in (None, "", "-", "N/A"):
        return None
    try:
        cleaned = str(value).replace("%", "").replace(",", "").strip()
        if cleaned.endswith(("K", "M", "B", "T")):
            cleaned = cleaned[:-1]
        return Decimal(cleaned)
    except (InvalidOperation, ValueError):
        return None
