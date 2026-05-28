import unittest
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base
from app.models import DolAssessment, IrlErlMapping, LiquidityLevel, SsmtEvent, SweepEvent  # noqa: F401
from app.schemas.market import MarketDataInput
from app.schemas.ssmt import SsmtEvaluateRequest
from app.services.market_service import MarketService
from app.services.ssmt_service import SsmtService
from app.utils.timezone import NY_TZ


class SsmtServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=engine)
        self.db = Session(bind=engine)
        self.swept_high = self.level("PDH", "BSL", 4850, "taken")
        target = self.level("PDL", "SSL", 4700)
        self.dol = DolAssessment(
            symbol="XAUUSD",
            lifecycle_status="Active",
            delivery_direction="delivery_down",
            primary_level_id=target.id,
            engineered_level_id=self.swept_high.id,
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
        self.db.add(
            IrlErlMapping(
                symbol="XAUUSD",
                dol_assessment_id=self.dol.id,
                direction_flow="ERL -> IRL",
                mapping_status="aligned",
                status_reason="aligned bearish",
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
            as_of_utc=datetime(2026, 5, 20, 14, tzinfo=UTC),
            status_reason="fixture",
        )
        self.db.add(level)
        self.db.commit()
        self.db.refresh(level)
        return level

    def candle(
        self,
        symbol: str,
        timestamp: datetime,
        high: Decimal | int | float,
        low: Decimal | int | float,
        close: Decimal | int | float | None = None,
        timeframe: str = "H4",
    ):
        close_price = close if close is not None else (Decimal(str(high)) + Decimal(str(low))) / 2
        return MarketService.create_snapshot(
            self.db,
            MarketDataInput(
                symbol=symbol,
                timeframe=timeframe,
                timestamp_utc=timestamp,
                open=close_price,
                high=high,
                low=low,
                close=close_price,
            ),
        )

    def bearish_cic(self, second_time: datetime = datetime(2026, 5, 20, 14, tzinfo=UTC)) -> None:
        first_xau = self.candle("XAUUSD", datetime(2026, 5, 20, 8, tzinfo=UTC), 4850, 4800, 4830)
        self.candle("XAGUSD", datetime(2026, 5, 20, 8, tzinfo=UTC), 32.50, 31.80, 32.20)
        self.candle("XAUUSD", second_time, 4830, 4780, 4810)
        self.candle("XAGUSD", second_time, 32.80, 31.90, 32.60)
        event = SweepEvent(
            liquidity_level_id=self.swept_high.id,
            interaction_snapshot_id=first_xau.id,
            symbol="XAUUSD",
            level_type="PDH",
            liquidity_side="BSL",
            level_price=self.swept_high.price,
            session=first_xau.session,
            session_anchor=first_xau.session_anchor,
            daily_quarter=first_xau.daily_quarter,
            micro_quarter_90m=first_xau.micro_quarter_90m,
            sweep_status="Valid Sweep",
            confirmation_status="confirmed_reversal_displacement",
            displacement_detected=True,
            relevant_timing=True,
            narrative_alignment="aligned",
            reason="HTF BSL swept before SSMT",
            detected_at_utc=first_xau.timestamp_utc,
        )
        self.db.add(event)
        self.db.commit()

    def test_candidate_waits_when_poi_is_not_confirmed(self) -> None:
        self.bearish_cic()

        event = SsmtService.evaluate(self.db, SsmtEvaluateRequest())

        self.assertEqual("waiting", event.ssmt_status)
        self.assertTrue(event.cic_detected)
        self.assertTrue(event.quarter_sequence_valid)
        self.assertEqual("waiting_poi", event.ssmt_noise_status)

    def test_complete_bearish_sequence_is_valid_for_xau_only(self) -> None:
        self.bearish_cic()

        event = SsmtService.evaluate(
            self.db,
            SsmtEvaluateRequest(poi_touched=True, poi_reference="H4 bearish FVG"),
        )

        self.assertEqual("valid_bearish", event.ssmt_status)
        self.assertEqual("relative_weakness", event.xau_relative_state)
        self.assertEqual("XAUUSD", event.trade_asset)
        self.assertEqual("XAGUSD", event.confirmation_symbol)
        self.assertIn("XAU Lower High", event.confirmation_pair_state)
        self.assertEqual("liquidity -> liquidity", event.algorithm_state)
        self.assertEqual("supported", event.algorithm_context_status)
        self.assertIn("Trade asset remains XAUUSD", event.status_reason)

    def test_unsupported_market_algorithm_context_is_noise(self) -> None:
        self.bearish_cic()
        mapping = self.db.query(IrlErlMapping).first()
        mapping.direction_flow = "no man's land"
        self.db.commit()

        event = SsmtService.evaluate(
            self.db,
            SsmtEvaluateRequest(poi_touched=True, poi_reference="H4 bearish FVG"),
        )

        self.assertEqual("noise", event.ssmt_status)
        self.assertEqual("algorithm_context_not_supported", event.ssmt_noise_status)
        self.assertEqual("not_supported", event.algorithm_context_status)
        self.assertIn("algorithm context", event.status_reason)

    def test_quarter_gap_is_rejected_as_noise(self) -> None:
        self.bearish_cic(datetime(2026, 5, 20, 20, tzinfo=UTC))

        event = SsmtService.evaluate(
            self.db,
            SsmtEvaluateRequest(poi_touched=True, poi_reference="H4 FVG"),
        )

        self.assertEqual("noise", event.ssmt_status)
        self.assertFalse(event.quarter_sequence_valid)
        self.assertEqual("invalid_quarter_sequence", event.ssmt_noise_status)

    def bearish_micro_cic(self) -> None:
        # Two sequential 90-minute Daye micro-quarters in Q3 (NY 06:00 = 10:00 UTC EDT):
        #   Q3.1 start 06:00 NY (10:00 UTC), Q3.2 start 07:30 NY (11:30 UTC).
        first_xau = self.candle(
            "XAUUSD", datetime(2026, 5, 20, 10, 5, tzinfo=UTC), 4850, 4800, 4830, timeframe="M5"
        )
        self.candle(
            "XAGUSD", datetime(2026, 5, 20, 10, 5, tzinfo=UTC), 32.50, 31.80, 32.20, timeframe="M5"
        )
        self.candle(
            "XAUUSD", datetime(2026, 5, 20, 11, 35, tzinfo=UTC), 4830, 4780, 4810, timeframe="M5"
        )
        self.candle(
            "XAGUSD", datetime(2026, 5, 20, 11, 35, tzinfo=UTC), 32.80, 31.90, 32.60, timeframe="M5"
        )
        event = SweepEvent(
            liquidity_level_id=self.swept_high.id,
            interaction_snapshot_id=first_xau.id,
            symbol="XAUUSD",
            level_type="PDH",
            liquidity_side="BSL",
            level_price=self.swept_high.price,
            session=first_xau.session,
            session_anchor=first_xau.session_anchor,
            daily_quarter=first_xau.daily_quarter,
            micro_quarter_90m=first_xau.micro_quarter_90m,
            sweep_status="Valid Sweep",
            confirmation_status="confirmed_reversal_displacement",
            displacement_detected=True,
            relevant_timing=True,
            narrative_alignment="aligned",
            reason="HTF BSL swept before micro SSMT",
            detected_at_utc=first_xau.timestamp_utc,
        )
        self.db.add(event)
        self.db.commit()

    def test_90m_micro_cycle_validates_bearish_on_m5(self) -> None:
        self.bearish_micro_cic()

        event = SsmtService.evaluate(
            self.db,
            SsmtEvaluateRequest(
                cycle="90m",
                timeframe="M5",
                poi_touched=True,
                poi_reference="M5 bearish FVG",
            ),
        )

        self.assertEqual("valid_bearish", event.ssmt_status)
        self.assertEqual("M5", event.timeframe)
        self.assertEqual("Q3.1", event.first_quarter)
        self.assertEqual("Q3.2", event.second_quarter)
        self.assertTrue(event.quarter_sequence_valid)
        self.assertIn("XAU Lower High", event.confirmation_pair_state)

    def test_90m_cycle_rejects_h4_timeframe(self) -> None:
        with self.assertRaises(ValueError):
            SsmtEvaluateRequest(cycle="90m", timeframe="H4")

    def test_magneto_effect_invalidates_prior_valid_event(self) -> None:
        self.bearish_cic()
        valid = SsmtService.evaluate(
            self.db,
            SsmtEvaluateRequest(poi_touched=True, poi_reference="H4 bearish FVG"),
        )
        self.candle("XAUUSD", datetime(2026, 5, 20, 20, tzinfo=UTC), 4870, 4820, 4860)

        invalidated = SsmtService.evaluate(
            self.db,
            SsmtEvaluateRequest(
                poi_touched=True,
                poi_reference="H4 bearish FVG",
                as_of_utc=datetime(2026, 5, 20, 20, tzinfo=UTC),
            ),
        )

        self.assertEqual(valid.id, invalidated.id)
        self.assertEqual("magneto_invalidated", invalidated.ssmt_status)
        self.assertEqual("triggered", invalidated.magneto_status)
        self.assertIn("Magneto Effect", invalidated.status_reason)


if __name__ == "__main__":
    unittest.main()
