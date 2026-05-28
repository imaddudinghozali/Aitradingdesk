import unittest
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.config import Settings
from app.database import Base
from app.models import IngestionRun, MarketSnapshot  # noqa: F401
from app.services.market_ingestion_service import MarketIngestionService
from app.services.market_providers.base import CandleData, ProviderError
from app.services.market_providers.mock_provider import MockProvider, make_candle
from app.services.market_providers.twelvedata_provider import TwelveDataProvider


def _ts(hour: int) -> datetime:
    return datetime(2026, 5, 20, hour, 0, tzinfo=UTC)


class MarketIngestionServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=engine)
        self.db = Session(bind=engine)
        self.provider = MockProvider(
            [
                make_candle("XAUUSD", "H1", _ts(10), 2400, 2410, 2395, 2405),
                make_candle("XAUUSD", "H1", _ts(11), 2405, 2415, 2400, 2412),
                make_candle("XAUUSD", "H1", _ts(12), 2412, 2420, 2408, 2418),
            ]
        )

    def tearDown(self) -> None:
        self.db.close()

    def test_run_once_inserts_all_new_candles(self) -> None:
        outcome = MarketIngestionService.run_once(
            self.db, self.provider, "XAUUSD", "H1"
        )

        self.assertEqual("ok", outcome.status)
        self.assertEqual(3, outcome.candles_fetched)
        self.assertEqual(3, outcome.candles_inserted)
        self.assertEqual(0, outcome.candles_skipped)
        self.assertEqual(_ts(10), outcome.first_candle_utc)
        self.assertEqual(_ts(12), outcome.last_candle_utc)
        snapshots = self.db.query(MarketSnapshot).order_by(MarketSnapshot.timestamp_utc).all()
        self.assertEqual(3, len(snapshots))
        self.assertEqual("XAUUSD", snapshots[0].symbol)
        self.assertEqual("H1", snapshots[0].timeframe)

    def test_run_twice_dedupes(self) -> None:
        MarketIngestionService.run_once(self.db, self.provider, "XAUUSD", "H1")
        outcome = MarketIngestionService.run_once(self.db, self.provider, "XAUUSD", "H1")

        self.assertEqual("ok", outcome.status)
        self.assertEqual(3, outcome.candles_fetched)
        self.assertEqual(0, outcome.candles_inserted)
        self.assertEqual(3, outcome.candles_skipped)
        self.assertEqual(3, self.db.query(MarketSnapshot).count())

    def test_provider_error_records_run(self) -> None:
        class _Failing(MockProvider):
            name = "failing"

            def fetch_ohlc(self, *args, **kwargs):  # type: ignore[override]
                raise ProviderError("rate limited")

        outcome = MarketIngestionService.run_once(self.db, _Failing(), "XAUUSD", "H1")

        self.assertEqual("provider_error", outcome.status)
        self.assertEqual(0, outcome.candles_inserted)
        self.assertEqual("rate limited", outcome.error_message)
        run = MarketIngestionService.latest_run(self.db, "XAUUSD", "H1")
        self.assertIsNotNone(run)
        assert run is not None
        self.assertEqual("provider_error", run.status)

    def test_run_batch_iterates_all_pairs(self) -> None:
        self.provider.seed(
            [
                make_candle("XAGUSD", "H1", _ts(10), 30.1, 30.2, 30.0, 30.15),
                make_candle("XAGUSD", "H1", _ts(11), 30.15, 30.3, 30.1, 30.25),
                make_candle("XAUUSD", "M15", _ts(10), 2400, 2402, 2398, 2401),
            ]
        )

        outcomes = MarketIngestionService.run_batch(
            self.db,
            self.provider,
            symbols=["XAUUSD", "XAGUSD"],
            timeframes=["H1", "M15"],
        )

        self.assertEqual(4, len(outcomes))
        total_inserted = sum(o.candles_inserted for o in outcomes)
        self.assertEqual(3 + 2 + 1 + 0, total_inserted)

    @patch("app.services.market_ingestion_service.AnalysisPipelineService.run")
    @patch(
        "app.services.market_ingestion_service.get_settings",
        return_value=Settings(
            market_ingest_auto_analysis=True,
            market_ingest_auto_analysis_timeframe="M15",
            market_ingest_auto_analysis_provider="rules",
        ),
    )
    def test_auto_analysis_runs_once_after_new_execution_candle(
        self,
        _settings,
        run_analysis,
    ) -> None:
        self.provider.seed(
            [make_candle("XAUUSD", "M15", _ts(10), 2400, 2402, 2398, 2401)]
        )

        MarketIngestionService.run_batch(
            self.db,
            self.provider,
            symbols=["XAUUSD", "XAGUSD"],
            timeframes=["M15", "H1"],
        )

        run_analysis.assert_called_once()
        request = run_analysis.call_args.args[1]
        self.assertEqual("XAUUSD", request.symbol)
        self.assertEqual("M15", request.execution_timeframe)

    @patch("app.services.market_ingestion_service.AnalysisPipelineService.run")
    @patch(
        "app.services.market_ingestion_service.get_settings",
        return_value=Settings(
            market_ingest_auto_analysis=True,
            market_ingest_auto_analysis_timeframe="M15",
            market_ingest_auto_analysis_provider="rules",
        ),
    )
    def test_auto_analysis_does_not_run_without_new_execution_candle(
        self,
        _settings,
        run_analysis,
    ) -> None:
        MarketIngestionService.run_batch(
            self.db,
            self.provider,
            symbols=["XAUUSD"],
            timeframes=["H1"],
        )

        run_analysis.assert_not_called()

    def test_invalid_ohlc_is_skipped(self) -> None:
        bad = CandleData(
            symbol="XAUUSD",
            timeframe="H1",
            open=Decimal("2400"),
            high=Decimal("2395"),  # high < low
            low=Decimal("2398"),
            close=Decimal("2399"),
            volume=None,
            timestamp_utc=_ts(13),
        )
        self.provider.seed([bad])

        outcome = MarketIngestionService.run_once(self.db, self.provider, "XAUUSD", "H1")

        self.assertEqual(4, outcome.candles_fetched)
        self.assertEqual(3, outcome.candles_inserted)
        self.assertEqual(1, outcome.candles_skipped)


class TwelveDataProviderParsingTest(unittest.TestCase):
    def test_parses_payload_into_candles(self) -> None:
        payload = {
            "values": [
                {
                    "datetime": "2024-05-20 10:00:00",
                    "open": "2400.5",
                    "high": "2410.0",
                    "low": "2395.25",
                    "close": "2405.75",
                    "volume": "1000",
                },
                {
                    "datetime": "2024-05-20 11:00:00",
                    "open": "2405.75",
                    "high": "2415.0",
                    "low": "2400.0",
                    "close": "2412.0",
                    "volume": "",
                },
            ],
            "status": "ok",
        }

        provider = TwelveDataProvider(api_key="dummy", http_fetch=lambda url: payload)
        candles = provider.fetch_ohlc("XAUUSD", "H1")

        self.assertEqual(2, len(candles))
        self.assertEqual(Decimal("2400.5"), candles[0].open)
        self.assertEqual(Decimal("1000"), candles[0].volume)
        self.assertIsNone(candles[1].volume)
        self.assertEqual(UTC, candles[0].timestamp_utc.tzinfo)

    def test_api_error_payload_raises(self) -> None:
        provider = TwelveDataProvider(
            api_key="dummy",
            http_fetch=lambda url: {"status": "error", "message": "bad key"},
        )

        with self.assertRaises(ProviderError):
            provider.fetch_ohlc("XAUUSD", "H1")

    def test_unsupported_symbol_raises(self) -> None:
        provider = TwelveDataProvider(api_key="dummy", http_fetch=lambda url: {})
        with self.assertRaises(ProviderError):
            provider.fetch_ohlc("EURUSD", "H1")


if __name__ == "__main__":
    unittest.main()
