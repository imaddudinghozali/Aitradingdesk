import unittest
from datetime import UTC, datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base
from app.models import MarketSnapshot  # noqa: F401
from app.schemas.market import MarketDataInput
from app.services.market_service import MarketService
from app.services.multitf_dol_service import MultiTfDolService


class MultiTfDolServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=engine)
        self.db = Session(bind=engine)

    def tearDown(self) -> None:
        self.db.close()

    def candle(self, tf, ts, o, h, l, c):
        MarketService.create_snapshot(
            self.db,
            MarketDataInput(
                symbol="XAUUSD", timeframe=tf, timestamp_utc=ts,
                open=o, high=h, low=l, close=c,
            ),
        )

    def test_daily_against_htf_flags_major_conflict(self) -> None:
        # Monthly + Weekly bullish (low printed first, close > open), Daily bearish.
        self.candle("D", datetime(2026, 5, 1, tzinfo=UTC), 2400, 2410, 2390, 2405)
        self.candle("D", datetime(2026, 5, 27, tzinfo=UTC), 2480, 2520, 2470, 2500)
        self.candle("D", datetime(2026, 5, 28, tzinfo=UTC), 2490, 2510, 2485, 2505)
        # Daily H1 on NY date 2026-05-28: high first then deliver down (OHLC, close < open).
        self.candle("H1", datetime(2026, 5, 28, 10, tzinfo=UTC), 2500, 2510, 2495, 2498)
        self.candle("H1", datetime(2026, 5, 28, 14, tzinfo=UTC), 2498, 2500, 2470, 2475)

        ctx = MultiTfDolService.evaluate(
            self.db, "XAUUSD", as_of_utc=datetime(2026, 5, 28, 14, tzinfo=UTC)
        )

        by_tf = {c.timeframe: c for c in ctx.contexts}
        self.assertEqual("up", by_tf["Monthly"].frame.draw)
        self.assertEqual("up", by_tf["Weekly"].frame.draw)
        self.assertEqual("down", by_tf["Daily"].frame.draw)
        self.assertEqual("OHLC", by_tf["Daily"].frame.model)
        self.assertEqual("corrective", by_tf["Daily"].parent_status)
        self.assertEqual("major", ctx.conflict_level)
        self.assertIn("No Trade", ctx.execution_hint)

    def test_aligned_when_all_draws_agree(self) -> None:
        self.candle("D", datetime(2026, 5, 1, tzinfo=UTC), 2400, 2410, 2390, 2405)
        self.candle("D", datetime(2026, 5, 27, tzinfo=UTC), 2480, 2520, 2470, 2500)
        self.candle("D", datetime(2026, 5, 28, tzinfo=UTC), 2490, 2520, 2485, 2515)
        # Daily H1 bullish: low first then deliver up (OLHC, close > open).
        self.candle("H1", datetime(2026, 5, 28, 10, tzinfo=UTC), 2490, 2495, 2480, 2492)
        self.candle("H1", datetime(2026, 5, 28, 14, tzinfo=UTC), 2492, 2525, 2490, 2520)

        ctx = MultiTfDolService.evaluate(
            self.db, "XAUUSD", as_of_utc=datetime(2026, 5, 28, 14, tzinfo=UTC)
        )

        by_tf = {c.timeframe: c for c in ctx.contexts}
        self.assertEqual("up", by_tf["Daily"].frame.draw)
        self.assertEqual("aligned", by_tf["Daily"].parent_status)
        self.assertEqual("none", ctx.conflict_level)
        self.assertIn("Aligned", ctx.execution_hint)


if __name__ == "__main__":
    unittest.main()
