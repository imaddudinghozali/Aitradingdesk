from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.engines.time_engine import TimeEngine
from app.models.dol_assessment import DolAssessment
from app.models.irl_erl_mapping import IrlErlMapping
from app.models.liquidity_level import LiquidityLevel
from app.models.market_snapshot import MarketSnapshot
from app.models.ssmt_event import SsmtEvent
from app.models.sweep_event import SweepEvent
from app.schemas.ssmt import SsmtEvaluateRequest, SsmtStatus
from app.utils.timezone import to_ny_time, to_utc_time


@dataclass(frozen=True)
class QuarterSwing:
    quarter: str
    start_utc: datetime
    start_ny: datetime
    high: Decimal
    high_at_utc: datetime
    low: Decimal
    low_at_utc: datetime


class SsmtService:
    HTF_LEVEL_TYPES = {
        "PDH", "PDL", "PWH", "PWL", "PMH", "PML", "PYH", "PYL", "NEWS_HIGH", "NEWS_LOW"
    }
    # Minutes per Daye quarter for each candle timeframe (derived from the cycle).
    # H4 -> 6h daily quarters; M5/M15 -> 90-minute micro-quarters.
    _CYCLE_MINUTES = {"H4": 360, "M15": 90, "M5": 90}
    CONFIRMED_SWEEPS = {
        "Valid Sweep",
        "Turtle Soup",
        "Manipulation Sweep",
        "True Breakout / Breakdown",
    }

    @staticmethod
    def evaluate(db: Session, request: SsmtEvaluateRequest) -> SsmtEvent:
        dol = db.query(DolAssessment).filter(DolAssessment.symbol == request.trade_asset).first()
        if dol is None:
            raise ValueError("XAUUSD DOL assessment not found. Evaluate DOL before SSMT.")
        mapping = (
            db.query(IrlErlMapping)
            .filter(IrlErlMapping.symbol == request.trade_asset)
            .first()
        )
        if mapping is None:
            raise ValueError(
                "XAUUSD direction liquidity mapping not found. Evaluate IRL/ERL before SSMT."
            )
        cutoff = SsmtService._cutoff(db, request)
        cycle_minutes = SsmtService._cycle_minutes(request.timeframe)
        cycle_label = SsmtService._cycle_label(cycle_minutes)
        SsmtService._invalidate_active_events(db, request.trade_asset, cutoff)
        xau = SsmtService._quarter_swings(
            db, request.trade_asset, request.timeframe, cutoff, cycle_minutes
        )
        xag = SsmtService._quarter_swings(
            db, request.confirmation_symbol, request.timeframe, cutoff, cycle_minutes
        )
        common_starts = sorted(set(xau).intersection(xag))
        if len(common_starts) < 2:
            return SsmtService._waiting(
                db,
                request,
                cutoff,
                f"Waiting for two paired {cycle_label} from XAUUSD and XAGUSD.",
            )

        first = common_starts[-2]
        second = common_starts[-1]
        xau_first, xau_second = xau[first], xau[second]
        xag_first, xag_second = xag[first], xag[second]
        event = SsmtService._event_for_pair(db, request, xau_first, xau_second)
        if event.ssmt_status == SsmtStatus.MAGNETO_INVALIDATED.value:
            event.as_of_utc = cutoff
            return SsmtService._save(db, event)
        effective_poi = request.poi_touched or event.poi_touched
        poi_reference = request.poi_reference or event.poi_reference
        sequence_valid = SsmtService._sequential(xau_first, xau_second, cycle_minutes)
        direction = SsmtService._cic_direction(xau_first, xau_second, xag_first, xag_second)
        SsmtService._set_swings(event, request, direction, xau_first, xau_second)
        event.quarter_sequence_valid = sequence_valid
        event.cic_detected = direction is not None
        event.direction = direction
        event.poi_touched = effective_poi
        event.poi_reference = poi_reference
        event.xau_relative_state = SsmtService._relative_state(direction)
        event.confirmation_pair_state = SsmtService._confirmation_state(
            direction, xau_first, xau_second, xag_first, xag_second
        )
        event.as_of_utc = cutoff

        if not sequence_valid:
            SsmtService._reject(
                event,
                SsmtStatus.NOISE,
                "invalid_quarter_sequence",
                "SSMT noise: paired swings do not occur in sequential Daye quarters.",
            )
            return SsmtService._save(db, event)
        if direction is None:
            SsmtService._reject(
                event,
                SsmtStatus.NOISE,
                "no_cic",
                "SSMT noise: XAUUSD and XAGUSD do not show a qualifying crack in correlation.",
            )
            return SsmtService._save(db, event)

        expected_side = "BSL" if direction == "bearish" else "SSL"
        swing_time = event.second_swing_at_utc or cutoff
        sweep = SsmtService._source_sweep(db, expected_side, swing_time)
        event.source_sweep_event_id = sweep.id if sweep else None
        event.magneto_level_id = sweep.liquidity_level_id if sweep else None
        event.liquidity_context = SsmtService._liquidity_context(sweep)
        if sweep is None:
            SsmtService._reject(
                event,
                SsmtStatus.NOISE,
                "liquidity_not_swept",
                f"SSMT noise: no confirmed XAUUSD {expected_side} sweep exists before the divergent swing.",
            )
            return SsmtService._save(db, event)
        algorithm_state, algorithm_supported = SsmtService._algorithm_context(mapping, sweep)
        event.algorithm_state = algorithm_state
        event.algorithm_context_status = "supported" if algorithm_supported else "not_supported"
        if not algorithm_supported:
            SsmtService._reject(
                event,
                SsmtStatus.NOISE,
                "algorithm_context_not_supported",
                "SSMT Status: Noise - algorithm context does not support delivery of this divergence.",
            )
            return SsmtService._save(db, event)
        if not effective_poi:
            SsmtService._reject(
                event,
                SsmtStatus.WAITING,
                "waiting_poi",
                "SSMT candidate has CIC and swept liquidity, but POI touch is not confirmed.",
            )
            return SsmtService._save(db, event)

        expected_delivery = "delivery_down" if direction == "bearish" else "delivery_up"
        aligned = (
            dol.lifecycle_status in {"Active", "Shift Confirmed"}
            and dol.delivery_direction == expected_delivery
            and mapping.mapping_status == "aligned"
        )
        event.ssmt_dol_alignment = "aligned" if aligned else "conflict"
        if not aligned:
            SsmtService._reject(
                event,
                SsmtStatus.NOISE,
                "dol_conflict",
                "SSMT noise: divergence direction is not supported by active aligned XAUUSD DOL.",
            )
            return SsmtService._save(db, event)

        if SsmtService._magneto_triggered(db, event, cutoff):
            event.ssmt_status = SsmtStatus.MAGNETO_INVALIDATED.value
            event.magneto_status = "triggered"
            event.ssmt_noise_status = "magneto_invalidated"
            event.reason_if_noise = "SSMT Invalidated via Magneto Effect."
            event.status_reason = (
                "SSMT Invalidated via Magneto Effect: the prior HTF sweep level was breached "
                "after the divergence formed and now represents liquidity."
            )
            return SsmtService._save(db, event)

        event.ssmt_status = (
            SsmtStatus.VALID_BEARISH.value
            if direction == "bearish"
            else SsmtStatus.VALID_BULLISH.value
        )
        event.ssmt_dol_alignment = "aligned"
        event.ssmt_noise_status = "clear"
        event.magneto_status = "clear"
        event.reason_if_noise = None
        event.status_reason = (
            f"Valid {direction} SSMT: CIC, sequential Daye quarters, swept liquidity, "
            f"supported algorithm state ({event.algorithm_state}), POI touch, and "
            "XAUUSD DOL alignment are confirmed. "
            "Trade asset remains XAUUSD and execution still requires later confirmation."
        )
        return SsmtService._save(db, event)

    @staticmethod
    def get_current(db: Session) -> SsmtEvent | None:
        return (
            db.query(SsmtEvent)
            .filter(SsmtEvent.trade_asset == "XAUUSD", SsmtEvent.confirmation_symbol == "XAGUSD")
            .order_by(SsmtEvent.as_of_utc.desc(), SsmtEvent.id.desc())
            .first()
        )

    @staticmethod
    def display_status(event: SsmtEvent | None) -> str:
        if event is None:
            return "Waiting - no SSMT assessment has been generated."
        if event.ssmt_status == SsmtStatus.VALID_BEARISH.value:
            return "VALID BEARISH - XAU relative weakness confirmed by XAG; trade asset XAUUSD only."
        if event.ssmt_status == SsmtStatus.VALID_BULLISH.value:
            return "VALID BULLISH - XAU relative strength confirmed by XAG; trade asset XAUUSD only."
        if event.ssmt_status == SsmtStatus.MAGNETO_INVALIDATED.value:
            return "Invalidated via Magneto Effect - previous SSMT level is now liquidity."
        return f"{event.ssmt_status.title()} - {event.status_reason}"

    @staticmethod
    def _cutoff(db: Session, request: SsmtEvaluateRequest) -> datetime:
        if request.as_of_utc is not None:
            return SsmtService._utc(request.as_of_utc)
        latest = (
            db.query(MarketSnapshot)
            .filter(MarketSnapshot.symbol == request.trade_asset)
            .order_by(MarketSnapshot.timestamp_utc.desc())
            .first()
        )
        if latest is None:
            raise ValueError("No XAUUSD market snapshots found for SSMT evaluation.")
        return SsmtService._utc(latest.timestamp_utc)

    @staticmethod
    def _cycle_minutes(timeframe: str) -> int:
        return SsmtService._CYCLE_MINUTES.get(timeframe.upper(), 360)

    @staticmethod
    def _cycle_label(cycle_minutes: int) -> str:
        if cycle_minutes >= 360:
            return "H4 Daye quarters"
        return "90-minute Daye micro-quarters"

    @staticmethod
    def _quarter_swings(
        db: Session,
        symbol: str,
        timeframe: str,
        cutoff: datetime,
        cycle_minutes: int = 360,
    ) -> dict[datetime, QuarterSwing]:
        snapshots = (
            db.query(MarketSnapshot)
            .filter(MarketSnapshot.symbol == symbol, MarketSnapshot.timeframe == timeframe)
            .order_by(MarketSnapshot.timestamp_utc.asc())
            .all()
        )
        grouped: dict[datetime, list[MarketSnapshot]] = {}
        for snapshot in snapshots:
            if SsmtService._utc(snapshot.timestamp_utc) > cutoff:
                continue
            start_ny = SsmtService._quarter_start_ny(snapshot.timestamp_utc, cycle_minutes)
            start_utc = to_utc_time(start_ny)
            grouped.setdefault(start_utc, []).append(snapshot)
        result: dict[datetime, QuarterSwing] = {}
        for start_utc, candles in grouped.items():
            high_candle = max(candles, key=lambda candle: candle.high)
            low_candle = min(candles, key=lambda candle: candle.low)
            start_ny = to_ny_time(start_utc)
            result[start_utc] = QuarterSwing(
                quarter=SsmtService._quarter_label(start_ny, cycle_minutes),
                start_utc=start_utc,
                start_ny=start_ny,
                high=high_candle.high,
                high_at_utc=high_candle.timestamp_utc,
                low=low_candle.low,
                low_at_utc=low_candle.timestamp_utc,
            )
        return result

    @staticmethod
    def _quarter_label(start_ny: datetime, cycle_minutes: int) -> str:
        if cycle_minutes >= 360:
            return TimeEngine.get_daily_quarter(start_ny).value
        return TimeEngine.get_micro_quarter(start_ny)

    @staticmethod
    def _daily_quarter_start_ny(dt_ny: datetime) -> datetime:
        start_hours = {"Q1": 18, "Q2": 0, "Q3": 6, "Q4": 12}
        return dt_ny.replace(
            hour=start_hours[TimeEngine.get_daily_quarter(dt_ny).value],
            minute=0,
            second=0,
            microsecond=0,
        )

    @staticmethod
    def _quarter_start_ny(timestamp_utc: datetime, cycle_minutes: int = 360) -> datetime:
        dt_ny = to_ny_time(SsmtService._utc(timestamp_utc))
        daily_start = SsmtService._daily_quarter_start_ny(dt_ny)
        if cycle_minutes >= 360:
            return daily_start
        # Sub-quarter cycle: step inside the 6h daily quarter by cycle_minutes,
        # anchored to the daily quarter start so 90-min buckets align to Q*.1-Q*.4.
        elapsed = int((dt_ny - daily_start).total_seconds() // 60)
        bucket = (elapsed // cycle_minutes) * cycle_minutes
        return daily_start + timedelta(minutes=bucket)

    @staticmethod
    def _sequential(
        first: QuarterSwing, second: QuarterSwing, cycle_minutes: int = 360
    ) -> bool:
        first_wall = first.start_ny.replace(tzinfo=None)
        second_wall = second.start_ny.replace(tzinfo=None)
        return second_wall - first_wall == timedelta(minutes=cycle_minutes)

    @staticmethod
    def _cic_direction(
        xau_first: QuarterSwing,
        xau_second: QuarterSwing,
        xag_first: QuarterSwing,
        xag_second: QuarterSwing,
    ) -> str | None:
        bearish = xau_second.high < xau_first.high and xag_second.high > xag_first.high
        bullish = xau_second.low > xau_first.low and xag_second.low < xag_first.low
        if bearish == bullish:
            return None
        return "bearish" if bearish else "bullish"

    @staticmethod
    def _event_for_pair(
        db: Session,
        request: SsmtEvaluateRequest,
        first: QuarterSwing,
        second: QuarterSwing,
    ) -> SsmtEvent:
        event = (
            db.query(SsmtEvent)
            .filter(
                SsmtEvent.trade_asset == request.trade_asset,
                SsmtEvent.confirmation_symbol == request.confirmation_symbol,
                SsmtEvent.timeframe == request.timeframe,
                SsmtEvent.first_quarter_start_utc == first.start_utc,
                SsmtEvent.second_quarter_start_utc == second.start_utc,
            )
            .first()
        )
        return event or SsmtEvent(
            trade_asset=request.trade_asset,
            confirmation_symbol=request.confirmation_symbol,
            timeframe=request.timeframe,
            ssmt_status=SsmtStatus.WAITING.value,
            ssmt_dol_alignment="waiting",
            ssmt_noise_status="waiting",
            xau_relative_state="neutral",
            confirmation_pair_state="Waiting for paired swings.",
            liquidity_context="Waiting for a confirmed XAUUSD liquidity sweep.",
            status_reason="Waiting for SSMT evaluation.",
            magneto_status="clear",
            as_of_utc=second.start_utc,
        )

    @staticmethod
    def _set_swings(
        event: SsmtEvent,
        request: SsmtEvaluateRequest,
        direction: str | None,
        xau_first: QuarterSwing,
        xau_second: QuarterSwing,
    ) -> None:
        event.trade_asset = request.trade_asset
        event.confirmation_symbol = request.confirmation_symbol
        event.timeframe = request.timeframe
        event.first_quarter = xau_first.quarter
        event.second_quarter = xau_second.quarter
        event.first_quarter_start_utc = xau_first.start_utc
        event.second_quarter_start_utc = xau_second.start_utc
        if direction == "bullish":
            event.second_swing_at_utc = xau_second.low_at_utc
        else:
            event.second_swing_at_utc = xau_second.high_at_utc

    @staticmethod
    def _assign_directional_swings(
        event: SsmtEvent,
        direction: str | None,
        xau_first: QuarterSwing,
        xau_second: QuarterSwing,
        xag_first: QuarterSwing,
        xag_second: QuarterSwing,
    ) -> None:
        if direction == "bullish":
            event.xau_first_swing = xau_first.low
            event.xau_second_swing = xau_second.low
            event.xag_first_swing = xag_first.low
            event.xag_second_swing = xag_second.low
            event.second_swing_at_utc = xau_second.low_at_utc
        else:
            event.xau_first_swing = xau_first.high
            event.xau_second_swing = xau_second.high
            event.xag_first_swing = xag_first.high
            event.xag_second_swing = xag_second.high
            event.second_swing_at_utc = xau_second.high_at_utc

    @staticmethod
    def _source_sweep(db: Session, expected_side: str, cutoff: datetime) -> SweepEvent | None:
        events = (
            db.query(SweepEvent)
            .filter(SweepEvent.symbol == "XAUUSD", SweepEvent.liquidity_side == expected_side)
            .order_by(SweepEvent.detected_at_utc.desc(), SweepEvent.id.desc())
            .all()
        )
        return next(
            (
                event
                for event in events
                if SsmtService._utc(event.detected_at_utc) <= SsmtService._utc(cutoff)
                and event.sweep_status in SsmtService.CONFIRMED_SWEEPS
                and event.displacement_detected
                and event.relevant_timing
            ),
            None,
        )

    @staticmethod
    def _liquidity_context(sweep: SweepEvent | None) -> str:
        if sweep is None:
            return "No confirmed liquidity sweep found before SSMT formation."
        return f"{sweep.level_type} {sweep.liquidity_side} swept before SSMT formation."

    @staticmethod
    def _algorithm_context(
        mapping: IrlErlMapping,
        sweep: SweepEvent | None,
    ) -> tuple[str, bool]:
        if sweep is None:
            return "waiting", False
        supported_flows = {
            "liquidity -> liquidity": "liquidity -> liquidity",
            "ERL -> IRL": "liquidity -> liquidity",
            "IRL -> ERL": "liquidity -> liquidity",
            "ERL -> IRL -> ERL": "liquidity -> liquidity",
        }
        state = supported_flows.get(mapping.direction_flow)
        if state is None:
            return "no man's land / unresolved algorithm", False
        return state, mapping.mapping_status == "aligned"

    @staticmethod
    def _relative_state(direction: str | None) -> str:
        if direction == "bearish":
            return "relative_weakness"
        if direction == "bullish":
            return "relative_strength"
        return "neutral"

    @staticmethod
    def _confirmation_state(
        direction: str | None,
        xau_first: QuarterSwing,
        xau_second: QuarterSwing,
        xag_first: QuarterSwing,
        xag_second: QuarterSwing,
    ) -> str:
        if direction == "bearish":
            return (
                f"XAU Lower High ({xau_first.high} -> {xau_second.high}); "
                f"XAG Higher High ({xag_first.high} -> {xag_second.high})."
            )
        if direction == "bullish":
            return (
                f"XAU Higher Low ({xau_first.low} -> {xau_second.low}); "
                f"XAG Lower Low ({xag_first.low} -> {xag_second.low})."
            )
        return "No qualifying inverse swing sequence between XAUUSD and XAGUSD."

    @staticmethod
    def _magneto_triggered(db: Session, event: SsmtEvent, cutoff: datetime) -> bool:
        if event.magneto_level_id is None or event.second_swing_at_utc is None:
            return False
        level = db.get(LiquidityLevel, event.magneto_level_id)
        if level is None or level.level_type not in SsmtService.HTF_LEVEL_TYPES:
            return False
        candles = (
            db.query(MarketSnapshot)
            .filter(MarketSnapshot.symbol == "XAUUSD", MarketSnapshot.timeframe == event.timeframe)
            .order_by(MarketSnapshot.timestamp_utc.asc())
            .all()
        )
        for candle in candles:
            timestamp = SsmtService._utc(candle.timestamp_utc)
            if timestamp <= SsmtService._utc(event.second_swing_at_utc) or timestamp > cutoff:
                continue
            if event.direction == "bearish" and candle.close > level.price:
                return True
            if event.direction == "bullish" and candle.close < level.price:
                return True
        return False

    @staticmethod
    def _invalidate_active_events(db: Session, trade_asset: str, cutoff: datetime) -> None:
        events = (
            db.query(SsmtEvent)
            .filter(
                SsmtEvent.trade_asset == trade_asset,
                SsmtEvent.ssmt_status.in_(
                    [SsmtStatus.VALID_BULLISH.value, SsmtStatus.VALID_BEARISH.value]
                ),
            )
            .all()
        )
        changed = False
        for event in events:
            if SsmtService._magneto_triggered(db, event, cutoff):
                event.ssmt_status = SsmtStatus.MAGNETO_INVALIDATED.value
                event.magneto_status = "triggered"
                event.ssmt_noise_status = "magneto_invalidated"
                event.reason_if_noise = "SSMT Invalidated via Magneto Effect."
                event.status_reason = (
                    "SSMT Invalidated via Magneto Effect: the HTF level underlying "
                    "the divergence has been breached after formation."
                )
                event.as_of_utc = cutoff
                changed = True
        if changed:
            db.commit()

    @staticmethod
    def _reject(event: SsmtEvent, status: SsmtStatus, noise: str, reason: str) -> None:
        event.ssmt_status = status.value
        event.ssmt_dol_alignment = event.ssmt_dol_alignment or "waiting"
        event.ssmt_noise_status = noise
        event.magneto_status = "clear"
        event.reason_if_noise = reason
        event.status_reason = reason

    @staticmethod
    def _waiting(
        db: Session,
        request: SsmtEvaluateRequest,
        cutoff: datetime,
        reason: str,
    ) -> SsmtEvent:
        event = (
            db.query(SsmtEvent)
            .filter(
                SsmtEvent.trade_asset == request.trade_asset,
                SsmtEvent.confirmation_symbol == request.confirmation_symbol,
                SsmtEvent.timeframe == request.timeframe,
                SsmtEvent.first_quarter_start_utc.is_(None),
            )
            .first()
        ) or SsmtEvent(
            trade_asset=request.trade_asset,
            confirmation_symbol=request.confirmation_symbol,
            timeframe=request.timeframe,
            magneto_status="clear",
            algorithm_state="waiting",
            algorithm_context_status="waiting",
            as_of_utc=cutoff,
        )
        event.ssmt_status = SsmtStatus.WAITING.value
        event.cic_detected = False
        event.quarter_sequence_valid = False
        event.poi_touched = request.poi_touched
        event.poi_reference = request.poi_reference
        event.algorithm_state = "waiting"
        event.algorithm_context_status = "waiting"
        event.ssmt_dol_alignment = "waiting"
        event.ssmt_noise_status = "insufficient_paired_quarters"
        event.xau_relative_state = "neutral"
        event.confirmation_pair_state = (
            f"Waiting for paired {SsmtService._cycle_label(SsmtService._cycle_minutes(request.timeframe))}."
        )
        event.liquidity_context = "Waiting for qualifying liquidity context."
        event.reason_if_noise = reason
        event.status_reason = reason
        event.as_of_utc = cutoff
        return SsmtService._save(db, event)

    @staticmethod
    def _save(db: Session, event: SsmtEvent) -> SsmtEvent:
        if event.direction is not None and event.first_quarter_start_utc is not None:
            cycle_minutes = SsmtService._cycle_minutes(event.timeframe)
            xau = SsmtService._quarter_swings(
                db, event.trade_asset, event.timeframe, event.as_of_utc, cycle_minutes
            )
            xag = SsmtService._quarter_swings(
                db, event.confirmation_symbol, event.timeframe, event.as_of_utc, cycle_minutes
            )
            first = xau.get(event.first_quarter_start_utc)
            second = xau.get(event.second_quarter_start_utc)
            xag_first = xag.get(event.first_quarter_start_utc)
            xag_second = xag.get(event.second_quarter_start_utc)
            if first and second and xag_first and xag_second:
                SsmtService._assign_directional_swings(
                    event, event.direction, first, second, xag_first, xag_second
                )
        if event.id is None:
            db.add(event)
        db.commit()
        db.refresh(event)
        return event

    @staticmethod
    def _utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
