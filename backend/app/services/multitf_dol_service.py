"""Multi-timeframe DOL context (Shadow parent-child model).

Read-only top-down layer that sits ABOVE the operative DOL engine
(`DolService`). It does not pick entries or change the active DOL; it reports,
for Monthly -> Weekly -> Daily -> Intraday (H1/H4), each timeframe's delivery
draw, candle model (OHLC/OLHC), premium/discount position, and whether each
child obeys its parent. A major parent-child conflict yields a No-Trade hint.

The point (Shadow guardrail): the lower timeframe never sets the macro draw; it
only confirms, refines, or — when it breaks structure — flags a conflict.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.dol_assessment import DolAssessment
from app.models.liquidity_level import LiquidityLevel
from app.models.market_snapshot import MarketSnapshot
from app.utils.timezone import to_ny_time

# Candle timeframe used to source each frame's sub-candles.
_DAILY_SOURCE_TF = "D"   # month / week aggregate from daily candles
_INTRADAY_SOURCE_TF = "H1"  # day / intraday aggregate from H1 candles


@dataclass(frozen=True)
class TimeframeFrame:
    timeframe: str
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    model: str          # "OHLC" (high first) | "OLHC" (low first) | "flat"
    position: str       # "premium" | "discount" | "equilibrium"
    draw: str           # "up" | "down" | "neutral"
    candle_count: int


@dataclass(frozen=True)
class TimeframeContext:
    timeframe: str
    frame: TimeframeFrame | None
    parent_status: str  # "root" | "aligned" | "corrective" | "neutral" | "no_data"
    note: str


@dataclass(frozen=True)
class MultiTfDolContext:
    symbol: str
    as_of_utc: datetime
    contexts: list[TimeframeContext]
    conflict_level: str   # "none" | "minor" | "major"
    execution_hint: str
    active_dol: str


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _build_frame(timeframe: str, candles: list[MarketSnapshot]) -> TimeframeFrame | None:
    if not candles:
        return None
    ordered = sorted(candles, key=lambda c: _utc(c.timestamp_utc))
    open_price = ordered[0].open
    close_price = ordered[-1].close
    high_candle = max(ordered, key=lambda c: c.high)
    low_candle = min(ordered, key=lambda c: c.low)
    high = high_candle.high
    low = low_candle.low

    if _utc(high_candle.timestamp_utc) < _utc(low_candle.timestamp_utc):
        model = "OHLC"   # high printed first -> manipulation up, then deliver down
    elif _utc(high_candle.timestamp_utc) > _utc(low_candle.timestamp_utc):
        model = "OLHC"   # low printed first -> manipulation down, then deliver up
    else:
        model = "flat"

    mid = (high + low) / 2
    if close_price > mid:
        position = "premium"
    elif close_price < mid:
        position = "discount"
    else:
        position = "equilibrium"

    if close_price > open_price:
        draw = "up"
    elif close_price < open_price:
        draw = "down"
    else:
        draw = "up" if position == "discount" else "down" if position == "premium" else "neutral"

    return TimeframeFrame(
        timeframe=timeframe,
        open=open_price,
        high=high,
        low=low,
        close=close_price,
        model=model,
        position=position,
        draw=draw,
        candle_count=len(ordered),
    )


class MultiTfDolService:
    @staticmethod
    def evaluate(db: Session, symbol: str, as_of_utc: datetime | None = None) -> MultiTfDolContext:
        symbol = symbol.upper()
        daily_candles = MultiTfDolService._candles(db, symbol, _DAILY_SOURCE_TF, as_of_utc)
        h1_candles = MultiTfDolService._candles(db, symbol, _INTRADAY_SOURCE_TF, as_of_utc)
        if not daily_candles and not h1_candles:
            raise ValueError(f"No market snapshots found for {symbol}")

        cutoff = _utc(
            as_of_utc
            or (daily_candles or h1_candles)[-1].timestamp_utc
        )
        cutoff_ny = to_ny_time(cutoff)

        monthly = _build_frame(
            "Monthly",
            [c for c in daily_candles if MultiTfDolService._same_month(c, cutoff_ny)],
        )
        weekly = _build_frame(
            "Weekly",
            [c for c in daily_candles if MultiTfDolService._same_week(c, cutoff_ny)],
        )
        daily = _build_frame(
            "Daily",
            [c for c in h1_candles if MultiTfDolService._same_day(c, cutoff_ny)],
        )
        intraday = _build_frame(
            "Intraday",
            [c for c in h1_candles if MultiTfDolService._same_daily_quarter(c, cutoff_ny)],
        )

        contexts = [
            MultiTfDolService._context("Monthly", monthly, None, is_root=True),
            MultiTfDolService._context("Weekly", weekly, monthly),
            MultiTfDolService._context("Daily", daily, weekly),
            MultiTfDolService._context("Intraday", intraday, daily),
        ]

        conflict_level = MultiTfDolService._conflict_level(monthly, weekly, daily)
        execution_hint = MultiTfDolService._execution_hint(conflict_level, contexts)
        active_dol = MultiTfDolService._active_dol(db, symbol, daily)

        return MultiTfDolContext(
            symbol=symbol,
            as_of_utc=cutoff,
            contexts=contexts,
            conflict_level=conflict_level,
            execution_hint=execution_hint,
            active_dol=active_dol,
        )

    @staticmethod
    def _candles(
        db: Session, symbol: str, timeframe: str, as_of_utc: datetime | None
    ) -> list[MarketSnapshot]:
        query = db.query(MarketSnapshot).filter(
            MarketSnapshot.symbol == symbol,
            MarketSnapshot.timeframe == timeframe,
        )
        rows = query.order_by(MarketSnapshot.timestamp_utc.asc()).all()
        if as_of_utc is not None:
            cutoff = _utc(as_of_utc)
            rows = [r for r in rows if _utc(r.timestamp_utc) <= cutoff]
        return rows

    @staticmethod
    def _same_month(candle: MarketSnapshot, ref_ny: datetime) -> bool:
        ny = to_ny_time(_utc(candle.timestamp_utc))
        return ny.year == ref_ny.year and ny.month == ref_ny.month

    @staticmethod
    def _same_week(candle: MarketSnapshot, ref_ny: datetime) -> bool:
        ny = to_ny_time(_utc(candle.timestamp_utc))
        return ny.isocalendar()[:2] == ref_ny.isocalendar()[:2]

    @staticmethod
    def _same_day(candle: MarketSnapshot, ref_ny: datetime) -> bool:
        ny = to_ny_time(_utc(candle.timestamp_utc))
        return ny.date() == ref_ny.date()

    @staticmethod
    def _same_daily_quarter(candle: MarketSnapshot, ref_ny: datetime) -> bool:
        ny = to_ny_time(_utc(candle.timestamp_utc))
        if ny.date() != ref_ny.date():
            return False
        return (ny.hour // 6) == (ref_ny.hour // 6)

    @staticmethod
    def _context(
        timeframe: str,
        frame: TimeframeFrame | None,
        parent: TimeframeFrame | None,
        is_root: bool = False,
    ) -> TimeframeContext:
        if frame is None:
            return TimeframeContext(timeframe, None, "no_data", "No candles for this period yet.")
        if is_root:
            return TimeframeContext(
                timeframe, frame, "root",
                f"Macro draw {frame.draw} ({frame.model}, {frame.position}).",
            )
        status = MultiTfDolService._child_status(frame.draw, parent.draw if parent else "neutral")
        note = {
            "aligned": f"Obeys parent: {frame.draw} draw supports the higher-timeframe objective.",
            "corrective": f"Counter-parent {frame.draw} move — corrective/manipulation, not a new macro draw.",
            "neutral": "No decisive delivery this period.",
        }.get(status, "")
        return TimeframeContext(timeframe, frame, status, note)

    @staticmethod
    def _child_status(child_draw: str, parent_draw: str) -> str:
        if child_draw == "neutral" or parent_draw == "neutral":
            return "neutral"
        return "aligned" if child_draw == parent_draw else "corrective"

    @staticmethod
    def _conflict_level(
        monthly: TimeframeFrame | None,
        weekly: TimeframeFrame | None,
        daily: TimeframeFrame | None,
    ) -> str:
        if daily is None or daily.draw == "neutral":
            return "none"
        opposes = []
        for parent in (weekly, monthly):
            if parent is not None and parent.draw != "neutral" and parent.draw != daily.draw:
                opposes.append(parent)
        if len(opposes) == 2:
            return "major"
        if len(opposes) == 1:
            return "minor"
        return "none"

    @staticmethod
    def _execution_hint(conflict_level: str, contexts: list[TimeframeContext]) -> str:
        if conflict_level == "major":
            return (
                "No Trade - major multi-timeframe DOL conflict: Daily opposes both Weekly "
                "and Monthly draw. Wait for HTF resolution."
            )
        if conflict_level == "minor":
            return (
                "Caution - Daily draw conflicts with one higher timeframe; treat Daily move "
                "as corrective until it aligns."
            )
        return (
            "Aligned - Monthly, Weekly, and Daily draws agree; proceed to lower-timeframe "
            "confirmation layers."
        )

    @staticmethod
    def _active_dol(db: Session, symbol: str, daily: TimeframeFrame | None) -> str:
        assessment = db.query(DolAssessment).filter(DolAssessment.symbol == symbol).first()
        if assessment is None or assessment.primary_level_id is None:
            return "No operative DOL set."
        primary = db.get(LiquidityLevel, assessment.primary_level_id)
        if primary is None:
            return "No operative DOL set."
        daily_draw = daily.draw if daily else "unknown"
        return (
            f"{primary.level_type} {primary.liquidity_side} @ {primary.price} "
            f"serving {daily_draw} daily delivery."
        )
