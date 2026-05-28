"""Yahoo Finance market data provider.

Free, no API key. Uses the public chart endpoint via urllib. Provides spot
XAU/USD and XAG/USD (forex `=X` symbols). Yahoo only serves intraday down to
1h, so H4 is aggregated from 1h bars (UTC-aligned 4h buckets).
"""

from __future__ import annotations

import json
import logging
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Callable

from app.services.market_providers.base import (
    CandleData,
    MarketDataProvider,
    ProviderError,
)

logger = logging.getLogger(__name__)


# Yahoo carries no XAUUSD=X / XAGUSD=X spot forex symbols; the liquid free
# proxies are the COMEX futures (GC=F gold, SI=F silver). They track spot with a
# small basis and, crucially for SSMT, both come from the same source so the
# XAU/XAG correlation read stays clean.
_SYMBOL_MAP = {
    "XAUUSD": "GC=F",
    "XAGUSD": "SI=F",
}

# Yahoo native intervals. H4 has no native interval -> aggregate from 60m.
_INTERVAL_MAP = {
    "M5": "5m",
    "M15": "15m",
    "H1": "60m",
    "D": "1d",
}

# Default lookback range per interval (Yahoo enforces caps on intraday history).
_RANGE_MAP = {
    "5m": "1mo",
    "15m": "1mo",
    "60m": "3mo",
    "1d": "2y",
}

HttpFetcher = Callable[[str], dict[str, Any]]


def _default_http_fetch(url: str) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            # Yahoo rejects empty/default UA from some clients.
            "User-Agent": "Mozilla/5.0 (compatible; ImadztradesDesk/1.0)",
        },
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        payload = response.read().decode("utf-8")
    return json.loads(payload)


class YahooFinanceProvider(MarketDataProvider):
    name = "yahoo"
    BASE_URL = "https://query1.finance.yahoo.com/v8/finance/chart"

    def __init__(self, http_fetch: HttpFetcher | None = None) -> None:
        self._http_fetch = http_fetch or _default_http_fetch

    def fetch_ohlc(
        self,
        symbol: str,
        timeframe: str,
        start_utc: datetime | None = None,
        end_utc: datetime | None = None,
        limit: int | None = None,
    ) -> list[CandleData]:
        symbol_up = symbol.upper()
        timeframe_up = timeframe.upper()
        if symbol_up not in _SYMBOL_MAP:
            raise ProviderError(f"Yahoo mapping missing for symbol {symbol}")

        aggregate_h4 = timeframe_up == "H4"
        native_tf = "H1" if aggregate_h4 else timeframe_up
        if native_tf not in _INTERVAL_MAP:
            raise ProviderError(f"Yahoo mapping missing for timeframe {timeframe}")

        interval = _INTERVAL_MAP[native_tf]
        params = {
            "interval": interval,
            "range": _RANGE_MAP[interval],
            "includePrePost": "false",
        }
        url = (
            f"{self.BASE_URL}/{urllib.parse.quote(_SYMBOL_MAP[symbol_up])}"
            f"?{urllib.parse.urlencode(params)}"
        )

        try:
            payload = self._http_fetch(url)
        except Exception as exc:  # pragma: no cover - network failure path
            raise ProviderError(f"Yahoo HTTP error: {exc}") from exc

        candles = _parse_chart(payload, symbol_up, native_tf)
        if aggregate_h4:
            candles = _aggregate_to_h4(candles, symbol_up)

        if start_utc is not None:
            candles = [c for c in candles if c.timestamp_utc >= start_utc]
        if end_utc is not None:
            candles = [c for c in candles if c.timestamp_utc <= end_utc]
        candles.sort(key=lambda c: c.timestamp_utc)
        candles = _drop_forming_candle(candles)
        if limit is not None:
            candles = candles[-limit:]
        return candles


def _parse_chart(payload: dict, symbol: str, timeframe: str) -> list[CandleData]:
    chart = payload.get("chart", {}) if isinstance(payload, dict) else {}
    if chart.get("error"):
        raise ProviderError(f"Yahoo API error: {chart['error']}")
    results = chart.get("result")
    if not results:
        return []
    result = results[0]
    timestamps = result.get("timestamp") or []
    quote = (result.get("indicators", {}).get("quote") or [{}])[0]
    opens = quote.get("open") or []
    highs = quote.get("high") or []
    lows = quote.get("low") or []
    closes = quote.get("close") or []
    volumes = quote.get("volume") or []

    candles: list[CandleData] = []
    for i, ts in enumerate(timestamps):
        o, h, l, c = (
            _at(opens, i),
            _at(highs, i),
            _at(lows, i),
            _at(closes, i),
        )
        if None in (o, h, l, c):
            continue
        v = _at(volumes, i)
        candles.append(
            CandleData(
                symbol=symbol,
                timeframe=timeframe,
                open=Decimal(str(o)),
                high=Decimal(str(h)),
                low=Decimal(str(l)),
                close=Decimal(str(c)),
                volume=Decimal(str(v)) if v not in (None, 0) else None,
                timestamp_utc=datetime.fromtimestamp(ts, tz=UTC),
            )
        )
    return candles


def _aggregate_to_h4(candles: list[CandleData], symbol: str) -> list[CandleData]:
    """Aggregate 1h candles into UTC-aligned 4h buckets (00,04,08,12,16,20)."""
    buckets: dict[datetime, list[CandleData]] = {}
    for candle in candles:
        ts = candle.timestamp_utc
        bucket_hour = (ts.hour // 4) * 4
        bucket_key = ts.replace(hour=bucket_hour, minute=0, second=0, microsecond=0)
        buckets.setdefault(bucket_key, []).append(candle)

    aggregated: list[CandleData] = []
    for bucket_key in sorted(buckets):
        group = sorted(buckets[bucket_key], key=lambda c: c.timestamp_utc)
        volumes = [c.volume for c in group if c.volume is not None]
        aggregated.append(
            CandleData(
                symbol=symbol,
                timeframe="H4",
                open=group[0].open,
                high=max(c.high for c in group),
                low=min(c.low for c in group),
                close=group[-1].close,
                volume=sum(volumes) if volumes else None,
                timestamp_utc=bucket_key,
            )
        )
    return aggregated


def _at(values: list, index: int):
    return values[index] if index < len(values) else None


def _drop_forming_candle(candles: list[CandleData]) -> list[CandleData]:
    if not candles:
        return candles
    now = datetime.now(tz=UTC)
    if candles[-1].timestamp_utc > now:
        return candles[:-1]
    return candles
