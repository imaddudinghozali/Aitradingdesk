"""Market data provider adapters."""

from app.services.market_providers.base import (
    CandleData,
    MarketDataProvider,
    ProviderError,
)
from app.services.market_providers.factory import get_provider, register_provider
from app.services.market_providers.mock_provider import MockProvider
from app.services.market_providers.twelvedata_provider import TwelveDataProvider
from app.services.market_providers.yahoo_provider import YahooFinanceProvider

__all__ = [
    "CandleData",
    "MarketDataProvider",
    "ProviderError",
    "get_provider",
    "register_provider",
    "MockProvider",
    "TwelveDataProvider",
    "YahooFinanceProvider",
]
