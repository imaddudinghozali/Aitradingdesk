import unittest
from datetime import UTC, datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base
from app.models import AnalysisRun, NarrativeSnapshot  # noqa: F401
from app.schemas.analysis import AnalysisRunRequest
from app.schemas.market import MarketDataInput
from app.services.analysis_pipeline_service import AnalysisPipelineService
from app.services.market_service import MarketService


class AnalysisPipelineServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=engine)
        self.db = Session(bind=engine)

    def tearDown(self) -> None:
        self.db.close()

    def candle(self) -> None:
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

    def test_requires_execution_timeframe_market_input(self) -> None:
        with self.assertRaisesRegex(ValueError, "No M15 market snapshots"):
            AnalysisPipelineService.run(self.db, AnalysisRunRequest())

    def test_incomplete_evidence_records_conservative_no_trade_run(self) -> None:
        self.candle()

        run = AnalysisPipelineService.run(self.db, AnalysisRunRequest())
        response = AnalysisPipelineService.response(run)

        self.assertEqual("blocked", response.run_status)
        self.assertEqual("No Trade", response.decision_status)
        self.assertIsNotNone(response.narrative_snapshot_id)
        self.assertIsNone(response.execution_assessment_id)
        self.assertIn("DOL status is Shift Pending", response.no_trade_reason)
        self.assertIn(
            "Narrative ledger lacks a defined target and invalidation boundary.",
            response.missing_inputs,
        )
        stages = {step.stage: step.status for step in response.steps}
        self.assertEqual("waiting", stages["dol"])
        self.assertEqual("skipped", stages["execution_confirmation"])
        self.assertEqual("completed", stages["narrative_output"])

    def test_latest_returns_most_recent_persisted_run(self) -> None:
        self.candle()
        first = AnalysisPipelineService.run(self.db, AnalysisRunRequest())
        second = AnalysisPipelineService.run(self.db, AnalysisRunRequest())

        latest = AnalysisPipelineService.get_latest(self.db, "XAUUSD")

        self.assertEqual(second.id, latest.id)
        self.assertNotEqual(first.id, latest.id)


if __name__ == "__main__":
    unittest.main()
