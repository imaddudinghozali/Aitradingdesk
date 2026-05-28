import unittest
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base
from app.models import DolAssessment, LiquidityLevel, MarketSnapshot, NarrativeLedger, SweepEvent  # noqa: F401
from app.schemas.market import MarketDataInput
from app.services.market_service import MarketService
from app.services.mmxm_service import MmxmService
from app.utils.timezone import NY_TZ


class MmxmServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=engine)
        self.db = Session(bind=engine)
        self.target = self.level("PDL", "SSL", 2350)
        self.invalidation = self.level("PDH", "BSL", 2500, "taken")
        self.dol = DolAssessment(
            symbol="XAUUSD",
            lifecycle_status="Active",
            delivery_direction="delivery_down",
            primary_level_id=self.target.id,
            engineered_level_id=self.invalidation.id,
            objective_quality="true_objective",
            status_reason="bearish DOL",
            old_objective_resolved=False,
            displacement_confirmed=True,
            timing_confirmed=True,
            prior_narrative_resolved=False,
            as_of_utc=datetime(2026, 5, 20, 14, tzinfo=UTC),
        )
        self.db.add(self.dol)
        self.db.commit()
        self.db.refresh(self.dol)
        self.ledger = NarrativeLedger(
            symbol="XAUUSD",
            dol_assessment_id=self.dol.id,
            active_dol="PDL SSL at 2350",
            delivery_direction="delivery_down",
            target_level_id=self.target.id,
            target_liquidity="PDL SSL at 2350",
            invalidation_level_id=self.invalidation.id,
            invalidation_level="PDH BSL at 2500",
            invalidation_price=Decimal(2500),
            invalidation_condition="Two consecutive M15 closes above PDH BSL at 2500 invalidate bearish delivery.",
            next_decision_if_invalidated="Reset DOL identification.",
            reset_required=False,
            continuation_status="active",
            breach_status="clear",
            status_reason="active ledger",
            activated_at_utc=datetime(2026, 5, 20, 8, tzinfo=UTC),
            as_of_utc=datetime(2026, 5, 20, 14, tzinfo=UTC),
        )
        self.db.add(self.ledger)
        self.db.commit()
        self.h4(datetime(2026, 5, 20, 8, tzinfo=UTC), 2500, 2400, 2480)
        self.h4(datetime(2026, 5, 20, 14, tzinfo=UTC), 2460, 2380, 2420)

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
            status_reason="fixture",
        )
        self.db.add(level)
        self.db.commit()
        self.db.refresh(level)
        return level

    def h4(
        self,
        timestamp: datetime,
        high: int,
        low: int,
        close: int,
        open_price: int | None = None,
    ) -> MarketSnapshot:
        return MarketService.create_snapshot(
            self.db,
            MarketDataInput(
                symbol="XAUUSD",
                timeframe="H4",
                timestamp_utc=timestamp,
                open=open_price if open_price is not None else close,
                high=high,
                low=low,
                close=close,
            ),
        )

    def sweep(
        self,
        status: str = "Manipulation Sweep",
        level_type: str = "PDH",
    ) -> SweepEvent:
        interaction = self.db.query(MarketSnapshot).order_by(MarketSnapshot.timestamp_utc.desc()).first()
        event = SweepEvent(
            liquidity_level_id=self.invalidation.id,
            interaction_snapshot_id=interaction.id,
            symbol="XAUUSD",
            level_type=level_type,
            liquidity_side="BSL",
            level_price=self.invalidation.price,
            session="NY AM",
            session_anchor="09 NY",
            daily_quarter="Q3",
            micro_quarter_90m="Q3.3",
            sweep_status=status,
            confirmation_status="confirmed_reversal_displacement",
            displacement_detected=True,
            relevant_timing=True,
            narrative_alignment="aligned",
            reason="engineered high sweep",
            detected_at_utc=datetime(2026, 5, 20, 13, tzinfo=UTC),
        )
        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)
        self.dol.source_sweep_event_id = event.id
        self.db.commit()
        return event

    def test_active_down_delivery_is_mmsm_with_ohlc_context(self) -> None:
        assessment = MmxmService.evaluate(self.db, "XAUUSD")

        self.assertEqual("MMSM", assessment.active_model)
        self.assertEqual("OHLC", assessment.candle_delivery)
        self.assertEqual("context_confirmed", assessment.model_status)
        self.assertNotEqual("waiting_range", assessment.quadrant)
        self.assertIn("analytical context only", assessment.status_reason)

    def test_london_liquidity_manipulation_is_valid_judas_in_09_am_context(self) -> None:
        self.sweep(level_type="LONDON_HIGH")

        assessment = MmxmService.evaluate(self.db, "XAUUSD")

        self.assertEqual("valid", assessment.judas_status)
        self.assertIn("Engineered LONDON_HIGH sweep", assessment.judas_reason)
        self.assertIn("09 AM context active", assessment.nine_am_context)
        self.assertIn("LONDON_HIGH BSL was run", assessment.hrlr_status)

    def test_non_london_sweep_does_not_claim_specific_09_am_model(self) -> None:
        self.sweep()

        assessment = MmxmService.evaluate(self.db, "XAUUSD")

        self.assertEqual("valid", assessment.judas_status)
        self.assertIn("London High/Low sweep is not confirmed", assessment.nine_am_context)

    def test_valid_sweep_without_manipulation_label_is_only_potential_judas(self) -> None:
        self.sweep("Valid Sweep")

        assessment = MmxmService.evaluate(self.db, "XAUUSD")

        self.assertEqual("potential", assessment.judas_status)
        self.assertIn("explicit manipulation classification is pending", assessment.judas_reason)

    def test_failed_ledger_neutralizes_model_and_invalidates_judas(self) -> None:
        self.sweep()
        self.ledger.continuation_status = "failed"
        self.ledger.reset_required = True
        self.db.commit()

        assessment = MmxmService.evaluate(self.db, "XAUUSD")

        self.assertEqual("Neutral", assessment.active_model)
        self.assertEqual("invalidated", assessment.model_status)
        self.assertEqual("invalidated", assessment.judas_status)
        self.assertIn("true breakdown", assessment.opr_status)

    def test_opr_low_sweep_with_reclaim_waits_for_displacement(self) -> None:
        self.h4(datetime(2026, 5, 20, 20, tzinfo=UTC), 2450, 2360, 2410)

        assessment = MmxmService.evaluate(self.db, "XAUUSD")

        self.assertIn("Waiting", assessment.opr_status)
        self.assertIn("bullish displacement confirmation is required", assessment.opr_status)

    def test_opr_reclaim_with_aligned_displacement_reports_bounce(self) -> None:
        self.dol.delivery_direction = "delivery_up"
        self.ledger.delivery_direction = "delivery_up"
        self.db.commit()
        self.h4(datetime(2026, 5, 20, 20, tzinfo=UTC), 2450, 2360, 2410)
        self.h4(datetime(2026, 5, 21, 2, tzinfo=UTC), 2470, 2400, 2460, 2415)

        assessment = MmxmService.evaluate(self.db, "XAUUSD")

        self.assertIn("Active bounce", assessment.opr_status)
        self.assertIn("bullish displacement", assessment.opr_status)

    def test_opr_low_break_without_reclaim_reports_true_breakdown(self) -> None:
        self.h4(datetime(2026, 5, 20, 20, tzinfo=UTC), 2410, 2340, 2350)

        assessment = MmxmService.evaluate(self.db, "XAUUSD")

        self.assertIn("true breakdown", assessment.opr_status)

    def test_descending_h4_highs_are_provisional_lrlr_not_execution(self) -> None:
        self.h4(datetime(2026, 5, 20, 20, tzinfo=UTC), 2440, 2370, 2400)

        assessment = MmxmService.evaluate(self.db, "XAUUSD")

        self.assertIn("Provisional LRLR", assessment.lrlr_status)
        self.assertIn("requires HRLR sweep", assessment.lrlr_status)

    def test_ohcl_output_includes_delivery_leg_and_day_filter(self) -> None:
        assessment = MmxmService.evaluate(self.db, "XAUUSD")

        self.assertIn("High -> Low", assessment.htf_delivery_leg)
        self.assertEqual("mid week", assessment.timing_probability)
        self.assertIn("No day-of-week timing conflict", assessment.timing_conflict)


if __name__ == "__main__":
    unittest.main()
