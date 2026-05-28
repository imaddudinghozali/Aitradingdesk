from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.dol_assessment import DolAssessment
from app.models.liquidity_level import LiquidityLevel
from app.models.market_snapshot import MarketSnapshot
from app.models.mmxm_assessment import MmxmAssessment
from app.models.narrative_ledger import NarrativeLedger
from app.models.sweep_event import SweepEvent


class MmxmService:
    REVERSAL_SWEEPS = {"Valid Sweep", "Turtle Soup", "Manipulation Sweep"}

    @staticmethod
    def evaluate(
        db: Session,
        symbol: str,
        timeframe: str = "H4",
        as_of_utc: datetime | None = None,
    ) -> MmxmAssessment:
        dol = db.query(DolAssessment).filter(DolAssessment.symbol == symbol).first()
        if dol is None:
            raise ValueError("DOL assessment not found. Evaluate DOL before MMXM.")
        ledger = (
            db.query(NarrativeLedger)
            .filter(NarrativeLedger.symbol == symbol)
            .order_by(NarrativeLedger.created_at.desc(), NarrativeLedger.id.desc())
            .first()
        )
        if ledger is None:
            raise ValueError("Narrative ledger not found. Generate a complete narrative before MMXM.")
        market = MmxmService._latest_market(db, symbol, as_of_utc)
        sweep = (
            db.get(SweepEvent, dol.source_sweep_event_id)
            if dol.source_sweep_event_id
            else None
        )
        assessment = (
            db.query(MmxmAssessment).filter(MmxmAssessment.symbol == symbol).first()
            or MmxmAssessment(symbol=symbol, dol_assessment_id=dol.id, narrative_ledger_id=ledger.id)
        )
        active_model, model_status, candle_delivery = MmxmService._model(dol, ledger)
        range_low, range_high, position, quadrant = MmxmService._quadrant(
            db, symbol, timeframe, market
        )
        phase = MmxmService._phase(active_model, quadrant, model_status)
        target = db.get(LiquidityLevel, ledger.target_level_id)
        delivery_leg, timing_probability, timing_conflict = MmxmService._formation_context(
            active_model, quadrant, market.day_of_week, target
        )
        judas_status, judas_reason = MmxmService._judas(dol, sweep, ledger)

        assessment.dol_assessment_id = dol.id
        assessment.narrative_ledger_id = ledger.id
        assessment.source_sweep_event_id = sweep.id if sweep else None
        assessment.active_model = active_model
        assessment.model_status = model_status
        assessment.candle_delivery = candle_delivery
        assessment.htf_delivery_leg = delivery_leg
        assessment.timing_probability = timing_probability
        assessment.timing_conflict = timing_conflict
        assessment.mmxm_phase = phase
        assessment.quadrant = quadrant
        assessment.quadrant_position = position
        assessment.range_low = range_low
        assessment.range_high = range_high
        assessment.current_price = market.close
        assessment.terminus = ledger.invalidation_level
        assessment.hrlr_status = MmxmService._hrlr(sweep, dol)
        assessment.lrlr_status = MmxmService._lrlr(
            db, symbol, timeframe, market, dol.delivery_direction, ledger
        )
        assessment.opr_status = MmxmService._opr(db, symbol, timeframe, market, ledger)
        assessment.judas_status = judas_status
        assessment.judas_reason = judas_reason
        assessment.nine_am_context = MmxmService._nine_am(sweep)
        assessment.status_reason = MmxmService._reason(
            active_model, model_status, phase, ledger
        )
        assessment.as_of_utc = market.timestamp_utc
        if assessment.id is None:
            db.add(assessment)
        db.commit()
        db.refresh(assessment)
        return assessment

    @staticmethod
    def get_current(db: Session, symbol: str) -> MmxmAssessment | None:
        return db.query(MmxmAssessment).filter(MmxmAssessment.symbol == symbol).first()

    @staticmethod
    def display_model(assessment: MmxmAssessment | None) -> str:
        if assessment is None:
            return "Waiting - MMXM assessment has not been generated."
        return f"{assessment.active_model} - {assessment.mmxm_phase} ({assessment.model_status})."

    @staticmethod
    def display_judas(assessment: MmxmAssessment | None) -> str:
        if assessment is None:
            return "Waiting - Judas assessment has not been generated."
        return f"{assessment.judas_status}: {assessment.judas_reason}"

    @staticmethod
    def _latest_market(
        db: Session, symbol: str, as_of_utc: datetime | None
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
        cutoff = MmxmService._utc(as_of_utc)
        market = next(
            (
                snapshot
                for snapshot in snapshots
                if MmxmService._utc(snapshot.timestamp_utc) <= cutoff
            ),
            None,
        )
        if market is None:
            raise ValueError("No market snapshots exist at or before as_of_utc")
        return market

    @staticmethod
    def _model(dol: DolAssessment, ledger: NarrativeLedger) -> tuple[str, str, str]:
        if ledger.continuation_status in {"failed", "reversed", "redistributed"} or ledger.reset_required:
            return "Neutral", "invalidated", "Undetermined"
        if dol.lifecycle_status not in {"Active", "Shift Confirmed"}:
            return "Neutral", "waiting_dol", "Undetermined"
        if dol.delivery_direction == "delivery_up":
            return "MMBM", "context_confirmed", "OLHC"
        if dol.delivery_direction == "delivery_down":
            return "MMSM", "context_confirmed", "OHLC"
        return "Neutral", "waiting_direction", "Undetermined"

    @staticmethod
    def _quadrant(
        db: Session,
        symbol: str,
        timeframe: str,
        market: MarketSnapshot,
    ) -> tuple[Decimal | None, Decimal | None, Decimal | None, str]:
        cutoff = MmxmService._utc(market.timestamp_utc)
        candles = [
            candle
            for candle in (
                db.query(MarketSnapshot)
                .filter(MarketSnapshot.symbol == symbol, MarketSnapshot.timeframe == timeframe)
                .order_by(MarketSnapshot.timestamp_utc.desc())
                .limit(20)
                .all()
            )
            if MmxmService._utc(candle.timestamp_utc) <= cutoff
        ]
        if len(candles) < 2:
            return None, None, None, "waiting_range"
        low = min(candle.low for candle in candles)
        high = max(candle.high for candle in candles)
        spread = high - low
        if spread <= 0:
            return low, high, None, "waiting_range"
        position = (market.close - low) / spread
        if position <= Decimal("0.25"):
            quadrant = "0-0.25"
        elif position <= Decimal("0.50"):
            quadrant = "0.25-0.50"
        elif position <= Decimal("0.75"):
            quadrant = "0.50-0.75"
        else:
            quadrant = "0.75-1.00"
        return low, high, position, quadrant

    @staticmethod
    def _phase(active_model: str, quadrant: str, status: str) -> str:
        if status == "invalidated":
            return "Smart Money Reversal pending - prior narrative failed"
        if quadrant == "waiting_range":
            return "Waiting - insufficient H4 range for swing grading"
        phases = {
            "MMBM": {
                "0-0.25": "Smart Money Reversal / Accumulation",
                "0.25-0.50": "Re-accumulation",
                "0.50-0.75": "Expansion toward liquidity objective",
                "0.75-1.00": "Distribution near buyside objective",
            },
            "MMSM": {
                "0-0.25": "Distribution near sellside objective",
                "0.25-0.50": "Expansion toward liquidity objective",
                "0.50-0.75": "Re-distribution",
                "0.75-1.00": "Smart Money Reversal / Distribution",
            },
        }
        return phases.get(active_model, {}).get(quadrant, "Original Consolidation / Waiting")

    @staticmethod
    def _formation_context(
        active_model: str,
        quadrant: str,
        day_of_week: str,
        target: LiquidityLevel | None,
    ) -> tuple[str, str, str]:
        day_groups = {
            "Monday": "early week",
            "Tuesday": "early week",
            "Wednesday": "mid week",
            "Thursday": "late week",
            "Friday": "late week",
        }
        probability = day_groups.get(day_of_week, "outside weekly formation window")
        if active_model == "MMBM":
            if quadrant == "0-0.25":
                leg = "Open -> Low manipulation leg; await Low -> High expansion validation."
            elif quadrant == "waiting_range":
                leg = "OLHC leg waiting for sufficient H4 range evidence."
            else:
                leg = "Low -> High expansion leg toward buyside liquidity."
            conflict = (
                "Timing conflict - late-week buyside formation lacks an external HTF target."
                if day_of_week == "Friday"
                and (target is None or target.level_type not in {"PWH", "PMH", "PYH"})
                else "No day-of-week timing conflict identified for current bullish delivery."
            )
            return leg, probability, conflict
        if active_model == "MMSM":
            if quadrant == "0.75-1.00":
                leg = "Open -> High manipulation leg; await High -> Low expansion validation."
            elif quadrant == "waiting_range":
                leg = "OHLC leg waiting for sufficient H4 range evidence."
            else:
                leg = "High -> Low expansion leg toward sellside liquidity."
            conflict = (
                "Timing conflict - late-week sellside formation lacks an external HTF target."
                if day_of_week == "Friday"
                and (target is None or target.level_type not in {"PWL", "PML", "PYL"})
                else "No day-of-week timing conflict identified for current bearish delivery."
            )
            return leg, probability, conflict
        return (
            "HTF delivery leg is undetermined until the active model is valid.",
            probability,
            "Timing conflict cannot be resolved until DOL/model context is valid.",
        )

    @staticmethod
    def _judas(
        dol: DolAssessment,
        sweep: SweepEvent | None,
        ledger: NarrativeLedger,
    ) -> tuple[str, str]:
        if ledger.continuation_status in {"failed", "reversed"}:
            return "invalidated", "Narrative failure invalidates prior Judas interpretation."
        if sweep is None:
            return "not_detected", "No sweep linked to the active DOL."
        if not sweep.relevant_timing or not sweep.displacement_detected:
            return "potential", "Liquidity interaction exists without confirmed timed displacement."
        expected = MmxmService._direction_from_sweep(sweep)
        aligned = (
            expected == dol.delivery_direction
            and sweep.narrative_alignment == "aligned"
        )
        if sweep.sweep_status == "Manipulation Sweep" and aligned:
            return (
                "valid",
                f"Engineered {sweep.level_type} sweep failed to continue and displaced toward active DOL.",
            )
        if sweep.sweep_status in MmxmService.REVERSAL_SWEEPS and aligned:
            return (
                "potential",
                f"{sweep.sweep_status} aligns with DOL, but explicit manipulation classification is pending.",
            )
        return "not_valid", "Sweep direction is not aligned with current DOL delivery."

    @staticmethod
    def _direction_from_sweep(sweep: SweepEvent) -> str:
        reversal = sweep.sweep_status in MmxmService.REVERSAL_SWEEPS
        if sweep.liquidity_side == "BSL":
            return "delivery_down" if reversal else "delivery_up"
        return "delivery_up" if reversal else "delivery_down"

    @staticmethod
    def _hrlr(sweep: SweepEvent | None, dol: DolAssessment) -> str:
        if sweep is None:
            return "Waiting - no liquidity run is linked to the current DOL."
        if sweep.sweep_status == "True Breakout / Breakdown":
            return "True expansion - liquidity run continued through the level, not HRLR manipulation."
        if sweep.sweep_status in MmxmService.REVERSAL_SWEEPS:
            return (
                f"Taken - {sweep.level_type} {sweep.liquidity_side} was run before "
                f"{dol.delivery_direction} delivery."
            )
        return "Waiting - interaction is not confirmed as a valid liquidity run."

    @staticmethod
    def _lrlr(
        db: Session,
        symbol: str,
        timeframe: str,
        market: MarketSnapshot,
        direction: str | None,
        ledger: NarrativeLedger,
    ) -> str:
        candles = MmxmService._candles_through(db, symbol, timeframe, market)[-3:]
        if len(candles) < 3:
            return f"Waiting - insufficient H4 sequence; objective remains {ledger.target_liquidity}."
        if direction == "delivery_down" and candles[0].high > candles[1].high > candles[2].high:
            return (
                f"Provisional LRLR - three descending H4 highs end at {candles[-1].high}; "
                "requires HRLR sweep before bearish continuation is trusted."
            )
        if direction == "delivery_up" and candles[0].low < candles[1].low < candles[2].low:
            return (
                f"Provisional LRLR - three ascending H4 lows end at {candles[-1].low}; "
                "requires HRLR sweep before bullish continuation is trusted."
            )
        return f"Waiting - no provisional LRLR sequence; objective remains {ledger.target_liquidity}."

    @staticmethod
    def _opr(
        db: Session,
        symbol: str,
        timeframe: str,
        market: MarketSnapshot,
        ledger: NarrativeLedger,
    ) -> str:
        if ledger.continuation_status == "failed":
            return "Invalidated - close-and-hold failure is treated as true breakdown, not OPR bounce."
        candles = MmxmService._candles_through(db, symbol, timeframe, market)
        if len(candles) < 3:
            return "Waiting - insufficient H4 candles to establish an OPR range."
        latest = candles[-1]
        prior = candles[-3:-1]
        range_low = min(candle.low for candle in prior)
        range_high = max(candle.high for candle in prior)
        swept_low = latest.low < range_low
        swept_high = latest.high > range_high
        if len(candles) >= 4:
            sweep_candle = candles[-2]
            basis = candles[-4:-2]
            basis_low = min(candle.low for candle in basis)
            basis_high = max(candle.high for candle in basis)
            if (
                sweep_candle.low < basis_low
                and sweep_candle.close >= basis_low
                and latest.close > sweep_candle.high
                and latest.close > latest.open
            ):
                if ledger.delivery_direction != "delivery_up":
                    return "Waiting - OPR bullish displacement conflicts with the active DOL."
                return (
                    f"Active bounce - range low {basis_low} was taken and reclaimed with "
                    f"bullish displacement; opposite range target is {basis_high}."
                )
            if (
                sweep_candle.high > basis_high
                and sweep_candle.close <= basis_high
                and latest.close < sweep_candle.low
                and latest.close < latest.open
            ):
                if ledger.delivery_direction != "delivery_down":
                    return "Waiting - OPR bearish displacement conflicts with the active DOL."
                return (
                    f"Active rejection - range high {basis_high} was taken and rejected with "
                    f"bearish displacement; opposite range target is {basis_low}."
                )
        if swept_low and latest.close >= range_low:
            return (
                f"Waiting - range low {range_low} was taken and reclaimed; "
                "bullish displacement confirmation is required before OPR bounce."
            )
        if swept_high and latest.close <= range_high:
            return (
                f"Waiting - range high {range_high} was taken and rejected; "
                "bearish displacement confirmation is required before OPR rejection."
            )
        if latest.close < range_low:
            return f"Invalidated - close below range low {range_low} confirms true breakdown."
        if latest.close > range_high:
            return f"Invalidated - close above range high {range_high} confirms true breakout."
        return f"Forming - price remains inside provisional H4 range {range_low} to {range_high}."

    @staticmethod
    def _candles_through(
        db: Session,
        symbol: str,
        timeframe: str,
        market: MarketSnapshot,
    ) -> list[MarketSnapshot]:
        cutoff = MmxmService._utc(market.timestamp_utc)
        return [
            candle
            for candle in (
                db.query(MarketSnapshot)
                .filter(MarketSnapshot.symbol == symbol, MarketSnapshot.timeframe == timeframe)
                .order_by(MarketSnapshot.timestamp_utc.asc(), MarketSnapshot.id.asc())
                .all()
            )
            if MmxmService._utc(candle.timestamp_utc) <= cutoff
        ]

    @staticmethod
    def _nine_am(sweep: SweepEvent | None) -> str:
        if sweep is None:
            return "Not detected - no source sweep."
        if sweep.session_anchor == "09 NY" or sweep.session == "NY AM":
            if sweep.level_type in {"LONDON_HIGH", "LONDON_LOW"}:
                return (
                    f"09 AM context active: {sweep.level_type} liquidity was swept; "
                    "monitor reversal versus continuation profile."
                )
            return (
                "09 AM timing is present, but a London High/Low sweep is not confirmed "
                "for the specific 09 AM model."
            )
        return "Outside 09 AM model context."

    @staticmethod
    def _reason(
        active_model: str,
        model_status: str,
        phase: str,
        ledger: NarrativeLedger,
    ) -> str:
        if model_status == "invalidated":
            return (
                "MMXM is neutral because narrative invalidation requires DOL reset; "
                "the previous model cannot be treated as continuation."
            )
        return (
            f"{active_model} context follows the active DOL with phase {phase}. "
            f"Target remains {ledger.target_liquidity}; MMXM is analytical context only, not an entry signal."
        )

    @staticmethod
    def _utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
