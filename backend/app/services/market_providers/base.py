"""Abstract market data provider."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


class ProviderError(RuntimeError):
    """Raised when a market data provider fails to deliver candles."""


@dataclass(frozen=True)
class CandleData:
    """Normalized OHLC candle from any provider."""

    symbol: str
    timeframe: str
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal | None
    timestamp_utc: datetime


class MarketDataProvider(ABC):
    """Provider interface — return UTC-stamped candles for one symbol/timeframe."""

    name: str = "base"

    @abstractmethod
    def fetch_ohlc(
        self,
        symbol: str,
        timeframe: str,
        start_utc: datetime | None = None,
        end_utc: datetime | None = None,
        limit: int | None = None,
    ) -> list[CandleData]:
        """Return closed candles sorted ascending by timestamp_utc.

        Implementations must NOT return the currently-forming candle. If the
        provider returns a partial candle, the implementation must drop it.
        """

    def healthcheck(self) -> bool:
        return True
