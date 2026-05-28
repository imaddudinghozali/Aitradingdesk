"""Economic-calendar provider adapters."""

from app.services.calendar_providers.base import (
    CalendarEvent,
    CalendarProvider,
    CalendarProviderError,
)
from app.services.calendar_providers.factory import (
    get_calendar_provider,
    register_calendar_provider,
)
from app.services.calendar_providers.mock_provider import MockCalendarProvider
from app.services.calendar_providers.trading_economics_provider import (
    TradingEconomicsProvider,
)

__all__ = [
    "CalendarEvent",
    "CalendarProvider",
    "CalendarProviderError",
    "get_calendar_provider",
    "register_calendar_provider",
    "MockCalendarProvider",
    "TradingEconomicsProvider",
]
