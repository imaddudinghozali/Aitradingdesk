"""Hypothetical raw-candle replay engine.

Walks chronologically through stored market candles within [start_utc, end_utc],
calling a `ReplayPolicy` at each evaluation point with strictly past data
(no look-ahead), then grades the decision against subsequent candles up to
`horizon_bars`. Results are persisted as `replay_runs` + `replay_decisions`.

This complements `BacktestService` (which scores already-recorded decisions).
Replay rebuilds hypothetical decisions from raw candles.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from app.engines.time_engine import TimeEngine
from app.models.market_snapshot import MarketSnapshot
from app.models.replay_decision import ReplayDecisionRow
from app.models.replay_run import ReplayRun
from app.services.replay_policies.base import (
    ReplayContext,
    ReplayDecision,
    ReplayPolicy,
)

logger = logging.getLogger(__name__)


@dataclass
class ReplaySummary:
    evaluation_points: int
    valid_setups: int
    no_trades: int
    setup_wins: int
    setup_losses: int
    setup_unresolved: int
    winrate: Decimal | None
    average_rr: Decimal | None
    max_drawdown_rr: Decimal | None


class ReplayService:
    METHODOLOGY = (
        "Raw-candle replay: at every Nth stored candle within the window, the policy "
        "receives only candles up to that timestamp and emits a hypothetical decision. "
        "Each decision is then graded against the next `horizon_bars` candles strictly in "
        "the future. No stored gate state is used, so this is a clean shadow of the "
        "framework's behavior on historical data. Replay does NOT replace the "
        "decision-time backtest endpoint, which scores actually-recorded decisions."
    )

    @staticmethod
    def run(
        db: Session,
        symbol: str,
        timeframe: str,
        start_utc: datetime,
        end_utc: datetime,
        policy: ReplayPolicy,
        step_bars: int = 1,
        horizon_bars: int = 24,
        secondary_symbol: str | None = "XAGUSD",
    ) -> ReplayRun:
        if start_utc > end_utc:
            raise ValueError("start_utc must be <= end_utc")
        if step_bars < 1:
            raise ValueError("step_bars must be >= 1")
        if horizon_bars < 1:
            raise ValueError("horizon_bars must be >= 1")

        primary_all = (
            db.query(MarketSnapshot)
            .filter(
                MarketSnapshot.symbol == symbol,
                MarketSnapshot.timeframe == timeframe,
            )
            .order_by(MarketSnapshot.timestamp_utc.asc(), MarketSnapshot.id.asc())
            .all()
        )
        if not primary_all:
            raise ValueError(f"No stored candles for {symbol} {timeframe}")

        secondary_all = (
            db.query(MarketSnapshot)
            .filter(
                MarketSnapshot.symbol == secondary_symbol,
                MarketSnapshot.timeframe == timeframe,
            )
            .order_by(MarketSnapshot.timestamp_utc.asc(), MarketSnapshot.id.asc())
            .all()
            if secondary_symbol
            else []
        )

        window = [
            i for i, c in enumerate(primary_all)
            if start_utc <= _to_utc(c.timestamp_utc) <= end_utc
        ]
        if not window:
            raise ValueError("No stored candles fall inside the requested window")

        run = ReplayRun(
            symbol=symbol,
            timeframe=timeframe,
            policy_name=policy.name,
            start_utc=start_utc,
            end_utc=end_utc,
            step_bars=step_bars,
            horizon_bars=horizon_bars,
            status="running",
            methodology=ReplayService.METHODOLOGY,
        )
        db.add(run)
        db.flush()

        decisions: list[ReplayDecisionRow] = []
        for idx in window[::step_bars]:
            primary_history = primary_all[: idx + 1]
            current = primary_all[idx]
            as_of = _to_utc(current.timestamp_utc)
            secondary_history = [
                s for s in secondary_all if _to_utc(s.timestamp_utc) <= as_of
            ]
            ctx = ReplayContext(
                symbol=symbol,
                timeframe=timeframe,
                as_of_utc=as_of,
                primary_candles=primary_history,
                secondary_candles=secondary_history,
                time_context=TimeEngine.get_time_context(as_of),
            )
            try:
                decision = policy.decide(ctx)
            except Exception as exc:  # pragma: no cover - defensive
                logger.exception("Replay policy %s raised: %s", policy.name, exc)
                decision = ReplayDecision(
                    decision="No Trade",
                    direction="none",
                    target_price=None,
                    invalidation_price=None,
                    entry_reference=None,
                    expected_rr=None,
                    reason=f"policy_error: {exc}",
                )

            future = primary_all[idx + 1 : idx + 1 + horizon_bars]
            outcome, realized_rr, outcome_reason = _grade(decision, future)
            decisions.append(
                ReplayDecisionRow(
                    replay_run_id=run.id,
                    as_of_utc=as_of,
                    daily_quarter=ctx.time_context.get("daily_quarter", ""),
                    session=ctx.time_context.get("session", ""),
                    decision=decision.decision,
                    direction=decision.direction,
                    entry_reference=decision.entry_reference,
                    target_price=decision.target_price,
                    invalidation_price=decision.invalidation_price,
                    expected_rr=decision.expected_rr,
                    bars_observed=len(future),
                    outcome=outcome,
                    realized_rr=realized_rr,
                    outcome_reason=outcome_reason,
                    reason=decision.reason,
                )
            )

        db.add_all(decisions)
        db.flush()

        summary = _summarize(decisions)
        run.evaluation_points = summary.evaluation_points
        run.valid_setups = summary.valid_setups
        run.no_trades = summary.no_trades
        run.setup_wins = summary.setup_wins
        run.setup_losses = summary.setup_losses
        run.setup_unresolved = summary.setup_unresolved
        run.winrate = summary.winrate
        run.average_rr = summary.average_rr
        run.max_drawdown_rr = summary.max_drawdown_rr
        run.status = "completed"
        run.completed_at_utc = datetime.now(tz=UTC)
        db.commit()
        db.refresh(run)
        return run

    @staticmethod
    def list_runs(db: Session, symbol: str | None = None, limit: int = 100) -> list[ReplayRun]:
        query = db.query(ReplayRun)
        if symbol:
            query = query.filter(ReplayRun.symbol == symbol.upper())
        return query.order_by(ReplayRun.created_at.desc(), ReplayRun.id.desc()).limit(limit).all()

    @staticmethod
    def decisions(db: Session, run_id: int) -> list[ReplayDecisionRow]:
        return (
            db.query(ReplayDecisionRow)
            .filter(ReplayDecisionRow.replay_run_id == run_id)
            .order_by(ReplayDecisionRow.as_of_utc.asc(), ReplayDecisionRow.id.asc())
            .all()
        )


def _to_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _grade(
    decision: ReplayDecision,
    future_candles: list[MarketSnapshot],
) -> tuple[str, Decimal | None, str]:
    if decision.decision != "Valid Setup":
        if decision.target_price is None or decision.invalidation_price is None:
            return "no_trade", None, "No Trade — not graded against price outcome."
        for candle in future_candles:
            target = _target_hit(decision.direction, decision.target_price, candle)
            invalid = _invalidation_hit(decision.direction, decision.invalidation_price, candle)
            if target and invalid:
                return "ambiguous", None, "Both target and invalidation hit in one bar."
            if invalid:
                return "protected_no_trade", None, "No Trade guard avoided failed delivery."
            if target:
                return "missed_delivery", None, "Target hit first; conservative miss proxy."
        return "no_trade", None, "No Trade — neither target nor invalidation reached in horizon."

    if (
        decision.target_price is None
        or decision.invalidation_price is None
        or decision.entry_reference is None
    ):
        return "unresolved", None, "Decision missing geometry; cannot grade."
    if not future_candles:
        return "unresolved", None, "No future candles within horizon."

    for candle in future_candles:
        target = _target_hit(decision.direction, decision.target_price, candle)
        invalid = _invalidation_hit(decision.direction, decision.invalidation_price, candle)
        if target and invalid:
            return "ambiguous", None, "Both target and invalidation hit in one bar."
        if target:
            return "win", decision.expected_rr, "Target reached before invalidation."
        if invalid:
            return "loss", Decimal("-1"), "Invalidation reached before target."
    return "unresolved", None, "Neither target nor invalidation reached in horizon."


def _target_hit(direction: str, target: Decimal, candle: MarketSnapshot) -> bool:
    if direction == "delivery_up":
        return candle.high >= target
    if direction == "delivery_down":
        return candle.low <= target
    return False


def _invalidation_hit(direction: str, invalidation: Decimal, candle: MarketSnapshot) -> bool:
    if direction == "delivery_up":
        return candle.low <= invalidation
    if direction == "delivery_down":
        return candle.high >= invalidation
    return False


def _summarize(decisions: list[ReplayDecisionRow]) -> ReplaySummary:
    valid = [d for d in decisions if d.decision == "Valid Setup"]
    no_trades = [d for d in decisions if d.decision == "No Trade"]
    resolved = [d for d in valid if d.outcome in {"win", "loss"}]
    results = [d.realized_rr for d in resolved if d.realized_rr is not None]
    wins = sum(d.outcome == "win" for d in resolved)

    return ReplaySummary(
        evaluation_points=len(decisions),
        valid_setups=len(valid),
        no_trades=len(no_trades),
        setup_wins=wins,
        setup_losses=sum(d.outcome == "loss" for d in resolved),
        setup_unresolved=len(valid) - len(resolved),
        winrate=Decimal(wins) / Decimal(len(resolved)) if resolved else None,
        average_rr=(
            sum(results, Decimal(0)) / Decimal(len(results)) if results else None
        ),
        max_drawdown_rr=_max_drawdown(results),
    )


def _max_drawdown(values: list[Decimal]) -> Decimal | None:
    if not values:
        return None
    equity = Decimal(0)
    peak = Decimal(0)
    drawdown = Decimal(0)
    for value in values:
        equity += value
        peak = max(peak, equity)
        drawdown = max(drawdown, peak - equity)
    return drawdown
