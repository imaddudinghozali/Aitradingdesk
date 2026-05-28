import unittest
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base
from app.models import (  # noqa: F401
    BacktestObservation,
    BacktestRun,
    DolAssessment,
    ExecutionAssessment,
    IrlErlMapping,
    LiquidityLevel,
    NarrativeLedger,
    NarrativeSnapshot,
    QuarterReadinessAssessment,
    SsmtEvent,
    SweepEvent,
)
from app.schemas.backtest import BacktestRunRequest
from app.schemas.market import MarketDataInput
from app.services.backtest_service import BacktestService
from app.services.market_service import MarketService
from app.utils.timezone import NY_TZ


class BacktestServiceTest(unittest.TestCase):
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
            status_reason="fixture",
            old_objective_resolved=False,
            displacement_confirmed=True,
            timing_confirmed=True,
            prior_narrative_resolved=False,
            as_of_utc=datetime(2026, 5, 20, 13, tzinfo=UTC),
        )
        self.db.add(self.dol)
        self.db.commit()
        self.db.refresh(self.dol)
        self.mapping = IrlErlMapping(
            symbol="XAUUSD",
            dol_assessment_id=self.dol.id,
            direction_flow="IRL -> ERL",
            mapping_status="aligned",
            status_reason="fixture",
            as_of_utc=datetime(2026, 5, 20, 13, tzinfo=UTC),
        )
        self.db.add(self.mapping)
        self.db.commit()
        self.db.refresh(self.mapping)
        decision_market = self.candle(13, 0, 2450, 2460, 2445, 2450)
        self.quarter = QuarterReadinessAssessment(
            symbol="XAUUSD",
            market_snapshot_id=decision_market.id,
            dol_assessment_id=self.dol.id,
            irl_erl_mapping_id=self.mapping.id,
            daily_quarter="Q3",
            micro_quarter_90m="Q3.1",
            session="NY AM",
            quarter_status="Expansion Active",
            quarter_intent="fixture",
            manipulation_status="fixture",
            expansion_status="Active",
            quarter_execution_allowed=True,
            gate_decision="Waiting Confirmation",
            status_reason="fixture",
            next_valid_window="fixture",
            as_of_utc=decision_market.timestamp_utc,
        )
        self.db.add(self.quarter)
        self.db.commit()
        self.db.refresh(self.quarter)
        self.ledger = NarrativeLedger(
            symbol="XAUUSD",
            dol_assessment_id=self.dol.id,
            quarter_readiness_id=self.quarter.id,
            active_dol="PWH BSL at 2500",
            delivery_direction="delivery_up",
            target_level_id=self.target.id,
            target_liquidity="PWH BSL at 2500",
            invalidation_level_id=self.invalidation.id,
            invalidation_level="PWL SSL at 2400",
            invalidation_price=Decimal(2400),
            invalidation_condition="Two closes below PWL.",
            next_decision_if_invalidated="Reset DOL.",
            reset_required=False,
            continuation_status="active",
            breach_status="clear",
            status_reason="fixture",
            activated_at_utc=decision_market.timestamp_utc,
            as_of_utc=decision_market.timestamp_utc,
        )
        self.db.add(self.ledger)
        self.db.commit()
        self.db.refresh(self.ledger)

    def tearDown(self) -> None:
        self.db.close()

    def level(self, level_type: str, side: str, price: int, status: str = "active") -> LiquidityLevel:
        row = LiquidityLevel(
            symbol="XAUUSD",
            level_type=level_type,
            liquidity_side=side,
            price=Decimal(price),
            status=status,
            source_timeframe="D",
            source_period_start_ny=datetime(2026, 5, 19, tzinfo=NY_TZ),
            source_period_end_ny=datetime(2026, 5, 20, 5, tzinfo=NY_TZ),
            as_of_utc=datetime(2026, 5, 20, 13, tzinfo=UTC),
            status_reason="fixture",
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def candle(self, hour: int, minute: int, open_price: int, high: int, low: int, close: int):
        return MarketService.create_snapshot(
            self.db,
            MarketDataInput(
                symbol="XAUUSD",
                timeframe="M15",
                timestamp_utc=datetime(2026, 5, 20, hour, minute, tzinfo=UTC),
                open=open_price,
                high=high,
                low=low,
                close=close,
            ),
        )

    def execution(self, at: datetime, status: str) -> ExecutionAssessment:
        row = ExecutionAssessment(
            symbol="XAUUSD",
            timeframe="M15",
            dol_assessment_id=self.dol.id,
            narrative_ledger_id=self.ledger.id,
            quarter_readiness_id=self.quarter.id,
            delivery_direction="delivery_up",
            setup_context="fixture",
            poi_confirmation="validated",
            mss_confirmed=status == "Valid Setup",
            cisd_confirmed=status == "Valid Setup",
            trigger_confirmation="fixture",
            entry_reference=Decimal(2450),
            invalidation_price=Decimal(2400),
            target_price=Decimal(2500),
            risk_points=Decimal(50),
            reward_points=Decimal(50),
            rr_ratio=Decimal(2) if status == "Valid Setup" else Decimal(1),
            minimum_rr=Decimal(1),
            risk_status="sufficient",
            execution_status=status,
            no_trade_reason="fixture",
            validation_required="fixture",
            as_of_utc=at,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def sweep(self, market_id: int, at: datetime) -> SweepEvent:
        row = SweepEvent(
            liquidity_level_id=self.invalidation.id,
            interaction_snapshot_id=market_id,
            symbol="XAUUSD",
            level_type="PWL",
            liquidity_side="SSL",
            level_price=Decimal(2400),
            session="NY AM",
            session_anchor="09 NY",
            daily_quarter="Q3",
            micro_quarter_90m="Q3.1",
            sweep_status="Valid Sweep",
            confirmation_status="confirmed_reversal_displacement",
            displacement_detected=True,
            relevant_timing=True,
            narrative_alignment="aligned",
            reason="fixture",
            detected_at_utc=at,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def narrative(
        self,
        at: datetime,
        status: str,
        execution: ExecutionAssessment,
        session: str,
        quarter: str,
        sweep_id: int | None = None,
    ) -> NarrativeSnapshot:
        row = NarrativeSnapshot(
            symbol="XAUUSD",
            provider="rules",
            model=None,
            ai_enhanced=False,
            dol_assessment_id=self.dol.id,
            irl_erl_mapping_id=self.mapping.id,
            quarter_readiness_id=self.quarter.id,
            narrative_ledger_id=self.ledger.id,
            execution_assessment_id=execution.id,
            source_sweep_event_id=sweep_id,
            session=session,
            session_anchor="09 NY",
            daily_quarter=quarter,
            quarter_status="Expansion Active",
            next_valid_window="Current.",
            htf_dol="PWH BSL at 2500",
            dol_status="Active",
            direction_liquidity="IRL -> ERL",
            active_model="MMBM",
            macro_state="continuation",
            quarterly_state="expansion",
            session_state="expansion",
            intraday_state="expansion",
            conflict_resolution="Aligned.",
            news_catalyst_status="None.",
            delivery_tempo="aggressive delivery",
            delivery_state="fixture",
            session_narrative="fixture",
            judas_manipulation_status="Valid Judas fixture.",
            opr_status="Active bounce: OPR fixture.",
            mmxm_timing_context="mid week: No timing conflict.",
            ssmt_status="VALID BULLISH fixture.",
            expansion_quality="healthy expansion",
            setup_context="fixture",
            trigger_confirmation="fixture",
            risk_context="fixture",
            execution_status=status,
            no_trade_reason="fixture",
            validation_required="fixture",
            continuation_status="active",
            reset_required=False,
            next_decision_if_invalidated="Reset.",
            invalidation="PWL SSL at 2400",
            target_liquidity="PWH BSL at 2500",
            rendered_snapshot="fixture",
            as_of_utc=at,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def test_walk_forward_scores_stored_decisions_and_ignores_prior_candles(self) -> None:
        self.candle(12, 45, 2420, 2430, 2380, 2410)
        first_at = datetime(2026, 5, 20, 13, tzinfo=UTC)
        first = self.execution(first_at, "Valid Setup")
        first_sweep = self.sweep(self.quarter.market_snapshot_id, first_at)
        self.narrative(first_at, "Valid Setup", first, "NY AM", "Q3", first_sweep.id)
        self.candle(13, 15, 2480, 2505, 2470, 2500)

        second_market = self.candle(14, 0, 2450, 2460, 2440, 2450)
        second_at = second_market.timestamp_utc
        second = self.execution(second_at, "Valid Setup")
        second_sweep = self.sweep(second_market.id, second_at)
        self.narrative(second_at, "Valid Setup", second, "NY PM", "Q4", second_sweep.id)
        self.candle(14, 15, 2420, 2430, 2395, 2400)

        third_at = datetime(2026, 5, 20, 15, tzinfo=UTC)
        self.candle(15, 0, 2450, 2460, 2440, 2450)
        third = self.execution(third_at, "No Trade")
        self.narrative(third_at, "No Trade", third, "NY PM", "Q4")
        self.candle(15, 15, 2420, 2430, 2390, 2395)
        self.db.add_all(
            [
                SsmtEvent(
                    trade_asset="XAUUSD",
                    confirmation_symbol="XAGUSD",
                    timeframe="H4",
                    ssmt_status="valid_bullish",
                    ssmt_dol_alignment="aligned",
                    ssmt_noise_status="clear",
                    xau_relative_state="relative_strength",
                    confirmation_pair_state="confirm",
                    liquidity_context="fixture",
                    status_reason="fixture",
                    as_of_utc=first_at,
                ),
                SsmtEvent(
                    trade_asset="XAUUSD",
                    confirmation_symbol="XAGUSD",
                    timeframe="H1",
                    ssmt_status="magneto_invalidated",
                    ssmt_dol_alignment="aligned",
                    ssmt_noise_status="magneto_invalidated",
                    xau_relative_state="relative_strength",
                    confirmation_pair_state="invalidated",
                    liquidity_context="fixture",
                    status_reason="fixture",
                    as_of_utc=third_at,
                ),
            ]
        )
        self.db.commit()

        run = BacktestService.run(self.db, BacktestRunRequest(horizon_bars=2))
        observations = BacktestService.observations(self.db, run.id)
        breakdown = BacktestService.breakdown(self.db, run.id)

        self.assertEqual(["win", "loss", "protected_no_trade"], [row.outcome for row in observations])
        self.assertEqual(3, run.narrative_samples)
        self.assertEqual(2, run.valid_setup_samples)
        self.assertEqual(Decimal("0.5000"), run.winrate)
        self.assertEqual(Decimal("0.5000"), run.average_rr)
        self.assertEqual(Decimal("1.0000"), run.max_drawdown_rr)
        self.assertEqual(Decimal("1.0000"), run.no_trade_accuracy)
        self.assertEqual(Decimal("0.5000"), run.false_ssmt_rate)
        self.assertEqual(Decimal("0.5000"), run.false_sweep_rate)
        self.assertIn("NY AM", run.best_session)
        self.assertIn("NY PM", run.worst_session)
        concepts = {bucket.concept for bucket in breakdown}
        self.assertEqual(
            {"DOL", "IRL/ERL", "SSMT", "Judas", "OPR", "MMXM", "Session", "Quarter"},
            concepts,
        )

    def test_run_requires_recorded_point_in_time_narratives(self) -> None:
        with self.assertRaisesRegex(ValueError, "No stored narrative snapshots"):
            BacktestService.run(self.db, BacktestRunRequest())


if __name__ == "__main__":
    unittest.main()
