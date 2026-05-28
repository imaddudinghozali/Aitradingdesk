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
    MarketSnapshot,
    PoiZone,
)
from app.routers.irl_erl import _response
from app.schemas.market import MarketDataInput
from app.services.irl_erl_service import IrlErlService
from app.services.market_service import MarketService
from app.utils.timezone import NY_TZ


class IrlErlServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=engine)
        self.db = Session(bind=engine)

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

    def dol(
        self,
        primary: LiquidityLevel | None,
        engineered: LiquidityLevel | None,
        direction: str = "delivery_up",
        lifecycle: str = "Active",
    ) -> DolAssessment:
        assessment = DolAssessment(
            symbol="XAUUSD",
            lifecycle_status=lifecycle,
            delivery_direction=direction,
            primary_level_id=primary.id if primary else None,
            engineered_level_id=engineered.id if engineered else None,
            objective_quality="true_objective",
            status_reason="DOL fixture",
            old_objective_resolved=False,
            displacement_confirmed=True,
            timing_confirmed=True,
            prior_narrative_resolved=False,
            as_of_utc=datetime(2026, 5, 20, 15, tzinfo=UTC),
        )
        self.db.add(assessment)
        self.db.commit()
        self.db.refresh(assessment)
        return assessment

    def test_maps_weekly_and_daily_direction_with_macro_gap_disclosed(self) -> None:
        primary = self.level("PWH", "BSL", 2500)
        engineered = self.level("PWL", "SSL", 2350, "taken")
        self.level("PMH", "BSL", 2550)
        self.level("PYH", "BSL", 2700)
        self.level("PDH", "BSL", 2470)
        self.level("LONDON_HIGH", "BSL", 2460)
        self.dol(primary, engineered)

        result = IrlErlService.evaluate(self.db, "XAUUSD")
        response = _response(result)

        self.assertEqual("aligned", result.mapping.mapping_status)
        self.assertEqual("ERL -> IRL -> ERL", result.mapping.direction_flow)
        self.assertEqual("aligned", result.layers[0].status.value)
        self.assertEqual("aligned", result.layers[1].status.value)
        self.assertEqual("aligned", result.layers[2].status.value)
        self.assertTrue(
            any("Imbalance flow" in lim for lim in result.limitations),
            f"expected imbalance limitation note, got {result.limitations}",
        )
        self.assertEqual("Narrative Ready - wait for later execution confirmation layers", response.execution_status)
        current = IrlErlService.get_current(self.db, "XAUUSD")
        self.assertEqual(result.mapping.id, current.mapping.id)
        self.assertEqual("ERL -> IRL -> ERL", current.mapping.direction_flow)

    def test_missing_intraday_irl_returns_partial_not_false_alignment(self) -> None:
        primary = self.level("PWL", "SSL", 2350)
        engineered = self.level("PDH", "BSL", 2470, "taken")
        self.level("PDL", "SSL", 2400)
        self.dol(primary, engineered, direction="delivery_down")

        result = IrlErlService.evaluate(self.db, "XAUUSD")

        self.assertEqual("partial", result.mapping.mapping_status)
        self.assertEqual("partial", result.layers[2].status.value)
        self.assertIsNone(result.layers[2].irl)

    def test_unconfirmed_dol_keeps_mapping_waiting_and_no_trade(self) -> None:
        primary = self.level("PWH", "BSL", 2500)
        self.level("PDH", "BSL", 2470)
        self.level("LONDON_HIGH", "BSL", 2460)
        self.dol(primary, None, lifecycle="Shift Pending")

        result = IrlErlService.evaluate(self.db, "XAUUSD")
        response = _response(result)

        self.assertEqual("waiting_dol", result.mapping.mapping_status)
        self.assertEqual("No Trade - direction liquidity is not fully aligned", response.execution_status)

    def _seed_price(self, close: float) -> None:
        MarketService.create_snapshot(
            self.db,
            MarketDataInput(
                symbol="XAUUSD",
                timeframe="M15",
                timestamp_utc=datetime(2026, 5, 20, 15, tzinfo=UTC),
                open=close,
                high=close + 5,
                low=close - 5,
                close=close,
            ),
        )

    def _poi(
        self,
        poi_type: str,
        direction: str,
        price_low: int,
        price_high: int,
        timeframe: str = "H4",
        status: str = "pending",
    ) -> PoiZone:
        snapshot = (
            self.db.query(MarketSnapshot)
            .order_by(MarketSnapshot.timestamp_utc.desc())
            .first()
        )
        zone = PoiZone(
            symbol="XAUUSD",
            timeframe=timeframe,
            poi_type=poi_type,
            direction=direction,
            price_low=Decimal(price_low),
            price_high=Decimal(price_high),
            source_snapshot_id=snapshot.id if snapshot else None,
            status=status,
            status_reason="fixture imbalance",
            as_of_utc=datetime(2026, 5, 20, 15, tzinfo=UTC),
        )
        self.db.add(zone)
        self.db.commit()
        self.db.refresh(zone)
        return zone

    def test_imbalance_flow_substitutes_intraday_irl_when_session_irl_missing(self) -> None:
        primary = self.level("PWH", "BSL", 2500)
        engineered = self.level("PWL", "SSL", 2350, "taken")
        self.level("PDH", "BSL", 2470)
        self._seed_price(2425)
        self._poi("FVG", "bullish", 2410, 2418)
        self.dol(primary, engineered, direction="delivery_up")

        result = IrlErlService.evaluate(self.db, "XAUUSD")

        self.assertIsNotNone(result.imbalance)
        self.assertEqual("source_imbalance", result.imbalance_role)
        self.assertEqual("imbalance -> liquidity", result.mapping.direction_flow)
        daily_layer = result.layers[2]
        self.assertEqual("aligned", daily_layer.status.value)
        self.assertEqual(2418, int(daily_layer.imbalance.price_high))

    def test_imbalance_outside_dol_band_is_ignored(self) -> None:
        primary = self.level("PWH", "BSL", 2500)
        engineered = self.level("PWL", "SSL", 2350, "taken")
        self.level("PDH", "BSL", 2470)
        self._seed_price(2425)
        self._poi("FVG", "bullish", 2520, 2530)
        self.dol(primary, engineered, direction="delivery_up")

        result = IrlErlService.evaluate(self.db, "XAUUSD")

        self.assertIsNone(result.imbalance)
        self.assertNotEqual("imbalance -> liquidity", result.mapping.direction_flow)

    def test_invalidated_poi_is_not_used_as_imbalance(self) -> None:
        primary = self.level("PWH", "BSL", 2500)
        engineered = self.level("PWL", "SSL", 2350, "taken")
        self._seed_price(2425)
        self._poi("FVG", "bullish", 2410, 2418, status="invalidated")
        self.dol(primary, engineered, direction="delivery_up")

        result = IrlErlService.evaluate(self.db, "XAUUSD")

        self.assertIsNone(result.imbalance)

    def test_primary_side_conflict_is_reported(self) -> None:
        wrong_primary = self.level("PWL", "SSL", 2350)
        self.level("PDH", "BSL", 2470)
        self.level("PWH", "BSL", 2500)
        self.level("LONDON_HIGH", "BSL", 2460)
        self.dol(wrong_primary, None, direction="delivery_up")

        result = IrlErlService.evaluate(self.db, "XAUUSD")

        self.assertEqual("conflict", result.mapping.mapping_status)
        self.assertEqual(1, len(result.conflicts))
        self.assertIn("requires BSL", result.conflicts[0])


if __name__ == "__main__":
    unittest.main()
