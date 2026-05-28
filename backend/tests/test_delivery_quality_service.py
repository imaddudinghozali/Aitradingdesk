import unittest
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base
from app.models import DolAssessment, LiquidityLevel, NarrativeLedger, SweepEvent  # noqa: F401
from app.schemas.market import MarketDataInput
from app.services.delivery_quality_service import DeliveryQualityService
from app.services.market_service import MarketService
from app.utils.timezone import NY_TZ


class DeliveryQualityServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=engine)
        self.db = Session(bind=engine)
        self.target = self.level("PWH", "BSL", 2500)
        self.invalidation = self.level("PWL", "SSL", 2400, "taken")
        self.dol = DolAssessment(
            symbol="XAUUSD",
            lifecycle_status="Active",
            delivery_direction="delivery_up",
            primary_level_id=self.target.id,
            engineered_level_id=self.invalidation.id,
            objective_quality="true_objective",
            status_reason="bullish fixture",
            old_objective_resolved=False,
            displacement_confirmed=True,
            timing_confirmed=True,
            prior_narrative_resolved=False,
            as_of_utc=datetime(2026, 5, 20, 13, tzinfo=UTC),
        )
        self.db.add(self.dol)
        self.db.commit()
        self.db.refresh(self.dol)
        self.ledger = NarrativeLedger(
            symbol="XAUUSD",
            dol_assessment_id=self.dol.id,
            active_dol="PWH BSL at 2500",
            delivery_direction="delivery_up",
            target_level_id=self.target.id,
            target_liquidity="PWH BSL at 2500",
            invalidation_level_id=self.invalidation.id,
            invalidation_level="PWL SSL at 2400",
            invalidation_price=Decimal(2400),
            invalidation_condition="Two consecutive M15 closes below PWL SSL at 2400 invalidate bullish delivery.",
            next_decision_if_invalidated="Reset DOL identification.",
            reset_required=False,
            continuation_status="active",
            breach_status="clear",
            status_reason="active ledger",
            activated_at_utc=datetime(2026, 5, 20, 13, tzinfo=UTC),
            as_of_utc=datetime(2026, 5, 20, 13, tzinfo=UTC),
        )
        self.db.add(self.ledger)
        self.db.commit()

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
            as_of_utc=datetime(2026, 5, 20, 13, tzinfo=UTC),
            status_reason="fixture",
        )
        self.db.add(level)
        self.db.commit()
        self.db.refresh(level)
        return level

    def candle(self, minute: int, open_price: int, high: int, low: int, close: int):
        return MarketService.create_snapshot(
            self.db,
            MarketDataInput(
                symbol="XAUUSD",
                timeframe="M15",
                timestamp_utc=datetime(2026, 5, 20, 13, minute, tzinfo=UTC),
                open=open_price,
                high=high,
                low=low,
                close=close,
            ),
        )

    def manipulation_sweep(self, interaction_id: int) -> None:
        sweep = SweepEvent(
            liquidity_level_id=self.invalidation.id,
            interaction_snapshot_id=interaction_id,
            symbol="XAUUSD",
            level_type="PWL",
            liquidity_side="SSL",
            level_price=self.invalidation.price,
            session="NY AM",
            session_anchor="09 NY",
            daily_quarter="Q3",
            micro_quarter_90m="Q3.1",
            sweep_status="Manipulation Sweep",
            confirmation_status="confirmed_reversal_displacement",
            displacement_detected=True,
            relevant_timing=True,
            narrative_alignment="aligned",
            reason="engineered SSL sweep",
            detected_at_utc=datetime(2026, 5, 20, 13, tzinfo=UTC),
        )
        self.db.add(sweep)
        self.db.commit()
        self.db.refresh(sweep)
        self.dol.source_sweep_event_id = sweep.id
        self.db.commit()

    def test_single_candle_keeps_expansion_delayed_and_waiting(self) -> None:
        self.candle(0, 2420, 2440, 2415, 2435)

        assessment = DeliveryQualityService.evaluate(self.db, "XAUUSD")

        self.assertEqual("delayed expansion", assessment.delivery_tempo)
        self.assertEqual("weak expansion", assessment.expansion_quality)
        self.assertEqual("waiting", assessment.expansion_status)

    def test_clean_drive_without_retracement_remains_compressed_delivery(self) -> None:
        self.candle(0, 2420, 2440, 2415, 2435)
        self.candle(15, 2437, 2460, 2435, 2455)

        assessment = DeliveryQualityService.evaluate(self.db, "XAUUSD")

        self.assertTrue(assessment.clean_displacement)
        self.assertEqual("compressed delivery", assessment.delivery_tempo)
        self.assertEqual("weak expansion", assessment.expansion_quality)
        self.assertEqual("waiting", assessment.expansion_status)
        self.assertIn("retracement", assessment.status_reason)

    def test_clean_delivery_with_confirmed_retracement_is_healthy_expansion(self) -> None:
        self.candle(0, 2420, 2440, 2415, 2435)
        self.candle(15, 2437, 2460, 2435, 2455)

        assessment = DeliveryQualityService.evaluate(
            self.db,
            "XAUUSD",
            valid_retracement=True,
            poi_reference="M15 bullish FVG",
        )

        self.assertTrue(assessment.clean_displacement)
        self.assertTrue(assessment.valid_retracement)
        self.assertEqual("M15 bullish FVG", assessment.poi_reference)
        self.assertEqual("aggressive delivery", assessment.delivery_tempo)
        self.assertEqual("healthy expansion", assessment.expansion_quality)
        self.assertEqual("valid", assessment.expansion_status)
        self.assertIn("CISD/MSS", assessment.execution_impact)

    def test_heavy_overlap_is_slow_weak_delivery(self) -> None:
        self.candle(0, 2420, 2440, 2410, 2435)
        self.candle(15, 2432, 2442, 2415, 2425)

        assessment = DeliveryQualityService.evaluate(self.db, "XAUUSD")

        self.assertTrue(assessment.overlap_heavy)
        self.assertEqual("slow delivery", assessment.delivery_tempo)
        self.assertEqual("weak expansion", assessment.expansion_quality)
        self.assertIn("overlap heavily", assessment.status_reason)
        self.assertEqual("failed", self.ledger.continuation_status)
        self.assertEqual("Shift Pending", self.dol.lifecycle_status)

    def test_manipulation_without_clean_follow_through_is_engineered(self) -> None:
        first = self.candle(0, 2420, 2440, 2410, 2435)
        self.candle(15, 2432, 2442, 2415, 2425)
        self.manipulation_sweep(first.id)

        assessment = DeliveryQualityService.evaluate(self.db, "XAUUSD")

        self.assertTrue(assessment.engineered_expansion)
        self.assertEqual("compressed delivery", assessment.delivery_tempo)
        self.assertEqual("engineered expansion", assessment.expansion_quality)
        self.assertEqual("invalidated", assessment.expansion_status)
        self.assertIn("No Trade", assessment.execution_impact)

    def test_target_then_failed_continuation_is_terminal_expansion(self) -> None:
        self.candle(0, 2470, 2505, 2465, 2495)
        self.candle(15, 2492, 2494, 2460, 2465)

        assessment = DeliveryQualityService.evaluate(self.db, "XAUUSD")

        self.assertTrue(assessment.target_reached)
        self.assertTrue(assessment.failed_continuation)
        self.assertTrue(assessment.terminal_expansion)
        self.assertEqual("exhausted expansion", assessment.delivery_tempo)
        self.assertEqual("terminal expansion", assessment.expansion_quality)
        self.assertIn("No Trade", assessment.execution_impact)
        self.assertEqual("failed", self.ledger.continuation_status)
        self.assertTrue(self.ledger.reset_required)
        self.assertEqual("Shift Pending", self.dol.lifecycle_status)


if __name__ == "__main__":
    unittest.main()
