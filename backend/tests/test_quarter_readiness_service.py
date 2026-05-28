import unittest
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base
from app.models import DolAssessment, IrlErlMapping, LiquidityLevel, SweepEvent  # noqa: F401
from app.schemas.market import MarketDataInput
from app.services.market_service import MarketService
from app.services.quarter_readiness_service import QuarterReadinessService
from app.utils.timezone import NY_TZ


class QuarterReadinessServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=engine)
        self.db = Session(bind=engine)
        target = self.level("PWH", "BSL", 2500)
        engineered = self.level("PWL", "SSL", 2400, "taken")
        self.dol = DolAssessment(
            symbol="XAUUSD",
            lifecycle_status="Active",
            delivery_direction="delivery_up",
            primary_level_id=target.id,
            engineered_level_id=engineered.id,
            objective_quality="true_objective",
            status_reason="active delivery",
            old_objective_resolved=False,
            displacement_confirmed=True,
            timing_confirmed=True,
            prior_narrative_resolved=False,
            as_of_utc=datetime(2026, 5, 20, 14, tzinfo=UTC),
        )
        self.db.add(self.dol)
        self.db.commit()
        self.db.refresh(self.dol)
        self.mapping = IrlErlMapping(
            symbol="XAUUSD",
            dol_assessment_id=self.dol.id,
            direction_flow="ERL -> IRL -> ERL",
            mapping_status="aligned",
            status_reason="aligned direction",
            as_of_utc=datetime(2026, 5, 20, 14, tzinfo=UTC),
        )
        self.db.add(self.mapping)
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
            as_of_utc=datetime(2026, 5, 20, 14, tzinfo=UTC),
            status_reason="test level",
        )
        self.db.add(level)
        self.db.commit()
        self.db.refresh(level)
        return level

    def market(self, timestamp: datetime):
        return MarketService.create_snapshot(
            self.db,
            MarketDataInput(
                symbol="XAUUSD",
                timeframe="M15",
                timestamp_utc=timestamp,
                open=2450,
                high=2455,
                low=2445,
                close=2450,
            ),
        )

    def sweep(self, snapshot, displacement: bool = True) -> SweepEvent:
        event = SweepEvent(
            liquidity_level_id=self.dol.engineered_level_id,
            interaction_snapshot_id=snapshot.id,
            symbol="XAUUSD",
            level_type="PWL",
            liquidity_side="SSL",
            level_price=Decimal(2400),
            session=snapshot.session,
            session_anchor=snapshot.session_anchor,
            daily_quarter=snapshot.daily_quarter,
            micro_quarter_90m=snapshot.micro_quarter_90m,
            sweep_status="Valid Sweep" if displacement else "Liquidity Tap",
            confirmation_status="confirmed_reversal_displacement" if displacement else "waiting_confirmation",
            displacement_detected=displacement,
            relevant_timing=True,
            narrative_alignment="unknown",
            reason="quarter fixture",
            detected_at_utc=snapshot.timestamp_utc,
        )
        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)
        return event

    def test_new_quarter_without_interaction_is_forming_and_no_trade(self) -> None:
        self.market(datetime(2026, 5, 20, 10, 15, tzinfo=UTC))

        assessment = QuarterReadinessService.evaluate(self.db, "XAUUSD")

        self.assertEqual("Forming", assessment.quarter_status)
        self.assertEqual("No Trade", assessment.gate_decision)
        self.assertFalse(assessment.quarter_execution_allowed)
        self.assertIn("Current Q3", assessment.next_valid_window)

    def test_liquidity_tap_keeps_quarter_in_manipulation_phase(self) -> None:
        snapshot = self.market(datetime(2026, 5, 20, 13, tzinfo=UTC))
        self.sweep(snapshot, displacement=False)

        assessment = QuarterReadinessService.evaluate(self.db, "XAUUSD")

        self.assertEqual("Manipulation Phase", assessment.quarter_status)
        self.assertEqual("No Trade", assessment.gate_decision)
        self.assertIn("displacement", assessment.status_reason)

    def test_displacement_without_bound_dol_is_expansion_ready(self) -> None:
        snapshot = self.market(datetime(2026, 5, 20, 13, tzinfo=UTC))
        self.sweep(snapshot)

        assessment = QuarterReadinessService.evaluate(self.db, "XAUUSD")

        self.assertEqual("Expansion Ready", assessment.quarter_status)
        self.assertTrue(assessment.quarter_execution_allowed)
        self.assertEqual("Waiting Confirmation", assessment.gate_decision)

    def test_aligned_source_sweep_is_expansion_active(self) -> None:
        snapshot = self.market(datetime(2026, 5, 20, 13, tzinfo=UTC))
        event = self.sweep(snapshot)
        self.dol.source_sweep_event_id = event.id
        self.db.commit()

        assessment = QuarterReadinessService.evaluate(self.db, "XAUUSD")

        self.assertEqual("Expansion Active", assessment.quarter_status)
        self.assertTrue(assessment.quarter_execution_allowed)
        self.assertIn("active DOL", assessment.status_reason)

    def test_last_hour_is_closed_for_new_entry(self) -> None:
        self.market(datetime(2026, 5, 20, 15, 30, tzinfo=UTC))

        assessment = QuarterReadinessService.evaluate(self.db, "XAUUSD")

        self.assertEqual("Closed / Late Entry", assessment.quarter_status)
        self.assertEqual("No Trade", assessment.gate_decision)
        self.assertIn("Next Q4", assessment.next_valid_window)

    def test_direction_conflict_is_failure_risk_and_no_trade(self) -> None:
        snapshot = self.market(datetime(2026, 5, 20, 13, tzinfo=UTC))
        event = self.sweep(snapshot)
        event.liquidity_side = "BSL"
        self.db.commit()

        assessment = QuarterReadinessService.evaluate(self.db, "XAUUSD")

        self.assertEqual("Failure Risk", assessment.quarter_status)
        self.assertEqual("No Trade", assessment.gate_decision)
        self.assertIn("away from", assessment.status_reason)


if __name__ == "__main__":
    unittest.main()
