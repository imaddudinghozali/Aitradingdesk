from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.backtest_observation import BacktestObservation
from app.models.backtest_run import BacktestRun
from app.models.execution_assessment import ExecutionAssessment
from app.models.market_snapshot import MarketSnapshot
from app.models.narrative_snapshot import NarrativeSnapshot
from app.models.ssmt_event import SsmtEvent
from app.models.sweep_event import SweepEvent
from app.schemas.backtest import BacktestBreakdownBucket, BacktestRunRequest


class BacktestService:
    METHODOLOGY = (
        "Walk-forward scoring of stored narrative decisions only. Each observation uses the "
        "execution geometry persisted at decision time and candles strictly after its timestamp "
        "for the requested horizon. No Trade accuracy is a conservative target-versus-invalidation "
        "proxy, not proof that no alternative entry existed. False sweep rate measures resolved "
        "setup failure after a confirmed source sweep; false SSMT rate measures Magneto-invalidated "
        "stored SSMT events."
    )
    CONFIRMED_SWEEPS = {"Valid Sweep", "Turtle Soup", "Manipulation Sweep"}

    @staticmethod
    def run(db: Session, request: BacktestRunRequest) -> BacktestRun:
        if request.start_utc and request.end_utc and request.start_utc > request.end_utc:
            raise ValueError("start_utc must be earlier than or equal to end_utc.")
        query = db.query(NarrativeSnapshot).filter(NarrativeSnapshot.symbol == request.symbol)
        if request.start_utc:
            query = query.filter(NarrativeSnapshot.as_of_utc >= request.start_utc)
        if request.end_utc:
            query = query.filter(NarrativeSnapshot.as_of_utc <= request.end_utc)
        snapshots = query.order_by(NarrativeSnapshot.as_of_utc.asc(), NarrativeSnapshot.id.asc()).all()
        if not snapshots:
            raise ValueError(
                "No stored narrative snapshots found for this range. "
                "Backtest scores recorded point-in-time decisions only."
            )

        run = BacktestRun(
            symbol=request.symbol,
            timeframe=request.timeframe,
            start_utc=request.start_utc,
            end_utc=request.end_utc,
            horizon_bars=request.horizon_bars,
            status="running",
            methodology=BacktestService.METHODOLOGY,
        )
        db.add(run)
        db.flush()
        observations = [
            BacktestService._observation(db, run.id, snapshot, request)
            for snapshot in snapshots
        ]
        db.add_all(observations)
        db.flush()
        BacktestService._summarize(db, run, observations, request)
        run.status = "completed"
        run.completed_at_utc = datetime.now(UTC)
        db.commit()
        db.refresh(run)
        return run

    @staticmethod
    def list_runs(db: Session, symbol: str | None = None, limit: int = 100) -> list[BacktestRun]:
        query = db.query(BacktestRun)
        if symbol:
            query = query.filter(BacktestRun.symbol == symbol)
        return query.order_by(BacktestRun.created_at.desc(), BacktestRun.id.desc()).limit(limit).all()

    @staticmethod
    def observations(db: Session, run_id: int) -> list[BacktestObservation]:
        return (
            db.query(BacktestObservation)
            .filter(BacktestObservation.backtest_run_id == run_id)
            .order_by(BacktestObservation.observed_at_utc.asc(), BacktestObservation.id.asc())
            .all()
        )

    @staticmethod
    def breakdown(db: Session, run_id: int) -> list[BacktestBreakdownBucket]:
        observations = [
            row for row in BacktestService.observations(db, run_id)
            if row.execution_status == "Valid Setup"
        ]
        dimensions = [
            ("DOL", "htf_dol"),
            ("IRL/ERL", "direction_liquidity"),
            ("SSMT", "ssmt_status"),
            ("Judas", "judas_status"),
            ("OPR", "opr_status"),
            ("MMXM", "active_model"),
            ("Session", "session"),
            ("Quarter", "daily_quarter"),
        ]
        buckets: list[BacktestBreakdownBucket] = []
        for concept, field in dimensions:
            values = sorted({BacktestService._category(getattr(row, field)) for row in observations})
            for value in values:
                selected = [
                    row for row in observations
                    if BacktestService._category(getattr(row, field)) == value
                ]
                resolved = [row for row in selected if row.outcome in {"win", "loss"}]
                results = [row.realized_rr for row in resolved if row.realized_rr is not None]
                wins = sum(row.outcome == "win" for row in resolved)
                buckets.append(
                    BacktestBreakdownBucket(
                        concept=concept,
                        value=value,
                        setup_samples=len(selected),
                        resolved_setups=len(resolved),
                        wins=wins,
                        winrate=(
                            Decimal(wins) / Decimal(len(resolved)) if resolved else None
                        ),
                        average_rr=(
                            sum(results, Decimal(0)) / Decimal(len(results))
                            if results else None
                        ),
                    )
                )
        return buckets

    @staticmethod
    def _observation(
        db: Session,
        run_id: int,
        snapshot: NarrativeSnapshot,
        request: BacktestRunRequest,
    ) -> BacktestObservation:
        execution = (
            db.get(ExecutionAssessment, snapshot.execution_assessment_id)
            if snapshot.execution_assessment_id else None
        )
        candles = BacktestService._future_candles(
            db, snapshot.symbol, request.timeframe, snapshot.as_of_utc, request.horizon_bars
        )
        outcome, realized_rr, reason = BacktestService._score(snapshot, execution, candles)
        return BacktestObservation(
            backtest_run_id=run_id,
            narrative_snapshot_id=snapshot.id,
            execution_assessment_id=execution.id if execution else None,
            source_sweep_event_id=snapshot.source_sweep_event_id,
            symbol=snapshot.symbol,
            timeframe=request.timeframe,
            observed_at_utc=snapshot.as_of_utc,
            session=snapshot.session,
            daily_quarter=snapshot.daily_quarter,
            htf_dol=snapshot.htf_dol,
            direction_liquidity=snapshot.direction_liquidity,
            active_model=snapshot.active_model,
            ssmt_status=snapshot.ssmt_status,
            judas_status=snapshot.judas_manipulation_status,
            opr_status=snapshot.opr_status,
            mmxm_timing_context=snapshot.mmxm_timing_context,
            execution_status=snapshot.execution_status,
            entry_reference=execution.entry_reference if execution else None,
            invalidation_price=execution.invalidation_price if execution else None,
            target_price=execution.target_price if execution else None,
            expected_rr=execution.rr_ratio if execution else None,
            bars_observed=len(candles),
            outcome=outcome,
            realized_rr=realized_rr,
            outcome_reason=reason,
        )

    @staticmethod
    def _future_candles(
        db: Session,
        symbol: str,
        timeframe: str,
        observed_at: datetime,
        horizon: int,
    ) -> list[MarketSnapshot]:
        return (
            db.query(MarketSnapshot)
            .filter(
                MarketSnapshot.symbol == symbol,
                MarketSnapshot.timeframe == timeframe,
                MarketSnapshot.timestamp_utc > observed_at,
            )
            .order_by(MarketSnapshot.timestamp_utc.asc(), MarketSnapshot.id.asc())
            .limit(horizon)
            .all()
        )

    @staticmethod
    def _score(
        snapshot: NarrativeSnapshot,
        execution: ExecutionAssessment | None,
        candles: list[MarketSnapshot],
    ) -> tuple[str, Decimal | None, str]:
        if execution is None or execution.target_price is None or execution.entry_reference is None:
            return (
                "unscored",
                None,
                "No immutable execution geometry is attached to this narrative snapshot.",
            )
        if not candles:
            return "unresolved", None, "No later candles exist inside the selected outcome horizon."
        direction = execution.delivery_direction
        for candle in candles:
            target = BacktestService._target_hit(direction, execution.target_price, candle)
            invalid = BacktestService._invalidation_hit(
                direction, execution.invalidation_price, candle
            )
            if target and invalid:
                return (
                    "ambiguous",
                    None,
                    "Target and invalidation were both crossed within one candle; order is unknowable.",
                )
            if snapshot.execution_status == "Valid Setup":
                if target:
                    return "win", execution.rr_ratio, "Target liquidity was reached before invalidation."
                if invalid:
                    return "loss", Decimal("-1"), "Invalidation was reached before target liquidity."
            elif snapshot.execution_status == "No Trade":
                if invalid:
                    return (
                        "protected_no_trade",
                        None,
                        "Invalidation was reached before target; the No Trade guard avoided failed delivery.",
                    )
                if target:
                    return (
                        "missed_delivery",
                        None,
                        "Target was reached first; recorded as a conservative No Trade miss proxy.",
                    )
        return "unresolved", None, "Neither target nor invalidation was reached inside the outcome horizon."

    @staticmethod
    def _summarize(
        db: Session,
        run: BacktestRun,
        observations: list[BacktestObservation],
        request: BacktestRunRequest,
    ) -> None:
        setups = [item for item in observations if item.execution_status == "Valid Setup"]
        resolved_setups = [item for item in setups if item.outcome in {"win", "loss"}]
        no_trades = [item for item in observations if item.execution_status == "No Trade"]
        resolved_no_trades = [
            item for item in no_trades if item.outcome in {"protected_no_trade", "missed_delivery"}
        ]
        results = [
            item.realized_rr for item in resolved_setups if item.realized_rr is not None
        ]
        wins = sum(item.outcome == "win" for item in resolved_setups)
        run.narrative_samples = len(observations)
        run.scored_samples = sum(item.outcome not in {"unscored", "unresolved", "ambiguous"} for item in observations)
        run.valid_setup_samples = len(setups)
        run.setup_wins = wins
        run.setup_losses = sum(item.outcome == "loss" for item in resolved_setups)
        run.setup_unresolved = len(setups) - len(resolved_setups)
        run.no_trade_samples = len(no_trades)
        run.no_trade_scored = len(resolved_no_trades)
        run.no_trade_correct = sum(item.outcome == "protected_no_trade" for item in resolved_no_trades)
        run.winrate = Decimal(wins) / Decimal(len(resolved_setups)) if resolved_setups else None
        run.average_rr = sum(results, Decimal(0)) / Decimal(len(results)) if results else None
        run.max_drawdown_rr = BacktestService._max_drawdown(results)
        run.no_trade_accuracy = (
            Decimal(run.no_trade_correct) / Decimal(len(resolved_no_trades))
            if resolved_no_trades else None
        )
        run.false_ssmt_rate = BacktestService._false_ssmt_rate(db, request)
        run.false_sweep_rate = BacktestService._false_sweep_rate(db, resolved_setups)
        run.best_session, run.worst_session = BacktestService._best_worst(resolved_setups, "session")
        run.best_quarter, run.worst_quarter = BacktestService._best_worst(
            resolved_setups, "daily_quarter"
        )

    @staticmethod
    def _false_ssmt_rate(db: Session, request: BacktestRunRequest) -> Decimal | None:
        query = db.query(SsmtEvent).filter(SsmtEvent.trade_asset == request.symbol)
        if request.start_utc:
            query = query.filter(SsmtEvent.as_of_utc >= request.start_utc)
        if request.end_utc:
            query = query.filter(SsmtEvent.as_of_utc <= request.end_utc)
        events = [
            event for event in query.all()
            if event.ssmt_status in {"valid_bullish", "valid_bearish", "magneto_invalidated"}
        ]
        if not events:
            return None
        false_count = sum(event.ssmt_status == "magneto_invalidated" for event in events)
        return Decimal(false_count) / Decimal(len(events))

    @staticmethod
    def _false_sweep_rate(
        db: Session,
        resolved_setups: list[BacktestObservation],
    ) -> Decimal | None:
        claimed: list[BacktestObservation] = []
        for observation in resolved_setups:
            event = (
                db.get(SweepEvent, observation.source_sweep_event_id)
                if observation.source_sweep_event_id else None
            )
            if event and event.sweep_status in BacktestService.CONFIRMED_SWEEPS:
                claimed.append(observation)
        if not claimed:
            return None
        return Decimal(sum(item.outcome == "loss" for item in claimed)) / Decimal(len(claimed))

    @staticmethod
    def _best_worst(
        observations: list[BacktestObservation],
        field: str,
    ) -> tuple[str | None, str | None]:
        groups: dict[str, list[Decimal]] = {}
        for item in observations:
            if item.realized_rr is not None:
                groups.setdefault(getattr(item, field), []).append(item.realized_rr)
        if not groups:
            return None, None
        averages = {
            name: sum(values, Decimal(0)) / Decimal(len(values))
            for name, values in groups.items()
        }
        best = max(averages, key=averages.get)
        worst = min(averages, key=averages.get)
        return (
            f"{best} (avg RR {BacktestService._number(averages[best])})",
            f"{worst} (avg RR {BacktestService._number(averages[worst])})",
        )

    @staticmethod
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

    @staticmethod
    def _target_hit(direction: str, target: Decimal, candle: MarketSnapshot) -> bool:
        return candle.high >= target if direction == "delivery_up" else candle.low <= target

    @staticmethod
    def _invalidation_hit(direction: str, invalidation: Decimal, candle: MarketSnapshot) -> bool:
        return candle.low <= invalidation if direction == "delivery_up" else candle.high >= invalidation

    @staticmethod
    def _number(value: Decimal) -> str:
        return format(value.normalize(), "f")

    @staticmethod
    def _category(value: str) -> str:
        return value.split(":", 1)[0].strip() if ":" in value else value.strip()
