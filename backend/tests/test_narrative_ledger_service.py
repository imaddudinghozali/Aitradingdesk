import unittest
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base
from app.models import (  # noqa: F401
    DolAssessment,
    IrlErlMapping,
    LiquidityLevel,
    NarrativeLedger,
    QuarterReadinessAssessment,
    SsmtEvent,
    SweepEvent,
)
from app.schemas.market import MarketDataInput
from app.schemas.narrative import NarrativeGenerateRequest
from app.services.market_service import MarketService
from app.services.narrative_ledger_service import NarrativeLedgerService
from app.services.narrative_service import NarrativeService
from app.utils.timezone import NY_TZ


class NarrativeLedgerServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=engine)
        self.db = Session(bind=engine)
        self.market(datetime(2026, 5, 20, 13, tzinfo=UTC), 2450, 2455, 2445, 2450)
        self.target = self.level("PWH", "BSL", 2500)
        self.invalidation = self.level("PWL", "SSL", 2400, "taken")
        self.dol = DolAssessment(
            symbol="XAUUSD",
            lifecycle_status="Active",
            delivery_direction="delivery_up",
            primary_level_id=self.target.id,
            engineered_level_id=self.invalidation.id,
            objective_quality="true_objective",
            status_reason="active bullish DOL",
            old_objective_resolved=False,
            displacement_confirmed=True,
            timing_confirmed=True,
            prior_narrative_resolved=False,
            as_of_utc=datetime(2026, 5, 20, 13, tzinfo=UTC),
        )
        self.db.add(self.dol)
        self.db.commit()
        self.db.refresh(self.dol)
        self.db.add(
            IrlErlMapping(
                symbol="XAUUSD",
                dol_assessment_id=self.dol.id,
                direction_flow="IRL -> ERL",
                mapping_status="aligned",
                status_reason="aligned bullish mapping",
                as_of_utc=datetime(2026, 5, 20, 13, tzinfo=UTC),
            )
        )
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

    def market(self, timestamp: datetime, open_price: int, high: int, low: int, close: int):
        return MarketService.create_snapshot(
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

    def generate(self):
        return NarrativeService.generate(self.db, NarrativeGenerateRequest())

    def test_complete_narrative_registers_structured_invalidation_ledger(self) -> None:
        snapshot = self.generate()
        ledger = NarrativeLedgerService.get_current(self.db, "XAUUSD")

        self.assertIsNotNone(ledger)
        self.assertEqual(ledger.id, snapshot.narrative_ledger_id)
        self.assertEqual("active", ledger.continuation_status)
        self.assertIn("Two consecutive M15 closes below", ledger.invalidation_condition)
        self.assertIn("Reset DOL identification", ledger.next_decision_if_invalidated)
        self.assertIn("Narrative Status: active", snapshot.rendered_snapshot)

    def test_incomplete_narrative_does_not_register_active_ledger(self) -> None:
        self.dol.engineered_level_id = None
        self.invalidation.status = "invalidated"
        self.db.commit()

        snapshot = self.generate()

        self.assertIsNone(snapshot.narrative_ledger_id)
        self.assertTrue(snapshot.reset_required)
        self.assertIn("Narrative incomplete", snapshot.no_trade_reason)
        self.assertIsNone(NarrativeLedgerService.get_current(self.db, "XAUUSD"))

    def test_missing_engineered_link_uses_protective_liquidity_as_invalidation(self) -> None:
        self.dol.engineered_level_id = None
        self.invalidation.status = "active"
        self.db.commit()

        snapshot = self.generate()
        ledger = NarrativeLedgerService.get_current(self.db, "XAUUSD")

        self.assertIsNotNone(ledger)
        self.assertEqual(ledger.id, snapshot.narrative_ledger_id)
        self.assertEqual(self.invalidation.id, ledger.invalidation_level_id)
        self.assertIn("Two consecutive M15 closes below", ledger.invalidation_condition)

    def test_wick_through_invalidation_marks_weakening_without_reset(self) -> None:
        self.generate()
        self.market(datetime(2026, 5, 20, 13, 15, tzinfo=UTC), 2420, 2430, 2390, 2410)

        ledger = NarrativeLedgerService.evaluate(self.db, "XAUUSD")

        self.assertEqual("weakening", ledger.continuation_status)
        self.assertEqual("potential_sweep", ledger.breach_status)
        self.assertFalse(ledger.reset_required)
        self.assertEqual("Active", self.dol.lifecycle_status)

    def test_close_and_hold_failure_resets_dol_to_shift_pending(self) -> None:
        self.generate()
        self.market(datetime(2026, 5, 20, 13, 15, tzinfo=UTC), 2398, 2399, 2385, 2390)
        self.market(datetime(2026, 5, 20, 13, 30, tzinfo=UTC), 2390, 2392, 2375, 2380)

        ledger = NarrativeLedgerService.evaluate(self.db, "XAUUSD")
        self.db.refresh(self.dol)

        self.assertEqual("failed", ledger.continuation_status)
        self.assertEqual("close_and_hold_breached", ledger.breach_status)
        self.assertTrue(ledger.reset_required)
        self.assertEqual("Shift Pending", self.dol.lifecycle_status)
        self.assertIn("fresh DOL identification", self.dol.status_reason)

    def test_new_snapshot_reports_failure_detected_during_generation(self) -> None:
        self.generate()
        self.market(datetime(2026, 5, 20, 13, 15, tzinfo=UTC), 2398, 2399, 2385, 2390)
        self.market(datetime(2026, 5, 20, 13, 30, tzinfo=UTC), 2390, 2392, 2375, 2380)

        snapshot = self.generate()

        self.assertEqual("failed", snapshot.continuation_status)
        self.assertTrue(snapshot.reset_required)
        self.assertEqual("Shift Pending", snapshot.dol_status)
        self.assertIn("Narrative status is failed", snapshot.no_trade_reason)

    def test_ssmt_direction_conflict_fails_active_narrative(self) -> None:
        self.generate()
        self.db.add(
            SsmtEvent(
                trade_asset="XAUUSD",
                confirmation_symbol="XAGUSD",
                timeframe="H4",
                ssmt_status="noise",
                direction="bearish",
                cic_detected=True,
                quarter_sequence_valid=True,
                magneto_status="clear",
                poi_touched=True,
                ssmt_dol_alignment="conflict",
                ssmt_noise_status="dol_conflict",
                xau_relative_state="relative_weakness",
                confirmation_pair_state="Opposing SSMT fixture.",
                liquidity_context="Liquidity was swept.",
                status_reason="SSMT noise: divergence direction is not supported by active DOL.",
                as_of_utc=datetime(2026, 5, 20, 13, tzinfo=UTC),
            )
        )
        self.db.commit()

        snapshot = self.generate()
        ledger = NarrativeLedgerService.get_current(self.db, "XAUUSD")

        self.assertEqual("failed", ledger.continuation_status)
        self.assertTrue(ledger.reset_required)
        self.assertEqual("Shift Pending", snapshot.dol_status)
        self.assertIn("SSMT direction conflicts", ledger.status_reason)

    def test_closed_expansion_without_target_fails_narrative(self) -> None:
        self.generate()
        ledger = NarrativeLedgerService.get_current(self.db, "XAUUSD")
        quarter = self.db.query(QuarterReadinessAssessment).first()
        interaction = MarketService.get_latest(self.db, "XAUUSD", "M15")
        event = SweepEvent(
            liquidity_level_id=self.dol.engineered_level_id,
            interaction_snapshot_id=interaction.id,
            symbol="XAUUSD",
            level_type="PWL",
            liquidity_side="SSL",
            level_price=Decimal(2400),
            session=interaction.session,
            session_anchor=interaction.session_anchor,
            daily_quarter=interaction.daily_quarter,
            micro_quarter_90m=interaction.micro_quarter_90m,
            sweep_status="Valid Sweep",
            confirmation_status="confirmed_reversal_displacement",
            displacement_detected=True,
            relevant_timing=True,
            narrative_alignment="aligned",
            reason="expansion began but target remained untaken",
            detected_at_utc=interaction.timestamp_utc,
        )
        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)
        self.dol.source_sweep_event_id = event.id
        quarter.source_sweep_event_id = event.id
        quarter.quarter_status = "Closed / Late Entry"
        self.db.commit()

        failed = NarrativeLedgerService.apply_context_failure(
            self.db, ledger, self.dol, quarter, None
        )

        self.assertEqual("failed", failed.continuation_status)
        self.assertTrue(failed.reset_required)
        self.assertIn("objective was reached", failed.status_reason)


if __name__ == "__main__":
    unittest.main()
