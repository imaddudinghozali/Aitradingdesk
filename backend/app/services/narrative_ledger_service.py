from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.dol_assessment import DolAssessment
from app.models.liquidity_level import LiquidityLevel
from app.models.market_snapshot import MarketSnapshot
from app.models.narrative_ledger import NarrativeLedger
from app.models.quarter_readiness import QuarterReadinessAssessment
from app.models.ssmt_event import SsmtEvent


class NarrativeLedgerService:
    TERMINAL_STATUSES = {"failed", "reversed", "redistributed"}
    VALID_INVALIDATION_STATUSES = {"active", "touched", "taken"}

    @staticmethod
    def ensure_active(
        db: Session,
        dol: DolAssessment,
        market: MarketSnapshot,
        target: LiquidityLevel | None,
        invalidation: LiquidityLevel | None,
        quarter: QuarterReadinessAssessment,
        ssmt: SsmtEvent | None,
    ) -> NarrativeLedger | None:
        if (
            target is None
            or invalidation is None
            or dol.delivery_direction not in {"delivery_up", "delivery_down"}
        ):
            return None
        existing = NarrativeLedgerService.get_current(db, dol.symbol)
        same_structure = (
            existing is not None
            and existing.target_level_id == target.id
            and existing.invalidation_level_id == invalidation.id
            and existing.delivery_direction == dol.delivery_direction
        )
        if same_structure:
            existing.quarter_readiness_id = quarter.id
            existing.ssmt_event_id = ssmt.id if ssmt else None
            existing.as_of_utc = market.timestamp_utc
            db.commit()
            db.refresh(existing)
            return existing

        ledger = NarrativeLedger(
            symbol=dol.symbol,
            dol_assessment_id=dol.id,
            quarter_readiness_id=quarter.id,
            ssmt_event_id=ssmt.id if ssmt else None,
            active_dol=NarrativeLedgerService._level_text(target),
            delivery_direction=dol.delivery_direction,
            target_level_id=target.id,
            target_liquidity=NarrativeLedgerService._level_text(target),
            invalidation_level_id=invalidation.id,
            invalidation_level=NarrativeLedgerService._level_text(invalidation),
            invalidation_price=invalidation.price,
            invalidation_condition=NarrativeLedgerService._condition(
                dol.delivery_direction, invalidation
            ),
            next_decision_if_invalidated=NarrativeLedgerService._next_decision(
                dol.delivery_direction
            ),
            reset_required=False,
            continuation_status="active",
            breach_status="clear",
            status_reason="Narrative registered with a defined target and invalidation boundary.",
            activated_at_utc=market.timestamp_utc,
            as_of_utc=market.timestamp_utc,
        )
        db.add(ledger)
        db.commit()
        db.refresh(ledger)
        return ledger

    @staticmethod
    def resolve_invalidation(
        db: Session,
        dol: DolAssessment,
        market: MarketSnapshot,
    ) -> LiquidityLevel | None:
        if dol.engineered_level_id:
            engineered = db.get(LiquidityLevel, dol.engineered_level_id)
            if engineered is not None:
                return engineered
        if dol.delivery_direction == "delivery_up":
            side = "SSL"
            candidates = (
                db.query(LiquidityLevel)
                .filter(
                    LiquidityLevel.symbol == dol.symbol,
                    LiquidityLevel.liquidity_side == side,
                    LiquidityLevel.status.in_(NarrativeLedgerService.VALID_INVALIDATION_STATUSES),
                    LiquidityLevel.price < market.close,
                )
                .all()
            )
        elif dol.delivery_direction == "delivery_down":
            side = "BSL"
            candidates = (
                db.query(LiquidityLevel)
                .filter(
                    LiquidityLevel.symbol == dol.symbol,
                    LiquidityLevel.liquidity_side == side,
                    LiquidityLevel.status.in_(NarrativeLedgerService.VALID_INVALIDATION_STATUSES),
                    LiquidityLevel.price > market.close,
                )
                .all()
            )
        else:
            return None
        candidates.sort(key=lambda level: abs(level.price - market.close))
        return candidates[0] if candidates else None

    @staticmethod
    def evaluate(
        db: Session,
        symbol: str,
        timeframe: str = "M15",
        as_of_utc: datetime | None = None,
    ) -> NarrativeLedger:
        ledger = NarrativeLedgerService.get_current(db, symbol)
        if ledger is None:
            raise ValueError(
                "Active narrative ledger not found. Generate a complete narrative first."
            )
        cutoff = NarrativeLedgerService._utc(as_of_utc or ledger.as_of_utc)
        if as_of_utc is None:
            latest = (
                db.query(MarketSnapshot)
                .filter(MarketSnapshot.symbol == symbol, MarketSnapshot.timeframe == timeframe)
                .order_by(MarketSnapshot.timestamp_utc.desc(), MarketSnapshot.id.desc())
                .first()
            )
            if latest is not None:
                cutoff = NarrativeLedgerService._utc(latest.timestamp_utc)
        if ledger.continuation_status in NarrativeLedgerService.TERMINAL_STATUSES:
            ledger.as_of_utc = cutoff
            db.commit()
            db.refresh(ledger)
            return ledger

        candles = (
            db.query(MarketSnapshot)
            .filter(MarketSnapshot.symbol == symbol, MarketSnapshot.timeframe == timeframe)
            .order_by(MarketSnapshot.timestamp_utc.asc(), MarketSnapshot.id.asc())
            .all()
        )
        observed = [
            candle
            for candle in candles
            if NarrativeLedgerService._utc(ledger.activated_at_utc)
            <= NarrativeLedgerService._utc(candle.timestamp_utc)
            <= cutoff
        ]
        breached = [
            candle
            for candle in observed
            if NarrativeLedgerService._close_breached(ledger, candle.close)
        ]
        latest_two = observed[-2:]
        confirmed_failure = (
            len(latest_two) == 2
            and all(
                NarrativeLedgerService._close_breached(ledger, candle.close)
                for candle in latest_two
            )
        )
        if confirmed_failure:
            ledger.continuation_status = "failed"
            ledger.breach_status = "close_and_hold_breached"
            ledger.reset_required = True
            ledger.invalidated_at_utc = latest_two[-1].timestamp_utc
            ledger.status_reason = (
                "Narrative failed: two consecutive closes breached the invalidation "
                "boundary. Reset DOL identification before any new setup."
            )
            dol = db.get(DolAssessment, ledger.dol_assessment_id)
            if dol is not None:
                dol.lifecycle_status = "Shift Pending"
                dol.prior_narrative_resolved = True
                dol.status_reason = (
                    "Narrative invalidation confirmed; active objective is suspended "
                    "pending fresh DOL identification. No Trade."
                )
        elif breached or any(NarrativeLedgerService._wick_breached(ledger, candle) for candle in observed):
            ledger.continuation_status = "weakening"
            ledger.breach_status = "potential_sweep"
            ledger.reset_required = False
            ledger.status_reason = (
                "Potential sweep of invalidation level; close-and-hold failure is not confirmed. "
                "Monitor the next quarter and keep execution blocked."
            )
        else:
            ledger.continuation_status = (
                "continuing" if ledger.continuation_status == "active" and len(observed) >= 2 else "active"
            )
            ledger.breach_status = "clear"
            ledger.reset_required = False
            ledger.status_reason = "Narrative invalidation boundary remains intact."
        ledger.as_of_utc = cutoff
        db.commit()
        db.refresh(ledger)
        return ledger

    @staticmethod
    def get_current(db: Session, symbol: str) -> NarrativeLedger | None:
        return (
            db.query(NarrativeLedger)
            .filter(NarrativeLedger.symbol == symbol)
            .order_by(NarrativeLedger.created_at.desc(), NarrativeLedger.id.desc())
            .first()
        )

    @staticmethod
    def apply_context_failure(
        db: Session,
        ledger: NarrativeLedger,
        dol: DolAssessment,
        quarter: QuarterReadinessAssessment,
        ssmt: SsmtEvent | None,
    ) -> NarrativeLedger:
        if ledger.continuation_status in NarrativeLedgerService.TERMINAL_STATUSES:
            return ledger
        reason: str | None = None
        if ssmt is not None and ssmt.ssmt_noise_status == "dol_conflict" and ssmt.cic_detected:
            reason = "Narrative failed: SSMT direction conflicts with the active DOL."
        elif quarter.quarter_status == "Failure Risk":
            reason = "Narrative failed: quarter delivery priority conflicts with the active DOL."
        elif (
            quarter.quarter_status == "Closed / Late Entry"
            and quarter.source_sweep_event_id is not None
            and quarter.source_sweep_event_id == dol.source_sweep_event_id
        ):
            target = db.get(LiquidityLevel, ledger.target_level_id)
            if target is not None and target.status != "taken":
                reason = (
                    "Narrative failed: expansion quarter closed before the active liquidity "
                    "objective was reached."
                )
        if reason is None:
            return ledger
        ledger.continuation_status = "failed"
        ledger.breach_status = "context_conflict"
        ledger.reset_required = True
        ledger.invalidated_at_utc = quarter.as_of_utc
        ledger.status_reason = reason + " Reset DOL identification before any new setup."
        dol.lifecycle_status = "Shift Pending"
        dol.prior_narrative_resolved = True
        dol.status_reason = reason + " Active objective is suspended. No Trade."
        db.commit()
        db.refresh(ledger)
        return ledger

    @staticmethod
    def invalidation_text(ledger: NarrativeLedger | None) -> str:
        if ledger is None:
            return "Narrative incomplete - invalidation level is not defined. No Trade."
        return f"{ledger.invalidation_condition} Current status: {ledger.continuation_status}."

    @staticmethod
    def _condition(direction: str, invalidation: LiquidityLevel) -> str:
        label = NarrativeLedgerService._level_text(invalidation)
        if direction == "delivery_up":
            return f"Two consecutive M15 closes below {label} invalidate bullish delivery."
        return f"Two consecutive M15 closes above {label} invalidate bearish delivery."

    @staticmethod
    def _next_decision(direction: str) -> str:
        if direction == "delivery_up":
            return (
                "Reset DOL identification; suspend buyside delivery and identify a fresh "
                "sellside objective below the invalidation boundary."
            )
        return (
            "Reset DOL identification; suspend sellside delivery and identify a fresh "
            "buyside objective above the invalidation boundary."
        )

    @staticmethod
    def _close_breached(ledger: NarrativeLedger, close: Decimal) -> bool:
        if ledger.delivery_direction == "delivery_up":
            return close < ledger.invalidation_price
        return close > ledger.invalidation_price

    @staticmethod
    def _wick_breached(ledger: NarrativeLedger, candle: MarketSnapshot) -> bool:
        if ledger.delivery_direction == "delivery_up":
            return candle.low < ledger.invalidation_price <= candle.close
        return candle.high > ledger.invalidation_price >= candle.close

    @staticmethod
    def _level_text(level: LiquidityLevel) -> str:
        return f"{level.level_type} {level.liquidity_side} at {format(level.price.normalize(), 'f')}"

    @staticmethod
    def _utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
