"""TwelveData market data provider.

Free tier supports XAU/USD and XAG/USD as forex pairs. The provider returns
closed OHLC candles only. Requires TWELVEDATA_API_KEY.
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


_SYMBOL_MAP = {
    "XAUUSD": "XAU/USD",
    "XAGUSD": "XAG/USD",
}

_INTERVAL_MAP = {
    "M5": "5min",
    "M15": "15min",
    "H1": "1h",
    "H4": "4h",
    "D": "1day",
}


HttpFetcher = Callable[[str], dict[str, Any]]


def _default_http_fetch(url: str) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=15) as response:
        payload = response.read().decode("utf-8")
    return json.loads(payload)


class TwelveDataProvider(MarketDataProvider):
    name = "twelvedata"
    BASE_URL = "https://api.twelvedata.com/time_series"

    def __init__(
        self,
        api_key: str,
        http_fetch: HttpFetcher | None = None,
    ) -> None:
        if not api_key:
            raise ProviderError("TwelveData API key is required")
        self.api_key = api_key
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
            raise ProviderError(f"TwelveData mapping missing for symbol {symbol}")
        if timeframe_up not in _INTERVAL_MAP:
            raise ProviderError(f"TwelveData mapping missing for timeframe {timeframe}")

        params: dict[str, str] = {
            "symbol": _SYMBOL_MAP[symbol_up],
            "interval": _INTERVAL_MAP[timeframe_up],
            "format": "JSON",
            "order": "ASC",
            "timezone": "UTC",
            "apikey": self.api_key,
        }
        if start_utc is not None:
            params["start_date"] = start_utc.strftime("%Y-%m-%d %H:%M:%S")
        if end_utc is not None:
            params["end_date"] = end_utc.strftime("%Y-%m-%d %H:%M:%S")
        if limit is not None:
            params["outputsize"] = str(min(max(int(limit), 1), 5000))
        else:
            params["outputsize"] = "200"

        url = f"{self.BASE_URL}?{urllib.parse.urlencode(params)}"

        try:
            payload = self._http_fetch(url)
        except Exception as exc:  # pragma: no cover - network failure path
            raise ProviderError(f"TwelveData HTTP error: {exc}") from exc

        if isinstance(payload, dict) and payload.get("status") == "error":
            raise ProviderError(
                f"TwelveData API error: {payload.get('message', 'unknown')}"
            )

        values = payload.get("values") if isinstance(payload, dict) else None
        if not values:
            return []

        candles: list[CandleData] = []
        for row in values:
            ts_raw = row.get("datetime")
            if not ts_raw:
                continue
            try:
                ts = _parse_timestamp(ts_raw)
            except ValueError:
                logger.warning("Skipping TwelveData row with unparsable datetime: %s", ts_raw)
                continue
            candles.append(
                CandleData(
                    symbol=symbol_up,
                    timeframe=timeframe_up,
                    open=Decimal(str(row["open"])),
                    high=Decimal(str(row["high"])),
                    low=Decimal(str(row["low"])),
                    close=Decimal(str(row["close"])),
                    volume=Decimal(str(row["volume"])) if row.get("volume") not in (None, "") else None,
                    timestamp_utc=ts,
                )
            )

        candles.sort(key=lambda c: c.timestamp_utc)
        return _drop_forming_candle(candles)


def _parse_timestamp(value: str) -> datetime:
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt).replace(tzinfo=UTC)
        except ValueError:
            continue
    raise ValueError(value)


def _drop_forming_candle(candles: list[CandleData]) -> list[CandleData]:
    if not candles:
        return candles
    now = datetime.now(tz=UTC)
    cutoff = candles[-1].timestamp_utc
    if cutoff > now:
        return candles[:-1]
    return candles
