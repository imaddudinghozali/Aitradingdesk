from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.engines.time_engine import TimeEngine
from app.models.dol_assessment import DolAssessment
from app.models.irl_erl_mapping import IrlErlMapping
from app.models.market_snapshot import MarketSnapshot
from app.models.quarter_readiness import QuarterReadinessAssessment
from app.models.sweep_event import SweepEvent
from app.schemas.quarter_readiness import QuarterStatus
from app.utils.timezone import to_ny_time, to_utc_time


class QuarterReadinessService:
    READY_DOL = {"Active", "Shift Confirmed"}
    CONFIRMED_SWEEPS = {
        "Valid Sweep",
        "Turtle Soup",
        "Manipulation Sweep",
        "True Breakout / Breakdown",
    }
    ENTRY_READY = {
        QuarterStatus.EXPANSION_READY,
        QuarterStatus.EXPANSION_ACTIVE,
    }

    @staticmethod
    def evaluate(
        db: Session,
        symbol: str,
        as_of_utc: datetime | None = None,
    ) -> QuarterReadinessAssessment:
        market = QuarterReadinessService._latest_market(db, symbol, as_of_utc)
        dol = db.query(DolAssessment).filter(DolAssessment.symbol == symbol).first()
        if dol is None:
            raise ValueError("DOL assessment not found. Evaluate DOL before quarter readiness.")
        mapping = db.query(IrlErlMapping).filter(IrlErlMapping.symbol == symbol).first()
        if mapping is None:
            raise ValueError(
                "Direction liquidity mapping not found. Evaluate IRL/ERL before quarter readiness."
            )

        start_ny, end_ny = QuarterReadinessService._quarter_window(market.timestamp_utc)
        source_sweep = QuarterReadinessService._quarter_sweep(
            db,
            symbol,
            to_utc_time(start_ny),
            QuarterReadinessService._utc(market.timestamp_utc),
        )
        status, reason = QuarterReadinessService._classify(
            market,
            dol,
            mapping,
            source_sweep,
            start_ny,
        )
        allowed = (
            status in QuarterReadinessService.ENTRY_READY
            and dol.lifecycle_status in QuarterReadinessService.READY_DOL
            and mapping.mapping_status == "aligned"
            and dol.delivery_direction is not None
        )
        assessment = (
            db.query(QuarterReadinessAssessment)
            .filter(QuarterReadinessAssessment.symbol == symbol)
            .first()
        )
        assessment = assessment or QuarterReadinessAssessment(symbol=symbol)
        assessment.market_snapshot_id = market.id
        assessment.dol_assessment_id = dol.id
        assessment.irl_erl_mapping_id = mapping.id
        assessment.source_sweep_event_id = source_sweep.id if source_sweep else None
        assessment.daily_quarter = market.daily_quarter
        assessment.micro_quarter_90m = market.micro_quarter_90m
        assessment.session = market.session
        assessment.quarter_status = status.value
        assessment.quarter_intent = QuarterReadinessService._intent(dol)
        assessment.manipulation_status = QuarterReadinessService._manipulation(source_sweep)
        assessment.expansion_status = QuarterReadinessService._expansion(status, source_sweep)
        assessment.quarter_execution_allowed = allowed
        assessment.gate_decision = "Waiting Confirmation" if allowed else "No Trade"
        assessment.status_reason = reason
        assessment.next_valid_window = QuarterReadinessService._next_window(
            status,
            market.daily_quarter,
            end_ny,
        )
        assessment.as_of_utc = market.timestamp_utc
        if assessment.id is None:
            db.add(assessment)
        db.commit()
        db.refresh(assessment)
        return assessment

    @staticmethod
    def get_current(db: Session, symbol: str) -> QuarterReadinessAssessment | None:
        return (
            db.query(QuarterReadinessAssessment)
            .filter(QuarterReadinessAssessment.symbol == symbol)
            .first()
        )

    @staticmethod
    def _latest_market(
        db: Session,
        symbol: str,
        as_of_utc: datetime | None,
    ) -> MarketSnapshot:
        snapshots = (
            db.query(MarketSnapshot)
            .filter(MarketSnapshot.symbol == symbol)
            .order_by(MarketSnapshot.timestamp_utc.desc(), MarketSnapshot.id.desc())
            .all()
        )
        if not snapshots:
            raise ValueError(f"No market snapshots found for {symbol}")
        if as_of_utc is None:
            return snapshots[0]
        cutoff = QuarterReadinessService._utc(as_of_utc)
        market = next(
            (
                snapshot
                for snapshot in snapshots
                if QuarterReadinessService._utc(snapshot.timestamp_utc) <= cutoff
            ),
            None,
        )
        if market is None:
            raise ValueError("No market snapshots exist at or before as_of_utc")
        return market

    @staticmethod
    def _quarter_window(timestamp_utc: datetime) -> tuple[datetime, datetime]:
        current_ny = to_ny_time(QuarterReadinessService._utc(timestamp_utc))
        start_hours = {"Q1": 18, "Q2": 0, "Q3": 6, "Q4": 12}
        start_ny = current_ny.replace(
            hour=start_hours[TimeEngine.get_daily_quarter(current_ny).value],
            minute=0,
            second=0,
            microsecond=0,
        )
        return start_ny, start_ny + timedelta(hours=6)

    @staticmethod
    def _quarter_sweep(
        db: Session,
        symbol: str,
        quarter_start_utc: datetime,
        cutoff_utc: datetime,
    ) -> SweepEvent | None:
        events = (
            db.query(SweepEvent)
            .filter(SweepEvent.symbol == symbol)
            .order_by(SweepEvent.detected_at_utc.desc(), SweepEvent.id.desc())
            .all()
        )
        return next(
            (
                event
                for event in events
                if quarter_start_utc <= QuarterReadinessService._utc(event.detected_at_utc) <= cutoff_utc
            ),
            None,
        )

    @staticmethod
    def _classify(
        market: MarketSnapshot,
        dol: DolAssessment,
        mapping: IrlErlMapping,
        sweep: SweepEvent | None,
        start_ny: datetime,
    ) -> tuple[QuarterStatus, str]:
        current_ny = to_ny_time(QuarterReadinessService._utc(market.timestamp_utc))
        elapsed_minutes = int((current_ny - start_ny).total_seconds() / 60)
        if elapsed_minutes >= 300:
            return (
                QuarterStatus.CLOSED_LATE_ENTRY,
                "The active Daye quarter is in its final hour; new execution consideration is too late.",
            )
        if (
            dol.lifecycle_status in {"Weakening", "Completed", "Invalidated"}
            or mapping.mapping_status == "conflict"
        ):
            return (
                QuarterStatus.FAILURE_RISK,
                "DOL or direction liquidity conflicts with the active delivery context.",
            )
        if sweep is None:
            return (
                QuarterStatus.FORMING,
                "No liquidity interaction has established intent in the active quarter.",
            )
        confirmed_displacement = (
            sweep.sweep_status in QuarterReadinessService.CONFIRMED_SWEEPS
            and sweep.displacement_detected
            and sweep.relevant_timing
        )
        if not confirmed_displacement:
            return (
                QuarterStatus.MANIPULATION_PHASE,
                "Liquidity interaction is present, but displacement in a relevant timing window is not confirmed.",
            )
        if (
            dol.delivery_direction
            and QuarterReadinessService._delivery_direction(sweep) != dol.delivery_direction
        ):
            return (
                QuarterStatus.FAILURE_RISK,
                "Confirmed displacement points away from the active DOL delivery direction.",
            )
        if (
            dol.lifecycle_status in QuarterReadinessService.READY_DOL
            and mapping.mapping_status == "aligned"
            and dol.source_sweep_event_id == sweep.id
        ):
            return (
                QuarterStatus.EXPANSION_ACTIVE,
                "Confirmed displacement is linked to active DOL and aligned direction liquidity.",
            )
        return (
            QuarterStatus.EXPANSION_READY,
            "Initial displacement is confirmed, but active DOL alignment still needs confirmation.",
        )

    @staticmethod
    def _intent(dol: DolAssessment) -> str:
        if dol.delivery_direction == "delivery_up":
            return "Buyside delivery toward the active DOL."
        if dol.delivery_direction == "delivery_down":
            return "Sellside delivery toward the active DOL."
        return "Undetermined until DOL establishes delivery direction."

    @staticmethod
    def _delivery_direction(sweep: SweepEvent) -> str:
        reversal = sweep.sweep_status in {
            "Valid Sweep",
            "Turtle Soup",
            "Manipulation Sweep",
        }
        if sweep.liquidity_side == "BSL":
            return "delivery_down" if reversal else "delivery_up"
        return "delivery_up" if reversal else "delivery_down"

    @staticmethod
    def _manipulation(sweep: SweepEvent | None) -> str:
        if sweep is None:
            return "Waiting - no sweep or liquidity interaction recorded in the active quarter."
        return f"{sweep.sweep_status} observed at {sweep.level_type}."

    @staticmethod
    def _expansion(status: QuarterStatus, sweep: SweepEvent | None) -> str:
        if status == QuarterStatus.EXPANSION_ACTIVE:
            return "Active - displacement is aligned to current DOL delivery."
        if status == QuarterStatus.EXPANSION_READY:
            return "Ready - displacement is present while narrative alignment is pending."
        if sweep and sweep.displacement_detected:
            return "Displacement exists but the readiness gate is blocking continuation."
        return "Waiting - no validated expansion evidence."

    @staticmethod
    def _next_window(status: QuarterStatus, quarter: str, end_ny: datetime) -> str:
        if status in QuarterReadinessService.ENTRY_READY:
            return (
                f"Current {quarter} before {end_ny:%Y-%m-%d %H:%M} NY, "
                "subject to later execution confirmation."
            )
        if status in {QuarterStatus.FORMING, QuarterStatus.MANIPULATION_PHASE}:
            return (
                f"Current {quarter} before {end_ny:%Y-%m-%d %H:%M} NY "
                "after confirmed displacement aligns with DOL."
            )
        next_quarter = TimeEngine.get_daily_quarter(end_ny).value
        return (
            f"Next {next_quarter} starting {end_ny:%Y-%m-%d %H:%M} NY "
            "after a fresh readiness evaluation."
        )

    @staticmethod
    def _utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
