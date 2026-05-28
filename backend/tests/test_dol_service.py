import unittest
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base
from app.models import DolAssessment, LiquidityLevel, MarketSnapshot, SweepEvent  # noqa: F401
from app.routers.dol import _response
from app.schemas.market import MarketDataInput
from app.services.dol_service import DolService
from app.services.market_service import MarketService
from app.utils.timezone import NY_TZ


class DolServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=engine)
        self.db = Session(bind=engine)
        MarketService.create_snapshot(
            self.db,
            MarketDataInput(
                symbol="XAUUSD",
                timeframe="M15",
                timestamp_utc=datetime(2026, 5, 20, 15, tzinfo=UTC),
                open=2450,
                high=2455,
                low=2445,
                close=2450,
            ),
        )

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
            as_of_utc=datetime(2026, 5, 20, 15, tzinfo=UTC),
            status_reason="test level",
        )
        self.db.add(level)
        self.db.commit()
        self.db.refresh(level)
        return level

    def event(
        self,
        level: LiquidityLevel,
        status: str,
        event_time: datetime,
    ) -> SweepEvent:
        interaction = MarketService.get_latest(self.db, "XAUUSD", "M15")
        event = SweepEvent(
            liquidity_level_id=level.id,
            interaction_snapshot_id=interaction.id,
            symbol="XAUUSD",
            level_type=level.level_type,
            liquidity_side=level.liquidity_side,
            level_price=level.price,
            session="NY AM",
            session_anchor="09 NY",
            daily_quarter="Q3",
            micro_quarter_90m="Q3.3",
            sweep_status=status,
            confirmation_status="confirmed_reversal_displacement",
            displacement_detected=True,
            relevant_timing=True,
            narrative_alignment="unknown",
            reason="confirmed test event",
            target_liquidity=None,
            detected_at_utc=event_time,
        )
        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)
        return event

    def test_confirmed_reversal_selects_htf_primary_and_engineered_liquidity(self) -> None:
        swept_high = self.level("PDH", "BSL", 2470, "taken")
        target = self.level("PDL", "SSL", 2400)
        intraday = self.level("ASIA_LOW", "SSL", 2430)
        self.event(swept_high, "Valid Sweep", datetime(2026, 5, 20, 14, tzinfo=UTC))

        assessment = DolService.evaluate(self.db, "XAUUSD")
        response = _response(self.db, assessment)

        self.assertEqual("Active", assessment.lifecycle_status)
        self.assertEqual("delivery_down", assessment.delivery_direction)
        self.assertEqual(target.id, assessment.primary_level_id)
        self.assertEqual(intraday.id, assessment.intraday_level_id)
        self.assertEqual(swept_high.id, assessment.engineered_level_id)
        self.assertEqual("Narrative Ready - wait for later execution confirmation layers", response.execution_status)

    def test_opposing_objective_does_not_replace_unresolved_dol(self) -> None:
        swept_high = self.level("PDH", "BSL", 2470, "taken")
        old_target = self.level("PDL", "SSL", 2400)
        swept_low = self.level("LONDON_LOW", "SSL", 2420, "taken")
        new_target = self.level("PWH", "BSL", 2500)
        self.event(swept_high, "Valid Sweep", datetime(2026, 5, 20, 13, tzinfo=UTC))
        initial = DolService.evaluate(self.db, "XAUUSD")
        self.event(swept_low, "Valid Sweep", datetime(2026, 5, 20, 14, tzinfo=UTC))

        weakened = DolService.evaluate(self.db, "XAUUSD")

        self.assertEqual(old_target.id, initial.primary_level_id)
        self.assertEqual("Weakening", weakened.lifecycle_status)
        self.assertEqual(old_target.id, weakened.primary_level_id)
        self.assertEqual(new_target.id, weakened.secondary_level_id)
        self.assertIn("change rejected", weakened.status_reason)

    def test_shift_requires_resolved_old_objective_and_confirmed_new_delivery(self) -> None:
        swept_high = self.level("PDH", "BSL", 2470, "taken")
        old_target = self.level("PDL", "SSL", 2400)
        swept_low = self.level("LONDON_LOW", "SSL", 2420, "taken")
        new_target = self.level("PWH", "BSL", 2500)
        self.event(swept_high, "Valid Sweep", datetime(2026, 5, 20, 13, tzinfo=UTC))
        DolService.evaluate(self.db, "XAUUSD")
        self.event(swept_low, "Valid Sweep", datetime(2026, 5, 20, 14, tzinfo=UTC))
        DolService.evaluate(self.db, "XAUUSD")
        old_target.status = "taken"
        self.db.commit()

        shifted = DolService.evaluate(self.db, "XAUUSD")

        self.assertEqual("Shift Confirmed", shifted.lifecycle_status)
        self.assertEqual(new_target.id, shifted.primary_level_id)
        self.assertTrue(shifted.old_objective_resolved)
        self.assertTrue(shifted.displacement_confirmed)
        self.assertTrue(shifted.timing_confirmed)
        self.assertTrue(shifted.prior_narrative_resolved)

    def test_no_confirmed_sweep_returns_shift_pending_no_trade(self) -> None:
        self.level("PDH", "BSL", 2470)
        assessment = DolService.evaluate(self.db, "XAUUSD")
        response = _response(self.db, assessment)

        self.assertEqual("Shift Pending", assessment.lifecycle_status)
        self.assertIsNone(assessment.primary_level_id)
        self.assertEqual("No Trade - DOL is not confirmed for execution", response.execution_status)


if __name__ == "__main__":
    unittest.main()
