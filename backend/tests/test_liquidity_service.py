import unittest
from datetime import UTC, datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base
from app.engines.time_engine import TimeEngine
from app.models import LiquidityLevel, MarketSnapshot  # noqa: F401
from app.schemas.liquidity import LiquidityRefreshRequest, LiquidityStatusUpdate
from app.schemas.market import MarketDataInput
from app.services.liquidity_service import LiquidityService
from app.services.market_service import MarketService


class LiquidityServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=engine)
        self.db = Session(bind=engine)

    def tearDown(self) -> None:
        self.db.close()

    def add_snapshot(
        self,
        timeframe: str,
        timestamp: datetime,
        high: int,
        low: int,
        open_price: int | None = None,
        close: int | None = None,
    ) -> None:
        MarketService.create_snapshot(
            self.db,
            MarketDataInput(
                symbol="XAUUSD",
                timeframe=timeframe,
                timestamp_utc=timestamp,
                open=open_price or low,
                high=high,
                low=low,
                close=close or high,
            ),
        )

    def test_refresh_builds_base_liquidity_map_and_status(self) -> None:
        self.add_snapshot("D", datetime(2026, 5, 12, 4, tzinfo=UTC), 2410, 2380)
        self.add_snapshot("D", datetime(2026, 5, 15, 4, tzinfo=UTC), 2420, 2370)
        self.add_snapshot("D", datetime(2026, 5, 18, 4, tzinfo=UTC), 2440, 2390)
        self.add_snapshot("D", datetime(2026, 5, 19, 4, tzinfo=UTC), 2450, 2400)
        self.add_snapshot("M15", datetime(2026, 5, 20, 2, tzinfo=UTC), 2440, 2415)
        self.add_snapshot("M15", datetime(2026, 5, 20, 5, tzinfo=UTC), 2444, 2410)
        self.add_snapshot("M15", datetime(2026, 5, 20, 10, tzinfo=UTC), 2448, 2420)
        self.add_snapshot("M15", datetime(2026, 5, 20, 12, 30, tzinfo=UTC), 2449, 2425)
        self.add_snapshot("M15", datetime(2026, 5, 20, 15, tzinfo=UTC), 2452, 2405)

        _, levels, missing = LiquidityService.refresh_levels(
            self.db,
            LiquidityRefreshRequest(
                symbol="XAUUSD",
                as_of_utc=datetime(2026, 5, 20, 15, tzinfo=UTC),
            ),
        )
        by_type = {level.level_type: level for level in levels}

        self.assertEqual({"PMH", "PML", "PYH", "PYL"}, set(missing))
        self.assertEqual(
            set(LiquidityService.EXPECTED_LEVEL_TYPES) - set(missing),
            set(by_type),
        )
        self.assertEqual("BSL", by_type["PDH"].liquidity_side)
        self.assertEqual("SSL", by_type["PDL"].liquidity_side)
        self.assertEqual("taken", by_type["PDH"].status)
        self.assertEqual("active", by_type["PWL"].status)
        self.assertEqual("taken", by_type["ASIA_LOW"].status)
        self.assertEqual("taken", by_type["LONDON_HIGH"].status)

        invalidated = LiquidityService.update_status(
            self.db,
            by_type["PDH"].id,
            LiquidityStatusUpdate(status="invalidated", reason="Narrative invalidated this level"),
        )
        self.assertIsNotNone(invalidated)
        self.assertEqual("invalidated", invalidated.status)

        _, refreshed, _ = LiquidityService.refresh_levels(
            self.db,
            LiquidityRefreshRequest(
                symbol="XAUUSD",
                as_of_utc=datetime(2026, 5, 20, 15, tzinfo=UTC),
            ),
        )
        self.assertEqual(
            "invalidated",
            {level.level_type: level for level in refreshed}["PDH"].status,
        )

    def test_refresh_builds_previous_month_and_year_liquidity_when_data_exists(self) -> None:
        self.add_snapshot("D", datetime(2025, 11, 10, 5, tzinfo=UTC), 2300, 2100)
        self.add_snapshot("D", datetime(2025, 12, 10, 5, tzinfo=UTC), 2350, 2150)
        self.add_snapshot("D", datetime(2026, 4, 10, 4, tzinfo=UTC), 2400, 2200)
        self.add_snapshot("D", datetime(2026, 4, 20, 4, tzinfo=UTC), 2420, 2180)
        self.add_snapshot("D", datetime(2026, 5, 19, 4, tzinfo=UTC), 2450, 2380)

        _, levels, _ = LiquidityService.refresh_levels(
            self.db,
            LiquidityRefreshRequest(
                symbol="XAUUSD",
                as_of_utc=datetime(2026, 5, 20, 15, tzinfo=UTC),
            ),
        )
        by_type = {level.level_type: level for level in levels}

        self.assertEqual(2420, by_type["PMH"].price)
        self.assertEqual(2180, by_type["PML"].price)
        self.assertEqual(2350, by_type["PYH"].price)
        self.assertEqual(2100, by_type["PYL"].price)

    def test_ny_open_uses_ny_session_and_active_anchor(self) -> None:
        context = TimeEngine.get_time_context(datetime(2026, 5, 20, 13, 30, tzinfo=UTC))
        self.assertEqual("NY AM", context["session"])
        self.assertEqual("09 NY", context["session_anchor"])
        self.assertEqual("Q2", context["yearly_quarter"])
        self.assertEqual("Q3", context["monthly_quarter"])
        self.assertEqual("Q3", context["weekly_quarter"])
        self.assertEqual("Q3", context["daily_quarter"])


if __name__ == "__main__":
    unittest.main()
