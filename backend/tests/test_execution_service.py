import unittest
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base
from app.models import (  # noqa: F401
    DolAssessment,
    ExecutionAssessment,
    IrlErlMapping,
    LiquidityLevel,
    MmxmAssessment,
    NarrativeLedger,
    QuarterReadinessAssessment,
    SsmtEvent,
)
from app.schemas.execution import ExecutionEvaluateRequest, PoiScanRequest
from app.schemas.market import MarketDataInput
from app.services.execution_service import ExecutionService, PoiService
from app.services.market_service import MarketService
from app.utils.timezone import NY_TZ


class ExecutionServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=engine)
        self.db = Session(bind=engine)
        self.target = self.level("PWH", "BSL", 2550)
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
        self.mapping = IrlErlMapping(
            symbol="XAUUSD",
            dol_assessment_id=self.dol.id,
            direction_flow="IRL -> ERL",
            mapping_status="aligned",
            status_reason="aligned execution fixture",
            as_of_utc=datetime(2026, 5, 20, 13, tzinfo=UTC),
        )
        self.db.add(self.mapping)
        self.db.commit()
        self.db.refresh(self.mapping)
        self.ledger = NarrativeLedger(
            symbol="XAUUSD",
            dol_assessment_id=self.dol.id,
            active_dol="PWH BSL at 2550",
            delivery_direction="delivery_up",
            target_level_id=self.target.id,
            target_liquidity="PWH BSL at 2550",
            invalidation_level_id=self.invalidation.id,
            invalidation_level="PWL SSL at 2400",
            invalidation_price=Decimal(2400),
            invalidation_condition="Two consecutive M15 closes below PWL invalidate delivery.",
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
        self.db.add(
            SsmtEvent(
                trade_asset="XAUUSD",
                confirmation_symbol="XAGUSD",
                timeframe="H4",
                ssmt_status="valid_bullish",
                direction="bullish",
                cic_detected=True,
                quarter_sequence_valid=True,
                magneto_status="clear",
                poi_touched=True,
                ssmt_dol_alignment="aligned",
                ssmt_noise_status="clear",
                xau_relative_state="relative_strength",
                confirmation_pair_state="confirm",
                liquidity_context="SSL swept before bullish divergence.",
                status_reason="Valid fixture.",
                as_of_utc=datetime(2026, 5, 20, 13, tzinfo=UTC),
            )
        )
        self.db.commit()
        self.db.add(
            MmxmAssessment(
                symbol="XAUUSD",
                dol_assessment_id=self.dol.id,
                narrative_ledger_id=self.ledger.id,
                active_model="MMBM",
                model_status="active",
                candle_delivery="OHLC",
                htf_delivery_leg="Bullish delivery fixture.",
                timing_probability="mid week",
                timing_conflict="No day-of-week timing conflict identified for current bullish delivery.",
                mmxm_phase="expansion",
                quadrant="Q3",
                current_price=Decimal(2480),
                terminus="PWH BSL at 2550",
                hrlr_status="Context available.",
                lrlr_status="Waiting.",
                opr_status="Waiting.",
                judas_status="potential",
                judas_reason="Session context reviewed.",
                nine_am_context="No conflict.",
                status_reason="Valid model context fixture.",
                as_of_utc=datetime(2026, 5, 20, 14, tzinfo=UTC),
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

    def bullish_confirmation_candles(self) -> None:
        self.candle(13, 0, 2420, 2422, 2408, 2410)
        self.candle(13, 15, 2412, 2450, 2411, 2448)
        self.candle(13, 30, 2450, 2460, 2430, 2455)
        self.candle(13, 45, 2416, 2442, 2415, 2440)
        latest = self.candle(14, 0, 2440, 2485, 2438, 2480)
        self.db.add(
            QuarterReadinessAssessment(
                symbol="XAUUSD",
                market_snapshot_id=latest.id,
                dol_assessment_id=self.dol.id,
                irl_erl_mapping_id=self.mapping.id,
                daily_quarter="Q3",
                micro_quarter_90m="Q3.1",
                session="NY AM",
                quarter_status="Expansion Active",
                quarter_intent="Buyside delivery toward active DOL.",
                manipulation_status="Validated fixture.",
                expansion_status="Active.",
                quarter_execution_allowed=True,
                gate_decision="Waiting Confirmation",
                status_reason="Execution fixture is ready.",
                next_valid_window="Current Q3.",
                as_of_utc=latest.timestamp_utc,
            )
        )
        self.db.commit()

    def test_scan_detects_reacted_fvg_ob_and_mitigation(self) -> None:
        self.bullish_confirmation_candles()

        zones = PoiService.scan(self.db, PoiScanRequest())

        typed = {zone.poi_type: zone for zone in zones}
        self.assertEqual("validated_retracement", typed["FVG"].status)
        self.assertEqual("validated_retracement", typed["OB"].status)
        self.assertTrue(typed["MITIGATION"].reaction_confirmed)

    def test_validated_poi_mss_cisd_and_rr_produce_setup_context_only(self) -> None:
        self.bullish_confirmation_candles()

        assessment = ExecutionService.evaluate(
            self.db,
            ExecutionEvaluateRequest(minimum_rr=Decimal("0.80")),
        )

        self.assertEqual("Valid Setup", assessment.execution_status)
        self.assertTrue(assessment.mss_confirmed)
        self.assertTrue(assessment.cisd_confirmed)
        self.assertEqual("sufficient", assessment.risk_status)
        self.assertIn("no order is emitted", assessment.no_trade_reason)
        self.assertIn("MSS and CISD confirmed", assessment.trigger_confirmation)

    def test_rr_policy_blocks_an_otherwise_confirmed_setup(self) -> None:
        self.bullish_confirmation_candles()

        assessment = ExecutionService.evaluate(
            self.db,
            ExecutionEvaluateRequest(minimum_rr=Decimal("1.00")),
        )

        self.assertEqual("No Trade", assessment.execution_status)
        self.assertEqual("below_minimum", assessment.risk_status)
        self.assertIn("minimum RR", assessment.no_trade_reason)

    def test_each_execution_evaluation_keeps_an_immutable_history_row(self) -> None:
        self.bullish_confirmation_candles()

        first = ExecutionService.evaluate(
            self.db,
            ExecutionEvaluateRequest(minimum_rr=Decimal("0.80")),
        )
        second = ExecutionService.evaluate(
            self.db,
            ExecutionEvaluateRequest(minimum_rr=Decimal("1.00")),
        )

        self.assertNotEqual(first.id, second.id)
        self.assertEqual(2, self.db.query(ExecutionAssessment).count())
        self.assertEqual(second.id, ExecutionService.get_current(self.db, "XAUUSD").id)

    def test_day_of_week_timing_conflict_blocks_confirmed_setup(self) -> None:
        self.bullish_confirmation_candles()
        mmxm = self.db.query(MmxmAssessment).filter(MmxmAssessment.symbol == "XAUUSD").one()
        mmxm.timing_conflict = "Timing conflict - late-week buyside formation lacks an external HTF target."
        self.db.commit()

        assessment = ExecutionService.evaluate(
            self.db,
            ExecutionEvaluateRequest(minimum_rr=Decimal("0.80")),
        )

        self.assertEqual("No Trade", assessment.execution_status)
        self.assertIn("Timing conflict", assessment.no_trade_reason)

    def test_later_close_through_zone_invalidates_poi_and_creates_inversion(self) -> None:
        self.bullish_confirmation_candles()
        PoiService.scan(self.db, PoiScanRequest())
        self.candle(14, 15, 2430, 2431, 2398, 2405)

        zones = PoiService.scan(self.db, PoiScanRequest())

        fvg = next(zone for zone in zones if zone.poi_type == "FVG" and zone.direction == "bullish")
        inversion = next(zone for zone in zones if zone.poi_type == "IFVG" and zone.direction == "bearish")
        self.assertEqual("invalidated", fvg.status)
        self.assertEqual("active", inversion.status)


if __name__ == "__main__":
    unittest.main()
