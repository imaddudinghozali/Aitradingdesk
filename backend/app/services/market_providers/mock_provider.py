"""Deterministic in-memory provider used for tests and offline development."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from app.services.market_providers.base import CandleData, MarketDataProvider


class MockProvider(MarketDataProvider):
    name = "mock"

    def __init__(self, candles: list[CandleData] | None = None) -> None:
        self._store: dict[tuple[str, str], list[CandleData]] = {}
        for candle in candles or []:
            key = (candle.symbol.upper(), candle.timeframe.upper())
            self._store.setdefault(key, []).append(candle)
        for key in self._store:
            self._store[key].sort(key=lambda c: c.timestamp_utc)

    def seed(self, candles: list[CandleData]) -> None:
        for candle in candles:
            key = (candle.symbol.upper(), candle.timeframe.upper())
            self._store.setdefault(key, []).append(candle)
            self._store[key].sort(key=lambda c: c.timestamp_utc)

    def fetch_ohlc(
        self,
        symbol: str,
        timeframe: str,
        start_utc: datetime | None = None,
        end_utc: datetime | None = None,
        limit: int | None = None,
    ) -> list[CandleData]:
        key = (symbol.upper(), timeframe.upper())
        candles = list(self._store.get(key, ()))
        if start_utc is not None:
            candles = [c for c in candles if c.timestamp_utc >= start_utc]
        if end_utc is not None:
            candles = [c for c in candles if c.timestamp_utc <= end_utc]
        if limit is not None:
            candles = candles[-limit:]
        return candles


def _decimal(value: float | int | str) -> Decimal:
    return Decimal(str(value))


def make_candle(
    symbol: str,
    timeframe: str,
    timestamp_utc: datetime,
    open_price: float,
    high: float,
    low: float,
    close: float,
    volume: float | None = None,
) -> CandleData:
    return CandleData(
        symbol=symbol.upper(),
        timeframe=timeframe.upper(),
        open=_decimal(open_price),
        high=_decimal(high),
        low=_decimal(low),
        close=_decimal(close),
        volume=_decimal(volume) if volume is not None else None,
        timestamp_utc=timestamp_utc,
    )
