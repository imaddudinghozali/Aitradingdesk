from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.delivery_quality_assessment import DeliveryQualityAssessment
from app.models.dol_assessment import DolAssessment
from app.models.liquidity_level import LiquidityLevel
from app.models.market_snapshot import MarketSnapshot
from app.models.mmxm_assessment import MmxmAssessment
from app.models.narrative_ledger import NarrativeLedger
from app.models.sweep_event import SweepEvent


class DeliveryQualityService:
    TERMINAL_LEDGER_STATUSES = {"failed", "reversed", "redistributed"}

    @staticmethod
    def evaluate(
        db: Session,
        symbol: str,
        timeframe: str = "M15",
        as_of_utc: datetime | None = None,
        valid_retracement: bool = False,
        poi_reference: str | None = None,
    ) -> DeliveryQualityAssessment:
        dol = db.query(DolAssessment).filter(DolAssessment.symbol == symbol).first()
        if dol is None:
            raise ValueError("DOL assessment not found. Evaluate DOL before delivery quality.")
        ledger = (
            db.query(NarrativeLedger)
            .filter(NarrativeLedger.symbol == symbol)
            .order_by(NarrativeLedger.created_at.desc(), NarrativeLedger.id.desc())
            .first()
        )
        if ledger is None:
            raise ValueError(
                "Narrative ledger not found. Generate a complete narrative before delivery quality."
            )
        mmxm = db.query(MmxmAssessment).filter(MmxmAssessment.symbol == symbol).first()
        sweep = db.get(SweepEvent, dol.source_sweep_event_id) if dol.source_sweep_event_id else None
        target = db.get(LiquidityLevel, ledger.target_level_id)
        cutoff = DeliveryQualityService._cutoff(db, symbol, timeframe, ledger, as_of_utc)
        candles = DeliveryQualityService._candles(db, symbol, timeframe, ledger, cutoff)
        assessment = (
            db.query(DeliveryQualityAssessment)
            .filter(DeliveryQualityAssessment.symbol == symbol)
            .first()
        )
        confirmed_retracement = valid_retracement or bool(
            assessment and assessment.valid_retracement
        )
        stored_poi_reference = poi_reference or (assessment.poi_reference if assessment else None)

        clean = DeliveryQualityService._clean_displacement(candles, ledger.delivery_direction)
        overlap = DeliveryQualityService._overlap_heavy(candles)
        failed = DeliveryQualityService._failed_continuation(candles, ledger.delivery_direction)
        target_reached = DeliveryQualityService._target_reached(
            candles, target, ledger.delivery_direction
        )
        terminal = (
            ledger.continuation_status in DeliveryQualityService.TERMINAL_LEDGER_STATUSES
            or ledger.reset_required
            or (target_reached and (failed or overlap))
        )
        engineered = (
            not terminal
            and len(candles) >= 2
            and sweep is not None
            and sweep.sweep_status == "Manipulation Sweep"
            and sweep.displacement_detected
            and (failed or overlap or not clean)
        )
        tempo, quality, status, reason, impact = DeliveryQualityService._classification(
            candles,
            clean,
            overlap,
            failed,
            terminal,
            engineered,
            target_reached,
            confirmed_retracement,
        )
        assessment = assessment or DeliveryQualityAssessment(
                symbol=symbol,
                dol_assessment_id=dol.id,
                narrative_ledger_id=ledger.id,
                timeframe=timeframe,
                delivery_tempo=tempo,
                expansion_quality=quality,
                expansion_status=status,
                status_reason=reason,
                execution_impact=impact,
                as_of_utc=cutoff,
            )
        assessment.dol_assessment_id = dol.id
        assessment.narrative_ledger_id = ledger.id
        assessment.mmxm_assessment_id = mmxm.id if mmxm else None
        assessment.source_sweep_event_id = sweep.id if sweep else None
        assessment.timeframe = timeframe
        assessment.valid_retracement = confirmed_retracement
        assessment.poi_reference = stored_poi_reference
        assessment.delivery_tempo = tempo
        assessment.expansion_quality = quality
        assessment.expansion_status = status
        assessment.clean_displacement = clean
        assessment.overlap_heavy = overlap
        assessment.failed_continuation = failed
        assessment.terminal_expansion = terminal
        assessment.engineered_expansion = engineered
        assessment.target_reached = target_reached
        assessment.status_reason = reason
        assessment.execution_impact = impact
        assessment.as_of_utc = cutoff
        DeliveryQualityService._apply_narrative_failure(
            db, dol, ledger, terminal or overlap, reason, cutoff
        )
        if assessment.id is None:
            db.add(assessment)
        db.commit()
        db.refresh(assessment)
        return assessment

    @staticmethod
    def get_current(db: Session, symbol: str) -> DeliveryQualityAssessment | None:
        return (
            db.query(DeliveryQualityAssessment)
            .filter(DeliveryQualityAssessment.symbol == symbol)
            .first()
        )

    @staticmethod
    def display_quality(assessment: DeliveryQualityAssessment | None) -> str:
        if assessment is None:
            return "Waiting - Delivery Quality assessment has not been generated."
        return f"{assessment.expansion_quality}: {assessment.status_reason}"

    @staticmethod
    def _cutoff(
        db: Session,
        symbol: str,
        timeframe: str,
        ledger: NarrativeLedger,
        as_of_utc: datetime | None,
    ) -> datetime:
        if as_of_utc is not None:
            return DeliveryQualityService._utc(as_of_utc)
        latest = (
            db.query(MarketSnapshot)
            .filter(MarketSnapshot.symbol == symbol, MarketSnapshot.timeframe == timeframe)
            .order_by(MarketSnapshot.timestamp_utc.desc(), MarketSnapshot.id.desc())
            .first()
        )
        return DeliveryQualityService._utc(latest.timestamp_utc if latest else ledger.as_of_utc)

    @staticmethod
    def _candles(
        db: Session,
        symbol: str,
        timeframe: str,
        ledger: NarrativeLedger,
        cutoff: datetime,
    ) -> list[MarketSnapshot]:
        activated = DeliveryQualityService._utc(ledger.activated_at_utc)
        return [
            candle
            for candle in (
                db.query(MarketSnapshot)
                .filter(MarketSnapshot.symbol == symbol, MarketSnapshot.timeframe == timeframe)
                .order_by(MarketSnapshot.timestamp_utc.asc(), MarketSnapshot.id.asc())
                .all()
            )
            if activated <= DeliveryQualityService._utc(candle.timestamp_utc) <= cutoff
        ][-4:]

    @staticmethod
    def _clean_displacement(candles: list[MarketSnapshot], direction: str) -> bool:
        if len(candles) < 2:
            return False
        previous, latest = candles[-2:]
        strong = all(DeliveryQualityService._body_ratio(candle) >= Decimal("0.55") for candle in (previous, latest))
        if direction == "delivery_up":
            return strong and previous.close > previous.open and latest.close > previous.high
        if direction == "delivery_down":
            return strong and previous.close < previous.open and latest.close < previous.low
        return False

    @staticmethod
    def _overlap_heavy(candles: list[MarketSnapshot]) -> bool:
        if len(candles) < 2:
            return False
        left, right = candles[-2:]
        intersection = min(left.high, right.high) - max(left.low, right.low)
        smaller_range = min(left.high - left.low, right.high - right.low)
        return smaller_range > 0 and intersection > 0 and intersection / smaller_range >= Decimal("0.60")

    @staticmethod
    def _failed_continuation(candles: list[MarketSnapshot], direction: str) -> bool:
        if len(candles) < 2:
            return False
        previous, latest = candles[-2:]
        if direction == "delivery_up":
            return previous.close > previous.open and latest.close < previous.open
        if direction == "delivery_down":
            return previous.close < previous.open and latest.close > previous.open
        return False

    @staticmethod
    def _target_reached(
        candles: list[MarketSnapshot],
        target: LiquidityLevel | None,
        direction: str,
    ) -> bool:
        if target is None or not candles:
            return False
        if direction == "delivery_up":
            return any(candle.high >= target.price for candle in candles)
        if direction == "delivery_down":
            return any(candle.low <= target.price for candle in candles)
        return False

    @staticmethod
    def _classification(
        candles: list[MarketSnapshot],
        clean: bool,
        overlap: bool,
        failed: bool,
        terminal: bool,
        engineered: bool,
        target_reached: bool,
        valid_retracement: bool,
    ) -> tuple[str, str, str, str, str]:
        if terminal:
            reason = (
                "Expansion is terminal: objective interaction or narrative failure is followed "
                "by exhaustion/failure; continuation cannot be trusted."
            )
            return "exhausted expansion", "terminal expansion", "invalidated", reason, f"No Trade - {reason}"
        if engineered:
            reason = (
                "Manipulation displacement lacks clean follow-through and reads as an engineered "
                "move rather than confirmed continuation."
            )
            return "compressed delivery", "engineered expansion", "invalidated", reason, f"No Trade - {reason}"
        if clean and not valid_retracement:
            reason = (
                "Clean displacement is present without confirmed retracement to a POI; "
                "the drive remains compressed delivery until OB/FVG/Breaker context is supplied."
            )
            return "compressed delivery", "weak expansion", "waiting", reason, f"No Trade - {reason}"
        if clean:
            reason = "Two aligned M15 bodies displaced cleanly beyond the prior candle range."
            return (
                "aggressive delivery",
                "healthy expansion",
                "valid",
                reason,
                "Expansion context is valid; No Trade until POI and CISD/MSS confirmation exist.",
            )
        if failed:
            reason = "Directional expansion failed to continue and closed through the prior drive."
            return "exhausted expansion", "weak expansion", "waiting", reason, f"No Trade - {reason}"
        if overlap:
            reason = "Recent M15 ranges overlap heavily; delivery is inefficient and unresolved."
            return "slow delivery", "weak expansion", "waiting", reason, f"No Trade - {reason}"
        if len(candles) < 2:
            reason = "At least two M15 delivery candles are required to validate displacement."
        else:
            reason = "Directional follow-through has not displaced cleanly beyond the prior range."
        if target_reached:
            reason += " Target has been touched but terminal behavior is not confirmed."
        return "delayed expansion", "weak expansion", "waiting", reason, f"No Trade - {reason}"

    @staticmethod
    def _apply_narrative_failure(
        db: Session,
        dol: DolAssessment,
        ledger: NarrativeLedger,
        failed_delivery: bool,
        reason: str,
        cutoff: datetime,
    ) -> None:
        if not failed_delivery or ledger.continuation_status in DeliveryQualityService.TERMINAL_LEDGER_STATUSES:
            return
        ledger.continuation_status = "failed"
        ledger.breach_status = "terminal_expansion"
        ledger.reset_required = True
        ledger.invalidated_at_utc = cutoff
        ledger.status_reason = f"Narrative failed via Delivery Quality: {reason}"
        dol.lifecycle_status = "Shift Pending"
        dol.prior_narrative_resolved = True
        dol.status_reason = (
            "Inefficient or terminal expansion invalidated the active narrative; fresh DOL identification "
            "is required. No Trade."
        )

    @staticmethod
    def _body_ratio(candle: MarketSnapshot) -> Decimal:
        candle_range = candle.high - candle.low
        if candle_range <= 0:
            return Decimal(0)
        return abs(candle.close - candle.open) / candle_range

    @staticmethod
    def _utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
