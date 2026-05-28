import unittest
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base
from app.models import MarketSnapshot, ReplayDecisionRow, ReplayRun  # noqa: F401
from app.schemas.market import MarketDataInput
from app.services.market_service import MarketService
from app.services.replay_policies.base import (
    ReplayContext,
    ReplayDecision,
    ReplayPolicy,
)
from app.services.replay_policies.basic_policy import BasicReplayPolicy
from app.services.replay_service import ReplayContext as _Ctx  # noqa: F401
from app.services.replay_service import ReplayService


class _FixedDecisionPolicy(ReplayPolicy):
    name = "fixed"

    def __init__(self, decisions: list[ReplayDecision]) -> None:
        self._decisions = list(decisions)
        self._calls = 0

    def decide(self, ctx: ReplayContext) -> ReplayDecision:
        if self._calls >= len(self._decisions):
            return ReplayDecision(
                decision="No Trade",
                direction="none",
                target_price=None,
                invalidation_price=None,
                entry_reference=None,
                expected_rr=None,
                reason="fixture exhausted",
            )
        decision = self._decisions[self._calls]
        self._calls += 1
        return decision


def _seed_candles(
    db: Session, symbol: str, count: int, base_time: datetime, ohlc_factory
) -> None:
    for i in range(count):
        o, h, l, c = ohlc_factory(i)
        MarketService.create_snapshot(
            db,
            MarketDataInput(
                symbol=symbol,
                timeframe="M15",
                timestamp_utc=base_time + timedelta(minutes=15 * i),
                open=o,
                high=h,
                low=l,
                close=c,
            ),
        )


class ReplayServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=engine)
        self.db = Session(bind=engine)
        # Seed 60 M15 candles starting at a Q3 (08:00 UTC = 03:00 NY is Q2; let's pick UTC time
        # so that one of the eval points falls in Daye Q3 = 06:00-12:00 NY = 11:00-17:00 UTC).
        self.start = datetime(2024, 5, 20, 11, 0, tzinfo=UTC)
        _seed_candles(
            self.db,
            "XAUUSD",
            count=60,
            base_time=self.start,
            ohlc_factory=lambda i: (
                2400 + i * 0.5,
                2400 + i * 0.5 + 2,
                2400 + i * 0.5 - 2,
                2400 + i * 0.5 + 1,
            ),
        )

    def tearDown(self) -> None:
        self.db.close()

    def test_run_executes_and_records_decisions(self) -> None:
        policy = _FixedDecisionPolicy(
            [
                ReplayDecision(
                    decision="Valid Setup",
                    direction="delivery_up",
                    target_price=Decimal("2405"),
                    invalidation_price=Decimal("2390"),
                    entry_reference=Decimal("2402"),
                    expected_rr=Decimal("2.0"),
                    reason="forced bullish",
                )
            ]
        )
        run = ReplayService.run(
            self.db,
            symbol="XAUUSD",
            timeframe="M15",
            start_utc=self.start,
            end_utc=self.start + timedelta(hours=8),
            policy=policy,
            step_bars=4,
            horizon_bars=10,
            secondary_symbol=None,
        )

        self.assertEqual("completed", run.status)
        self.assertGreater(run.evaluation_points, 1)
        decisions = ReplayService.decisions(self.db, run.id)
        self.assertEqual(run.evaluation_points, len(decisions))
        wins = [d for d in decisions if d.outcome == "win"]
        self.assertGreaterEqual(len(wins), 1)

    def test_policy_must_see_only_past_candles(self) -> None:
        observed_counts: list[int] = []

        class _SpyPolicy(ReplayPolicy):
            name = "spy"

            def decide(self, ctx: ReplayContext) -> ReplayDecision:
                observed_counts.append(len(ctx.primary_candles))
                last = ctx.primary_candles[-1]
                # Ensure last candle's timestamp equals as_of_utc (no look-ahead)
                last_ts = last.timestamp_utc
                if last_ts.tzinfo is None:
                    last_ts = last_ts.replace(tzinfo=UTC)
                assert last_ts == ctx.as_of_utc, (last_ts, ctx.as_of_utc)
                return ReplayDecision(
                    decision="No Trade",
                    direction="none",
                    target_price=None,
                    invalidation_price=None,
                    entry_reference=None,
                    expected_rr=None,
                    reason="spy",
                )

        ReplayService.run(
            self.db,
            symbol="XAUUSD",
            timeframe="M15",
            start_utc=self.start,
            end_utc=self.start + timedelta(hours=4),
            policy=_SpyPolicy(),
            step_bars=2,
            horizon_bars=4,
            secondary_symbol=None,
        )

        self.assertTrue(observed_counts)
        # Strictly monotonic increase because step_bars=2 and ordering is chronological
        self.assertEqual(observed_counts, sorted(observed_counts))
        self.assertTrue(all(n >= 1 for n in observed_counts))

    def test_grade_loss_path(self) -> None:
        policy = _FixedDecisionPolicy(
            [
                ReplayDecision(
                    decision="Valid Setup",
                    direction="delivery_up",
                    target_price=Decimal("9999"),
                    invalidation_price=Decimal("2402"),
                    entry_reference=Decimal("2406"),
                    expected_rr=Decimal("3.0"),
                    reason="forced bullish unreachable target",
                )
            ]
        )
        run = ReplayService.run(
            self.db,
            symbol="XAUUSD",
            timeframe="M15",
            start_utc=self.start,
            end_utc=self.start + timedelta(hours=2),
            policy=policy,
            step_bars=4,
            horizon_bars=20,
            secondary_symbol=None,
        )

        decisions = ReplayService.decisions(self.db, run.id)
        self.assertTrue(any(d.outcome == "loss" for d in decisions))
        loss = next(d for d in decisions if d.outcome == "loss")
        self.assertEqual(Decimal("-1"), loss.realized_rr)


class BasicReplayPolicyTest(unittest.TestCase):
    def test_no_trade_when_quarter_not_q2_or_q3(self) -> None:
        # Daye Q1 is 18:00-00:00 NY (= 23:00-05:00 UTC); pick 23:30 UTC
        as_of = datetime(2024, 5, 20, 23, 30, tzinfo=UTC)
        engine_no_candles = []
        ctx = ReplayContext(
            symbol="XAUUSD",
            timeframe="M15",
            as_of_utc=as_of,
            primary_candles=engine_no_candles,
            secondary_candles=[],
            time_context={"daily_quarter": "Q1"},
        )
        policy = BasicReplayPolicy()
        decision = policy.decide(ctx)
        self.assertEqual("No Trade", decision.decision)
        self.assertIn("Insufficient", decision.reason)


if __name__ == "__main__":
    unittest.main()
