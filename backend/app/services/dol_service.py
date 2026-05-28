from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models.dol_assessment import DolAssessment
from app.models.liquidity_level import LiquidityLevel
from app.models.market_snapshot import MarketSnapshot
from app.models.sweep_event import SweepEvent
from app.schemas.dol import DeliveryDirection, DolLifecycle
from app.schemas.liquidity import LiquidityStatus
from app.schemas.sweep import SweepStatus


class DolService:
    HTF_LEVEL_TYPES = {
        "PDH", "PDL", "PWH", "PWL", "PMH", "PML", "PYH", "PYL", "NEWS_HIGH", "NEWS_LOW"
    }
    REVERSAL_SWEEPS = {
        SweepStatus.VALID_SWEEP.value,
        SweepStatus.TURTLE_SOUP.value,
        SweepStatus.MANIPULATION_SWEEP.value,
    }
    CONFIRMED_SWEEPS = REVERSAL_SWEEPS | {
        SweepStatus.TRUE_BREAKOUT_BREAKDOWN.value,
    }

    @staticmethod
    def evaluate(db: Session, symbol: str, as_of_utc: datetime | None = None) -> DolAssessment:
        snapshots = (
            db.query(MarketSnapshot)
            .filter(MarketSnapshot.symbol == symbol)
            .order_by(MarketSnapshot.timestamp_utc.desc())
            .all()
        )
        if not snapshots:
            raise ValueError(f"No market snapshots found for {symbol}")
        cutoff = DolService._utc(as_of_utc or snapshots[0].timestamp_utc)
        latest = next(
            (
                snapshot
                for snapshot in snapshots
                if DolService._utc(snapshot.timestamp_utc) <= cutoff
            ),
            None,
        )
        if latest is None:
            raise ValueError("No market snapshots exist at or before as_of_utc")
        latest_price = latest.close

        current = db.query(DolAssessment).filter(DolAssessment.symbol == symbol).first()
        existing_primary = (
            db.get(LiquidityLevel, current.primary_level_id)
            if current and current.primary_level_id
            else None
        )
        resolved_status = DolService._resolved_status(existing_primary)

        excluded_event_id = current.source_sweep_event_id if current and current.primary_level_id else None
        event = DolService._latest_confirmed_event(db, symbol, cutoff, excluded_event_id)

        if current and existing_primary and not event:
            if resolved_status:
                current.lifecycle_status = resolved_status.value
                current.old_objective_resolved = True
                current.prior_narrative_resolved = True
                current.status_reason = (
                    f"Primary DOL {existing_primary.level_type} is {existing_primary.status}; "
                    "waiting for a newly confirmed delivery objective."
                )
            current.as_of_utc = cutoff
            db.commit()
            db.refresh(current)
            return current

        if event is None:
            assessment = current or DolAssessment(symbol=symbol)
            assessment.lifecycle_status = DolLifecycle.SHIFT_PENDING.value
            assessment.status_reason = (
                "No confirmed displacement from a relevant sweep event. "
                "DOL is not confirmed; No Trade."
            )
            assessment.as_of_utc = cutoff
            assessment.old_objective_resolved = bool(resolved_status)
            assessment.displacement_confirmed = False
            assessment.timing_confirmed = False
            assessment.prior_narrative_resolved = bool(resolved_status)
            if current is None:
                db.add(assessment)
            db.commit()
            db.refresh(assessment)
            return assessment

        direction = DolService._delivery_direction(event)
        htf, intraday, primary, secondary = DolService._select_targets(
            db,
            symbol,
            direction,
            latest_price,
        )
        engineered = (
            db.get(LiquidityLevel, event.liquidity_level_id)
            if event.sweep_status in DolService.REVERSAL_SWEEPS
            else None
        )

        if primary is None:
            assessment = current or DolAssessment(symbol=symbol)
            assessment.lifecycle_status = (
                resolved_status.value if resolved_status else DolLifecycle.SHIFT_PENDING.value
            )
            assessment.delivery_direction = direction.value
            assessment.engineered_level_id = engineered.id if engineered else None
            assessment.source_sweep_event_id = event.id
            assessment.status_reason = (
                f"Confirmed {event.sweep_status} implies {direction.value}, "
                "but no untaken target liquidity is available in that direction."
            )
            assessment.displacement_confirmed = event.displacement_detected
            assessment.timing_confirmed = event.relevant_timing
            assessment.old_objective_resolved = bool(resolved_status)
            assessment.prior_narrative_resolved = bool(resolved_status)
            assessment.as_of_utc = cutoff
            if current is None:
                db.add(assessment)
            db.commit()
            db.refresh(assessment)
            return assessment

        if current is None or existing_primary is None:
            assessment = current or DolAssessment(symbol=symbol)
            DolService._apply_objective(
                assessment, direction, htf, intraday, primary, secondary, engineered, event
            )
            assessment.lifecycle_status = DolLifecycle.ACTIVE.value
            assessment.status_reason = DolService._active_reason(event, primary)
            assessment.old_objective_resolved = False
            assessment.prior_narrative_resolved = False
            assessment.as_of_utc = cutoff
            if current is None:
                db.add(assessment)
            db.commit()
            db.refresh(assessment)
            return assessment

        if existing_primary.id == primary.id:
            DolService._apply_objective(
                current, direction, htf, intraday, primary, secondary, engineered, event
            )
            current.lifecycle_status = DolLifecycle.ACTIVE.value
            current.status_reason = DolService._active_reason(event, primary)
            current.as_of_utc = cutoff
            db.commit()
            db.refresh(current)
            return current

        old_resolved = resolved_status is not None
        shift_ready = (
            old_resolved
            and event.displacement_detected
            and event.relevant_timing
        )
        if shift_ready:
            DolService._apply_objective(
                current, direction, htf, intraday, primary, secondary, engineered, event
            )
            current.lifecycle_status = DolLifecycle.SHIFT_CONFIRMED.value
            current.status_reason = (
                f"DOL shift confirmed from resolved {existing_primary.level_type} "
                f"to {primary.level_type}: prior objective resolved, displacement confirmed, "
                "and session/quarter timing supports the new delivery."
            )
            current.old_objective_resolved = True
            current.prior_narrative_resolved = True
        else:
            current.lifecycle_status = (
                DolLifecycle.WEAKENING.value
                if not old_resolved
                else DolLifecycle.SHIFT_PENDING.value
            )
            current.secondary_level_id = primary.id
            current.engineered_level_id = engineered.id if engineered else None
            current.status_reason = (
                f"Potential new objective {primary.level_type} detected from {event.sweep_status}, "
                f"but active DOL {existing_primary.level_type} is not yet resolved. "
                "DOL change rejected until all shift rules are met."
                if not old_resolved
                else (
                    f"Prior objective {existing_primary.level_type} is resolved, but shift "
                    "confirmation is incomplete; retaining prior DOL pending full validation."
                )
            )
            current.old_objective_resolved = old_resolved
            current.prior_narrative_resolved = old_resolved
            current.displacement_confirmed = event.displacement_detected
            current.timing_confirmed = event.relevant_timing
        current.as_of_utc = cutoff
        db.commit()
        db.refresh(current)
        return current

    @staticmethod
    def get_current(db: Session, symbol: str) -> DolAssessment | None:
        return db.query(DolAssessment).filter(DolAssessment.symbol == symbol.upper()).first()

    @staticmethod
    def _latest_confirmed_event(
        db: Session,
        symbol: str,
        cutoff: datetime,
        excluded_event_id: int | None,
    ) -> SweepEvent | None:
        events = (
            db.query(SweepEvent)
            .filter(SweepEvent.symbol == symbol)
            .order_by(SweepEvent.detected_at_utc.desc(), SweepEvent.id.desc())
            .all()
        )
        for event in events:
            if excluded_event_id and event.id == excluded_event_id:
                continue
            if DolService._utc(event.detected_at_utc) > cutoff:
                continue
            if event.sweep_status not in DolService.CONFIRMED_SWEEPS:
                continue
            if not event.displacement_detected or not event.relevant_timing:
                continue
            return event
        return None

    @staticmethod
    def _delivery_direction(event: SweepEvent) -> DeliveryDirection:
        reversed_delivery = event.sweep_status in DolService.REVERSAL_SWEEPS
        if event.liquidity_side == "BSL":
            return DeliveryDirection.DOWN if reversed_delivery else DeliveryDirection.UP
        return DeliveryDirection.UP if reversed_delivery else DeliveryDirection.DOWN

    @staticmethod
    def _select_targets(
        db: Session,
        symbol: str,
        direction: DeliveryDirection,
        latest_price,
    ) -> tuple[LiquidityLevel | None, LiquidityLevel | None, LiquidityLevel | None, LiquidityLevel | None]:
        desired_side = "BSL" if direction == DeliveryDirection.UP else "SSL"
        levels = (
            db.query(LiquidityLevel)
            .filter(
                LiquidityLevel.symbol == symbol,
                LiquidityLevel.liquidity_side == desired_side,
                LiquidityLevel.status.in_(
                    [LiquidityStatus.ACTIVE.value, LiquidityStatus.TOUCHED.value]
                ),
            )
            .all()
        )
        directional = [
            level
            for level in levels
            if (
                direction == DeliveryDirection.UP and level.price > latest_price
            ) or (
                direction == DeliveryDirection.DOWN and level.price < latest_price
            )
        ]
        directional.sort(key=lambda level: abs(level.price - latest_price))
        htf = next(
            (level for level in directional if level.level_type in DolService.HTF_LEVEL_TYPES),
            None,
        )
        intraday = next(
            (level for level in directional if level.level_type not in DolService.HTF_LEVEL_TYPES),
            None,
        )
        primary = htf or intraday
        secondary = next(
            (level for level in directional if primary is None or level.id != primary.id),
            None,
        )
        return htf, intraday, primary, secondary

    @staticmethod
    def _resolved_status(level: LiquidityLevel | None) -> DolLifecycle | None:
        if level is None:
            return None
        if level.status == LiquidityStatus.TAKEN.value:
            return DolLifecycle.COMPLETED
        if level.status == LiquidityStatus.INVALIDATED.value:
            return DolLifecycle.INVALIDATED
        return None

    @staticmethod
    def _apply_objective(
        assessment: DolAssessment,
        direction: DeliveryDirection,
        htf: LiquidityLevel | None,
        intraday: LiquidityLevel | None,
        primary: LiquidityLevel,
        secondary: LiquidityLevel | None,
        engineered: LiquidityLevel | None,
        event: SweepEvent,
    ) -> None:
        assessment.delivery_direction = direction.value
        assessment.primary_level_id = primary.id
        assessment.secondary_level_id = secondary.id if secondary else None
        assessment.htf_level_id = htf.id if htf else None
        assessment.intraday_level_id = intraday.id if intraday else None
        assessment.engineered_level_id = engineered.id if engineered else None
        assessment.source_sweep_event_id = event.id
        assessment.objective_quality = "true_objective"
        assessment.displacement_confirmed = event.displacement_detected
        assessment.timing_confirmed = event.relevant_timing

    @staticmethod
    def _active_reason(event: SweepEvent, primary: LiquidityLevel) -> str:
        return (
            f"Primary DOL {primary.level_type} selected as untaken {primary.liquidity_side} "
            f"objective after confirmed {event.sweep_status} with displacement during "
            f"{event.session} {event.daily_quarter}."
        )

    @staticmethod
    def _utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
