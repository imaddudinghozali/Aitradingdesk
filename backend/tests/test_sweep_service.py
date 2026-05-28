import unittest
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base
from app.models import LiquidityLevel, MarketSnapshot, SweepEvent  # noqa: F401
from app.routers.sweep import scan_sweeps
from app.schemas.market import MarketDataInput
from app.schemas.sweep import NarrativeAlignment, SweepScanRequest
from app.services.market_service import MarketService
from app.services.sweep_service import SweepService
from app.utils.timezone import NY_TZ


class SweepServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=engine)
        self.db = Session(bind=engine)

    def tearDown(self) -> None:
        self.db.close()

    def add_level(self, side: str, price: int, level_type: str = "PDH") -> LiquidityLevel:
        level = LiquidityLevel(
            symbol="XAUUSD",
            level_type=level_type,
            liquidity_side=side,
            price=Decimal(price),
            status="active",
            source_timeframe="D",
            source_period_start_ny=datetime(2026, 5, 19, 0, tzinfo=NY_TZ),
            source_period_end_ny=datetime(2026, 5, 20, 9, tzinfo=NY_TZ),
            as_of_utc=datetime(2026, 5, 20, 15, tzinfo=UTC),
            status_reason="test fixture",
        )
        self.db.add(level)
        self.db.commit()
        self.db.refresh(level)
        return level

    def add_snapshot(
        self,
        timestamp: datetime,
        high: int,
        low: int,
        open_price: int,
        close: int,
    ) -> None:
        MarketService.create_snapshot(
            self.db,
            MarketDataInput(
                symbol="XAUUSD",
                timeframe="M15",
                timestamp_utc=timestamp,
                open=open_price,
                high=high,
                low=low,
                close=close,
            ),
        )

    def scan(self, alignment: NarrativeAlignment = NarrativeAlignment.UNKNOWN):
        _, events, waiting = SweepService.scan(
            self.db,
            SweepScanRequest(
                symbol="XAUUSD",
                timeframe="M15",
                as_of_utc=datetime(2026, 5, 20, 15, tzinfo=UTC),
                narrative_alignment=alignment,
            ),
        )
        return events[0], waiting

    def test_penetration_with_reclaim_is_turtle_soup(self) -> None:
        self.add_level("BSL", 2450)
        self.add_snapshot(datetime(2026, 5, 20, 13, 30, tzinfo=UTC), 2455, 2445, 2449, 2448)

        event, waiting = self.scan()

        self.assertEqual("Turtle Soup", event.sweep_status)
        self.assertEqual("wick_reclaim_confirmed", event.confirmation_status)
        self.assertEqual([], waiting)

    def test_aligned_reversal_displacement_is_manipulation_sweep(self) -> None:
        self.add_level("BSL", 2450)
        self.add_snapshot(datetime(2026, 5, 20, 13, 30, tzinfo=UTC), 2455, 2445, 2449, 2451)
        self.add_snapshot(datetime(2026, 5, 20, 13, 45, tzinfo=UTC), 2451, 2438, 2450, 2440)

        event, waiting = self.scan(NarrativeAlignment.ALIGNED)

        self.assertEqual("Manipulation Sweep", event.sweep_status)
        self.assertTrue(event.displacement_detected)
        self.assertTrue(event.relevant_timing)
        self.assertEqual("NY AM", event.session)
        self.assertEqual("09 NY", event.session_anchor)
        self.assertEqual("Q3", event.daily_quarter)
        self.assertEqual([], waiting)

    def test_reversal_displacement_without_narrative_alignment_is_valid_sweep(self) -> None:
        self.add_level("BSL", 2450)
        self.add_snapshot(datetime(2026, 5, 20, 13, 30, tzinfo=UTC), 2455, 2445, 2449, 2451)
        self.add_snapshot(datetime(2026, 5, 20, 13, 45, tzinfo=UTC), 2451, 2438, 2450, 2440)

        event, waiting = self.scan()

        self.assertEqual("Valid Sweep", event.sweep_status)
        self.assertEqual([], waiting)

    def test_close_beyond_with_continuation_is_true_breakdown(self) -> None:
        self.add_level("SSL", 2400, "PDL")
        self.add_snapshot(datetime(2026, 5, 20, 13, 30, tzinfo=UTC), 2405, 2390, 2402, 2392)
        self.add_snapshot(datetime(2026, 5, 20, 13, 45, tzinfo=UTC), 2391, 2375, 2390, 2380)

        event, waiting = self.scan()

        self.assertEqual("True Breakout / Breakdown", event.sweep_status)
        self.assertTrue(event.displacement_detected)
        self.assertEqual([], waiting)

    def test_touch_without_confirmation_is_liquidity_tap(self) -> None:
        self.add_level("BSL", 2450)
        self.add_snapshot(datetime(2026, 5, 20, 13, 30, tzinfo=UTC), 2450, 2440, 2445, 2449)

        event, waiting = self.scan()
        response = scan_sweeps(
            SweepScanRequest(
                symbol="XAUUSD",
                timeframe="M15",
                as_of_utc=datetime(2026, 5, 20, 15, tzinfo=UTC),
            ),
            self.db,
        )

        self.assertEqual("Liquidity Tap", event.sweep_status)
        self.assertEqual("waiting_confirmation", event.confirmation_status)
        self.assertEqual(1, len(waiting))
        self.assertTrue(response.no_trade_required)

    def test_touch_followed_by_no_penetration_is_false_touch(self) -> None:
        self.add_level("BSL", 2450)
        self.add_snapshot(datetime(2026, 5, 20, 13, 30, tzinfo=UTC), 2450, 2440, 2445, 2449)
        self.add_snapshot(datetime(2026, 5, 20, 13, 45, tzinfo=UTC), 2449, 2441, 2448, 2446)

        event, waiting = self.scan()

        self.assertEqual("False Touch", event.sweep_status)
        self.assertEqual("rejected_as_sweep", event.confirmation_status)
        self.assertEqual(1, len(waiting))


if __name__ == "__main__":
    unittest.main()
