"""Calendar provider factory + registry."""

from __future__ import annotations

from typing import Callable

from app.config import get_settings
from app.services.calendar_providers.base import (
    CalendarProvider,
    CalendarProviderError,
)


_REGISTRY: dict[str, Callable[[], CalendarProvider]] = {}


def register_calendar_provider(name: str, factory: Callable[[], CalendarProvider]) -> None:
    _REGISTRY[name.lower()] = factory


def get_calendar_provider(name: str | None = None) -> CalendarProvider:
    settings = get_settings()
    provider_name = (name or settings.calendar_provider or "").lower().strip()
    if not provider_name:
        raise CalendarProviderError(
            "No calendar provider configured. Set CALENDAR_PROVIDER "
            "(trading_economics|mock) or pass a provider name."
        )

    if provider_name in _REGISTRY:
        return _REGISTRY[provider_name]()

    if provider_name in {"trading_economics", "tradingeconomics", "te"}:
        from app.services.calendar_providers.trading_economics_provider import (
            TradingEconomicsProvider,
        )

        return TradingEconomicsProvider(
            api_key=settings.trading_economics_api_key or "guest:guest"
        )

    if provider_name == "mock":
        from app.services.calendar_providers.mock_provider import MockCalendarProvider

        return MockCalendarProvider()

    raise CalendarProviderError(f"Unknown calendar provider: {provider_name}")
