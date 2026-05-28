import unittest
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base
from app.models import TradeJournalEntry  # noqa: F401
from app.schemas.journal import JournalCreateRequest, JournalUpdateRequest
from app.services.journal_service import JournalService


class JournalServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=engine)
        self.db = Session(bind=engine)

    def tearDown(self) -> None:
        self.db.close()

    def record(self, result: str, realized_rr: Decimal | None, note: str) -> TradeJournalEntry:
        return JournalService.create(
            self.db,
            JournalCreateRequest(
                setup_context="DOL aligned delivery with reviewed POI.",
                entry_reason=note,
                execution_confirmation="M15 confirmation reviewed manually.",
                invalidation="Invalid below reviewed liquidity.",
                risk="Fixed discretionary risk.",
                result=result,
                realized_rr=realized_rr,
            ),
        )

    def test_manual_setup_can_be_saved_and_reviewed(self) -> None:
        entry = self.record("pending", None, "Awaiting result.")

        updated = JournalService.update(
            self.db,
            entry,
            JournalUpdateRequest(
                result="win",
                realized_rr=Decimal("2.0"),
                narrative_review="Narrative remained aligned.",
            ),
        )

        self.assertEqual("win", updated.result)
        self.assertEqual(Decimal("2.0000"), updated.realized_rr)
        self.assertIn("aligned", updated.narrative_review)

    def test_performance_summary_uses_completed_journal_results_only(self) -> None:
        self.record("win", Decimal("2.0"), "win")
        self.record("loss", Decimal("-1.0"), "loss")
        self.record("no_trade", None, "guardrail review")
        self.record("pending", None, "unresolved")

        summary = JournalService.performance(self.db, "XAUUSD")

        self.assertEqual(4, summary.total_entries)
        self.assertEqual(2, summary.completed_trades)
        self.assertEqual(1, summary.no_trade_reviews)
        self.assertEqual(Decimal("0.5"), summary.winrate)
        self.assertEqual(Decimal("0.5"), summary.average_rr)
        self.assertEqual(Decimal("1.0"), summary.max_drawdown_rr)


if __name__ == "__main__":
    unittest.main()
