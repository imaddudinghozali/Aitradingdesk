import unittest
from decimal import Decimal

from app.services.market_providers.base import ProviderError
from app.services.market_providers.yahoo_provider import YahooFinanceProvider


def _chart(timestamps, opens, highs, lows, closes, volumes=None):
    return {
        "chart": {
            "error": None,
            "result": [
                {
                    "timestamp": timestamps,
                    "indicators": {
                        "quote": [
                            {
                                "open": opens,
                                "high": highs,
                                "low": lows,
                                "close": closes,
                                "volume": volumes or [None] * len(timestamps),
                            }
                        ]
                    },
                }
            ],
        }
    }


class YahooProviderTest(unittest.TestCase):
    def test_parses_h1_candles_and_maps_symbol(self) -> None:
        # 2024-05-20 10:00, 11:00, 12:00 UTC
        payload = _chart(
            [1716199200, 1716202800, 1716206400],
            [73.1, 73.2, 73.3],
            [73.5, 73.6, 73.7],
            [72.9, 73.0, 73.1],
            [73.2, 73.3, 73.4],
            [100, 200, 300],
        )
        captured = {}

        def fake_fetch(url: str):
            captured["url"] = url
            return payload

        provider = YahooFinanceProvider(http_fetch=fake_fetch)
        candles = provider.fetch_ohlc("XAGUSD", "H1")

        self.assertIn("SI%3DF", captured["url"])  # SI=F url-encoded
        self.assertEqual(3, len(candles))
        self.assertEqual("XAGUSD", candles[0].symbol)
        self.assertEqual(Decimal("73.1"), candles[0].open)
        self.assertEqual(Decimal("100"), candles[0].volume)

    def test_h4_aggregation_from_hourly(self) -> None:
        # Six 1h bars spanning two UTC 4h buckets:
        # 00:00,01:00,02:00,03:00 -> bucket 00:00 ; 04:00,05:00 -> bucket 04:00
        base = 1716163200  # 2024-05-20 00:00 UTC
        ts = [base + 3600 * i for i in range(6)]
        provider = YahooFinanceProvider(
            http_fetch=lambda url: _chart(
                ts,
                [10, 11, 12, 13, 14, 15],
                [12, 13, 14, 15, 16, 17],
                [9, 10, 11, 12, 13, 14],
                [11, 12, 13, 14, 15, 16],
                [1, 1, 1, 1, 1, 1],
            )
        )
        candles = provider.fetch_ohlc("XAUUSD", "H4")

        self.assertEqual(2, len(candles))
        first = candles[0]
        self.assertEqual("H4", first.timeframe)
        self.assertEqual(Decimal("10"), first.open)   # first bar open
        self.assertEqual(Decimal("15"), first.high)   # max high across 4 bars
        self.assertEqual(Decimal("9"), first.low)     # min low
        self.assertEqual(Decimal("14"), first.close)  # last bar close in bucket
        self.assertEqual(Decimal("4"), first.volume)  # summed
        self.assertEqual(0, first.timestamp_utc.hour)
        self.assertEqual(4, candles[1].timestamp_utc.hour)

    def test_unsupported_symbol_raises(self) -> None:
        provider = YahooFinanceProvider(http_fetch=lambda url: {})
        with self.assertRaises(ProviderError):
            provider.fetch_ohlc("EURUSD", "H1")

    def test_api_error_raises(self) -> None:
        provider = YahooFinanceProvider(
            http_fetch=lambda url: {"chart": {"error": {"code": "Not Found"}, "result": None}}
        )
        with self.assertRaises(ProviderError):
            provider.fetch_ohlc("XAUUSD", "D")


if __name__ == "__main__":
    unittest.main()
