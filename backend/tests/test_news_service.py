import unittest
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base
from app.models import DolAssessment, LiquidityLevel, NewsCatalystEvent  # noqa: F401
from app.schemas.market import MarketDataInput
from app.schemas.news import NewsCatalystEvaluateRequest
from app.services.market_service import MarketService
from app.services.news_service import NewsCatalystService
from app.utils.timezone import NY_TZ


class NewsCatalystServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=engine)
        self.db = Session(bind=engine)
        target = self.level("PDL", "SSL", 2350)
        invalidation = self.level("PDH", "BSL", 2500, "taken")
        self.db.add(
            DolAssessment(
                symbol="XAUUSD",
                lifecycle_status="Active",
                delivery_direction="delivery_down",
                primary_level_id=target.id,
                engineered_level_id=invalidation.id,
                objective_quality="true_objective",
                status_reason="bearish news fixture",
                old_objective_resolved=False,
                displacement_confirmed=True,
                timing_confirmed=True,
                prior_narrative_resolved=False,
                as_of_utc=datetime(2026, 5, 20, 12, tzinfo=UTC),
            )
        )
        self.db.commit()
        self.market(datetime(2026, 5, 20, 11, 30, tzinfo=UTC), 2460, 2470, 2450, 2465)
        self.market(datetime(2026, 5, 20, 12, tzinfo=UTC), 2465, 2480, 2455, 2475)

    def tearDown(self) -> None:
        self.db.close()

    def level(self, level_type: str, side: str, price: int, status: str = "active") -> LiquidityLevel:
        level = LiquidityLevel(
            symbol="XAUUSD",
            level_type=level_type,
            liquidity_side=side,
            price=Decimal(price),
            status=status,
            source_timeframe="D",
            source_period_start_ny=datetime(2026, 5, 19, 0, tzinfo=NY_TZ),
            source_period_end_ny=datetime(2026, 5, 20, 5, tzinfo=NY_TZ),
            as_of_utc=datetime(2026, 5, 20, 12, tzinfo=UTC),
            status_reason="fixture",
        )
        self.db.add(level)
        self.db.commit()
        self.db.refresh(level)
        return level

    def market(self, timestamp: datetime, open_price: int, high: int, low: int, close: int) -> None:
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

    def request(self, as_of: datetime) -> NewsCatalystEvaluateRequest:
        return NewsCatalystEvaluateRequest(
            symbol="XAUUSD",
            event_name="CPI",
            impact="high",
            scheduled_at_utc=datetime(2026, 5, 20, 12, 30, tzinfo=UTC),
            as_of_utc=as_of,
        )

    def test_pre_news_catalyst_blocks_execution(self) -> None:
        event = NewsCatalystService.evaluate(
            self.db, self.request(datetime(2026, 5, 20, 12, 15, tzinfo=UTC))
        )

        self.assertEqual("pre_news_accumulation", event.news_phase)
        self.assertEqual("waiting_release", event.catalyst_status)
        self.assertIn("high-impact CPI is pending", event.no_trade_reason)

    def test_post_news_creates_previous_news_liquidity_and_remains_no_trade(self) -> None:
        event = NewsCatalystService.evaluate(
            self.db, self.request(datetime(2026, 5, 20, 13, tzinfo=UTC))
        )
        levels = {
            level.level_type: level
            for level in self.db.query(LiquidityLevel)
            .filter(LiquidityLevel.level_type.in_(["NEWS_HIGH", "NEWS_LOW"]))
            .all()
        }

        self.assertEqual("post_news_repricing", event.news_phase)
        self.assertEqual("inconclusive", event.catalyst_status)
        self.assertIn("No Trade", event.no_trade_reason)
        self.assertEqual(2480, levels["NEWS_HIGH"].price)
        self.assertEqual(2450, levels["NEWS_LOW"].price)


if __name__ == "__main__":
    unittest.main()
