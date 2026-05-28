"""Provider factory + registry."""

from __future__ import annotations

from typing import Callable

from app.config import get_settings
from app.services.market_providers.base import MarketDataProvider, ProviderError


_REGISTRY: dict[str, Callable[[], MarketDataProvider]] = {}


def register_provider(name: str, factory: Callable[[], MarketDataProvider]) -> None:
    _REGISTRY[name.lower()] = factory


def get_provider(name: str | None = None) -> MarketDataProvider:
    settings = get_settings()
    provider_name = (name or settings.market_data_provider or "").lower().strip()
    if not provider_name:
        raise ProviderError(
            "No market data provider configured. Set MARKET_DATA_PROVIDER "
            "(twelvedata|mock) or pass a provider name."
        )

    if provider_name in _REGISTRY:
        return _REGISTRY[provider_name]()

    if provider_name == "twelvedata":
        from app.services.market_providers.twelvedata_provider import TwelveDataProvider

        if not settings.twelvedata_api_key:
            raise ProviderError("TWELVEDATA_API_KEY is not configured")
        return TwelveDataProvider(api_key=settings.twelvedata_api_key)

    if provider_name in {"yahoo", "yfinance", "yahoo_finance"}:
        from app.services.market_providers.yahoo_provider import YahooFinanceProvider

        return YahooFinanceProvider()

    if provider_name == "mock":
        from app.services.market_providers.mock_provider import MockProvider

        return MockProvider()

    raise ProviderError(f"Unknown market data provider: {provider_name}")
