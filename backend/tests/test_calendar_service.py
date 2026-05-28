import unittest
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base
from app.models import (  # noqa: F401
    DolAssessment,
    EconomicEvent,
    LiquidityLevel,
    MarketSnapshot,
    NewsCatalystEvent,
)
from app.schemas.market import MarketDataInput
from app.services.calendar_providers.mock_provider import (
    MockCalendarProvider,
    make_event,
)
from app.services.calendar_providers.trading_economics_provider import (
    TradingEconomicsProvider,
)
from app.services.calendar_service import CalendarService
from app.services.market_service import MarketService
from app.utils.timezone import NY_TZ


class CalendarServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=engine)
        self.db = Session(bind=engine)

    def tearDown(self) -> None:
        self.db.close()

    def _seed_dol_and_market(self, when: datetime) -> None:
        level_target = LiquidityLevel(
            symbol="XAUUSD",
            level_type="PDL",
            liquidity_side="SSL",
            price=Decimal(2350),
            status="active",
            source_timeframe="D",
            source_period_start_ny=datetime(2026, 5, 19, 0, tzinfo=NY_TZ),
            source_period_end_ny=datetime(2026, 5, 20, 5, tzinfo=NY_TZ),
            as_of_utc=when,
            status_reason="fixture",
        )
        level_inv = LiquidityLevel(
            symbol="XAUUSD",
            level_type="PDH",
            liquidity_side="BSL",
            price=Decimal(2500),
            status="taken",
            source_timeframe="D",
            source_period_start_ny=datetime(2026, 5, 19, 0, tzinfo=NY_TZ),
            source_period_end_ny=datetime(2026, 5, 20, 5, tzinfo=NY_TZ),
            as_of_utc=when,
            status_reason="fixture",
        )
        self.db.add_all([level_target, level_inv])
        self.db.commit()
        self.db.refresh(level_target)
        self.db.refresh(level_inv)

        self.db.add(
            DolAssessment(
                symbol="XAUUSD",
                lifecycle_status="Active",
                delivery_direction="delivery_down",
                primary_level_id=level_target.id,
                engineered_level_id=level_inv.id,
                objective_quality="true_objective",
                status_reason="fixture",
                old_objective_resolved=False,
                displacement_confirmed=True,
                timing_confirmed=True,
                prior_narrative_resolved=False,
                as_of_utc=when,
            )
        )
        self.db.commit()

        MarketService.create_snapshot(
            self.db,
            MarketDataInput(
                symbol="XAUUSD",
                timeframe="M15",
                timestamp_utc=when - timedelta(minutes=15),
                open=2460,
                high=2470,
                low=2450,
                close=2465,
            ),
        )
        MarketService.create_snapshot(
            self.db,
            MarketDataInput(
                symbol="XAUUSD",
                timeframe="M15",
                timestamp_utc=when,
                open=2465,
                high=2480,
                low=2455,
                close=2475,
            ),
        )

    def test_refresh_inserts_and_marks_relevant(self) -> None:
        now = datetime.now(tz=UTC)
        future = now + timedelta(hours=6)
        provider = MockCalendarProvider(
            [
                make_event("US CPI YoY", "United States", "high", future),
                make_event("ISM Manufacturing", "United States", "medium", future + timedelta(hours=1)),
                make_event("CPI MoM", "Germany", "medium", future + timedelta(hours=2)),
            ]
        )

        outcome = CalendarService.refresh(self.db, provider)

        self.assertEqual(2, outcome.fetched)
        self.assertEqual(2, outcome.inserted)
        self.assertEqual(0, outcome.updated)
        self.assertEqual(1, outcome.relevant)

        rows = self.db.query(EconomicEvent).order_by(EconomicEvent.scheduled_at_utc).all()
        relevant_us = [r for r in rows if r.is_relevant]
        self.assertEqual(1, len(relevant_us))
        self.assertEqual("US CPI YoY", relevant_us[0].event_name)
        self.assertEqual("high", relevant_us[0].impact)
        self.assertNotIn("Germany", {row.country for row in rows})

    def test_refresh_updates_existing_event_when_actual_arrives(self) -> None:
        now = datetime.now(tz=UTC)
        when = now + timedelta(hours=3)
        provider = MockCalendarProvider(
            [make_event("US CPI YoY", "United States", "high", when, forecast=2.5)]
        )
        CalendarService.refresh(self.db, provider)

        provider2 = MockCalendarProvider(
            [
                make_event(
                    "US CPI YoY",
                    "United States",
                    "high",
                    when,
                    actual=2.7,
                    forecast=2.5,
                )
            ]
        )
        outcome = CalendarService.refresh(self.db, provider2)

        self.assertEqual(1, outcome.fetched)
        self.assertEqual(0, outcome.inserted)
        self.assertEqual(1, outcome.updated)
        row = self.db.query(EconomicEvent).first()
        self.assertEqual(Decimal("2.7"), row.actual)

    def test_sync_to_catalyst_creates_news_event_when_dol_present(self) -> None:
        now = datetime.now(tz=UTC)
        scheduled = now + timedelta(hours=2)
        self._seed_dol_and_market(now)

        provider = MockCalendarProvider(
            [make_event("US CPI YoY", "United States", "high", scheduled)]
        )
        CalendarService.refresh(self.db, provider)

        outcome = CalendarService.sync_to_catalyst(self.db, symbol="XAUUSD")

        self.assertEqual(1, outcome.evaluated)
        self.assertEqual(0, outcome.skipped_missing_dol)
        catalysts = self.db.query(NewsCatalystEvent).all()
        self.assertEqual(1, len(catalysts))
        self.assertEqual("CPI", catalysts[0].event_name)
        self.assertEqual("pre_news_accumulation", catalysts[0].news_phase)

    def test_sync_skips_when_dol_missing(self) -> None:
        now = datetime.now(tz=UTC)
        scheduled = now + timedelta(hours=2)
        provider = MockCalendarProvider(
            [make_event("US CPI YoY", "United States", "high", scheduled)]
        )
        CalendarService.refresh(self.db, provider)

        outcome = CalendarService.sync_to_catalyst(self.db, symbol="XAUUSD")

        self.assertEqual(0, outcome.evaluated)
        self.assertEqual(1, outcome.skipped_missing_dol)

    def test_upcoming_filters_relevant_only(self) -> None:
        now = datetime.now(tz=UTC)
        provider = MockCalendarProvider(
            [
                make_event("US CPI YoY", "United States", "high", now + timedelta(hours=2)),
                make_event("ISM PMI", "United States", "medium", now + timedelta(hours=4)),
                make_event("Powell Speech", "United States", "high", now + timedelta(hours=10)),
            ]
        )
        CalendarService.refresh(self.db, provider)

        rel = CalendarService.upcoming(self.db, hours=24, relevant_only=True)
        all_events = CalendarService.upcoming(self.db, hours=24, relevant_only=False)

        self.assertEqual(2, len(rel))
        self.assertEqual(3, len(all_events))


class TradingEconomicsProviderTest(unittest.TestCase):
    def test_parses_payload(self) -> None:
        payload = [
            {
                "CalendarId": "12345",
                "Country": "United States",
                "Event": "Inflation Rate YoY",
                "Date": "2024-05-15T12:30:00",
                "Actual": "3.4%",
                "Forecast": "3.4%",
                "Previous": "3.5%",
                "Importance": 3,
            },
            {
                "Country": "United States",
                "Event": "Initial Jobless Claims",
                "Date": "2024-05-16T12:30:00",
                "Forecast": "215K",
                "Previous": "222K",
                "Importance": 2,
            },
        ]
        provider = TradingEconomicsProvider(http_fetch=lambda url: payload)
        start = datetime(2024, 5, 14, tzinfo=UTC)
        end = datetime(2024, 5, 17, tzinfo=UTC)
        events = provider.fetch_events(start, end, ["United States"])

        self.assertEqual(2, len(events))
        self.assertEqual("high", events[0].impact)
        self.assertEqual(Decimal("3.4"), events[0].actual)
        self.assertEqual("medium", events[1].impact)
        self.assertEqual(Decimal("215"), events[1].forecast)
        self.assertEqual("12345", events[0].source_id)


if __name__ == "__main__":
    unittest.main()
