from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.engines.time_engine import Session as MarketSession, TimeEngine
from app.models.liquidity_level import LiquidityLevel
from app.models.market_snapshot import MarketSnapshot
from app.schemas.liquidity import LiquidityRefreshRequest, LiquidityStatus, LiquidityStatusUpdate
from app.utils.timezone import NY_TZ, to_ny_time


@dataclass(frozen=True)
class LevelCandidate:
    level_type: str
    liquidity_side: str
    price: Decimal
    source_timeframe: str
    source_period_start_ny: datetime
    source_period_end_ny: datetime


class LiquidityService:
    EXPECTED_LEVEL_TYPES = [
        "PDH",
        "PDL",
        "PWH",
        "PWL",
        "PMH",
        "PML",
        "PYH",
        "PYL",
        "ASIA_HIGH",
        "ASIA_LOW",
        "LONDON_HIGH",
        "LONDON_LOW",
    ]
    INTRADAY_TIMEFRAMES = {"M5", "M15", "H1"}
    SWING_TIMEFRAMES = {"H1": 3, "H4": 2}
    SWING_TOP_N = 3

    @staticmethod
    def refresh_levels(
        db: Session,
        request: LiquidityRefreshRequest,
    ) -> tuple[datetime, list[LiquidityLevel], list[str]]:
        snapshots = (
            db.query(MarketSnapshot)
            .filter(MarketSnapshot.symbol == request.symbol)
            .order_by(MarketSnapshot.timestamp_utc.asc())
            .all()
        )
        if not snapshots:
            raise ValueError(f"No market snapshots found for {request.symbol}")

        as_of_utc = request.as_of_utc or snapshots[-1].timestamp_utc
        as_of_utc = LiquidityService._utc(as_of_utc)
        eligible = [
            snapshot
            for snapshot in snapshots
            if LiquidityService._utc(snapshot.timestamp_utc) <= as_of_utc
        ]
        if not eligible:
            raise ValueError("No market snapshots exist at or before as_of_utc")

        as_of_ny = to_ny_time(as_of_utc)
        candidates = [
            *LiquidityService._previous_daily_candidates(eligible, as_of_ny),
            *LiquidityService._previous_weekly_candidates(eligible, as_of_ny),
            *LiquidityService._previous_monthly_candidates(eligible, as_of_ny),
            *LiquidityService._previous_yearly_candidates(eligible, as_of_ny),
            *LiquidityService._session_candidates(eligible, as_of_ny, MarketSession.ASIA),
            *LiquidityService._session_candidates(eligible, as_of_ny, MarketSession.LONDON),
        ]
        for tf, window in LiquidityService.SWING_TIMEFRAMES.items():
            candidates.extend(
                LiquidityService._swing_point_candidates(eligible, as_of_utc, tf, window)
            )

        levels = [
            LiquidityService._upsert_level(db, request.symbol, candidate, eligible, as_of_utc)
            for candidate in candidates
        ]
        news_levels = (
            db.query(LiquidityLevel)
            .filter(
                LiquidityLevel.symbol == request.symbol,
                LiquidityLevel.level_type.in_(["NEWS_HIGH", "NEWS_LOW"]),
                LiquidityLevel.as_of_utc <= as_of_utc,
            )
            .all()
        )
        levels.extend(news_levels)
        db.commit()
        for level in levels:
            db.refresh(level)

        generated_types = {level.level_type for level in levels}
        missing_types = [
            level_type
            for level_type in LiquidityService.EXPECTED_LEVEL_TYPES
            if level_type not in generated_types
        ]
        return as_of_utc, sorted(levels, key=lambda level: level.level_type), missing_types

    @staticmethod
    def list_levels(
        db: Session,
        symbol: str,
        status: LiquidityStatus | None = None,
    ) -> list[LiquidityLevel]:
        query = db.query(LiquidityLevel).filter(LiquidityLevel.symbol == symbol.upper())
        if status:
            query = query.filter(LiquidityLevel.status == status.value)
        return query.order_by(LiquidityLevel.level_type.asc()).all()

    @staticmethod
    def update_status(
        db: Session,
        level_id: int,
        update: LiquidityStatusUpdate,
    ) -> LiquidityLevel | None:
        level = db.query(LiquidityLevel).filter(LiquidityLevel.id == level_id).first()
        if level is None:
            return None

        level.status = update.status.value
        level.status_reason = update.reason
        event_time = datetime.now(UTC)
        if update.status == LiquidityStatus.INVALIDATED:
            level.invalidated_at_utc = event_time
        elif update.status == LiquidityStatus.TOUCHED:
            level.touched_at_utc = event_time
            level.taken_at_utc = None
            level.invalidated_at_utc = None
        elif update.status == LiquidityStatus.TAKEN:
            level.touched_at_utc = event_time
            level.taken_at_utc = event_time
            level.invalidated_at_utc = None
        elif update.status == LiquidityStatus.ACTIVE:
            level.touched_at_utc = None
            level.taken_at_utc = None
            level.invalidated_at_utc = None

        db.commit()
        db.refresh(level)
        return level

    @staticmethod
    def _previous_daily_candidates(
        snapshots: list[MarketSnapshot],
        as_of_ny: datetime,
    ) -> list[LevelCandidate]:
        daily = [
            snapshot
            for snapshot in snapshots
            if snapshot.timeframe == "D" and to_ny_time(LiquidityService._utc(snapshot.timestamp_utc)).date() < as_of_ny.date()
        ]
        if not daily:
            return []

        source_date = max(
            to_ny_time(LiquidityService._utc(snapshot.timestamp_utc)).date()
            for snapshot in daily
        )
        source = [
            snapshot
            for snapshot in daily
            if to_ny_time(LiquidityService._utc(snapshot.timestamp_utc)).date() == source_date
        ]
        start = LiquidityService._ny_midnight(source_date)
        end = start + timedelta(days=1)
        return LiquidityService._high_low_candidates("PD", "D", source, start, end)

    @staticmethod
    def _previous_weekly_candidates(
        snapshots: list[MarketSnapshot],
        as_of_ny: datetime,
    ) -> list[LevelCandidate]:
        current_week = as_of_ny.date().isocalendar()[:2]
        daily = [snapshot for snapshot in snapshots if snapshot.timeframe == "D"]
        grouped: dict[tuple[int, int], list[MarketSnapshot]] = {}
        for snapshot in daily:
            snapshot_date = to_ny_time(LiquidityService._utc(snapshot.timestamp_utc)).date()
            week_key = snapshot_date.isocalendar()[:2]
            if week_key < current_week:
                grouped.setdefault(week_key, []).append(snapshot)
        if not grouped:
            return []

        source = grouped[max(grouped)]
        source_dates = [
            to_ny_time(LiquidityService._utc(snapshot.timestamp_utc)).date()
            for snapshot in source
        ]
        week_start_date = min(source_dates) - timedelta(days=min(source_dates).weekday())
        start = LiquidityService._ny_midnight(week_start_date)
        end = start + timedelta(days=7)
        return LiquidityService._high_low_candidates("PW", "D", source, start, end)

    @staticmethod
    def _previous_monthly_candidates(
        snapshots: list[MarketSnapshot],
        as_of_ny: datetime,
    ) -> list[LevelCandidate]:
        current_month = (as_of_ny.year, as_of_ny.month)
        daily = [snapshot for snapshot in snapshots if snapshot.timeframe == "D"]
        grouped: dict[tuple[int, int], list[MarketSnapshot]] = {}
        for snapshot in daily:
            snapshot_date = to_ny_time(LiquidityService._utc(snapshot.timestamp_utc)).date()
            key = (snapshot_date.year, snapshot_date.month)
            if key < current_month:
                grouped.setdefault(key, []).append(snapshot)
        if not grouped:
            return []
        source_key = max(grouped)
        source = grouped[source_key]
        start = LiquidityService._ny_midnight(date(source_key[0], source_key[1], 1))
        if source_key[1] == 12:
            end = LiquidityService._ny_midnight(date(source_key[0] + 1, 1, 1))
        else:
            end = LiquidityService._ny_midnight(date(source_key[0], source_key[1] + 1, 1))
        return LiquidityService._high_low_candidates("PM", "D", source, start, end)

    @staticmethod
    def _previous_yearly_candidates(
        snapshots: list[MarketSnapshot],
        as_of_ny: datetime,
    ) -> list[LevelCandidate]:
        daily = [snapshot for snapshot in snapshots if snapshot.timeframe == "D"]
        grouped: dict[int, list[MarketSnapshot]] = {}
        for snapshot in daily:
            snapshot_date = to_ny_time(LiquidityService._utc(snapshot.timestamp_utc)).date()
            if snapshot_date.year < as_of_ny.year:
                grouped.setdefault(snapshot_date.year, []).append(snapshot)
        if not grouped:
            return []
        source_year = max(grouped)
        start = LiquidityService._ny_midnight(date(source_year, 1, 1))
        end = LiquidityService._ny_midnight(date(source_year + 1, 1, 1))
        return LiquidityService._high_low_candidates("PY", "D", grouped[source_year], start, end)

    @staticmethod
    def _session_candidates(
        snapshots: list[MarketSnapshot],
        as_of_ny: datetime,
        session: MarketSession,
    ) -> list[LevelCandidate]:
        grouped: dict[date, list[MarketSnapshot]] = {}
        for snapshot in snapshots:
            if snapshot.timeframe not in LiquidityService.INTRADAY_TIMEFRAMES:
                continue
            snapshot_ny = to_ny_time(LiquidityService._utc(snapshot.timestamp_utc))
            if TimeEngine.get_session(snapshot_ny) != session:
                continue
            session_date = LiquidityService._session_date(snapshot_ny, session)
            _, session_end = LiquidityService._session_window(session, session_date)
            if session_end <= as_of_ny:
                grouped.setdefault(session_date, []).append(snapshot)
        if not grouped:
            return []

        session_date = max(grouped)
        source = grouped[session_date]
        start, end = LiquidityService._session_window(session, session_date)
        prefix = "ASIA" if session == MarketSession.ASIA else "LONDON"
        return LiquidityService._high_low_candidates(prefix + "_", "intraday", source, start, end)

    @staticmethod
    def _swing_point_candidates(
        snapshots: list[MarketSnapshot],
        as_of_utc: datetime,
        timeframe: str,
        window: int,
    ) -> list[LevelCandidate]:
        """Detect untaken swing highs/lows on a single timeframe.

        A swing point is a candle whose high (low) is strictly greater (less)
        than `window` candles on both sides. We surface the most recent
        `SWING_TOP_N` swing highs and lows that have not been violated by any
        subsequent candle within `[swing_index + window + 1, as_of]`.
        """
        candles = sorted(
            (c for c in snapshots if c.timeframe == timeframe),
            key=lambda c: LiquidityService._utc(c.timestamp_utc),
        )
        if len(candles) < window * 2 + 1:
            return []

        swing_highs: list[tuple[MarketSnapshot, Decimal]] = []
        swing_lows: list[tuple[MarketSnapshot, Decimal]] = []
        for i in range(window, len(candles) - window):
            pivot = candles[i]
            left = candles[i - window : i]
            right = candles[i + 1 : i + window + 1]
            if pivot.high > max(c.high for c in left) and pivot.high > max(c.high for c in right):
                later = candles[i + window + 1 :]
                if not any(c.high > pivot.high for c in later):
                    swing_highs.append((pivot, pivot.high))
            if pivot.low < min(c.low for c in left) and pivot.low < min(c.low for c in right):
                later = candles[i + window + 1 :]
                if not any(c.low < pivot.low for c in later):
                    swing_lows.append((pivot, pivot.low))

        swing_highs.sort(
            key=lambda pair: LiquidityService._utc(pair[0].timestamp_utc), reverse=True
        )
        swing_lows.sort(
            key=lambda pair: LiquidityService._utc(pair[0].timestamp_utc), reverse=True
        )

        candidates: list[LevelCandidate] = []
        for rank, (pivot, price) in enumerate(swing_highs[: LiquidityService.SWING_TOP_N], start=1):
            ny_start = to_ny_time(LiquidityService._utc(pivot.timestamp_utc))
            ny_end = ny_start + LiquidityService._timeframe_delta(timeframe)
            candidates.append(
                LevelCandidate(
                    level_type=f"{timeframe}_SWING_HIGH_{rank}",
                    liquidity_side="BSL",
                    price=price,
                    source_timeframe=timeframe,
                    source_period_start_ny=ny_start,
                    source_period_end_ny=ny_end,
                )
            )
        for rank, (pivot, price) in enumerate(swing_lows[: LiquidityService.SWING_TOP_N], start=1):
            ny_start = to_ny_time(LiquidityService._utc(pivot.timestamp_utc))
            ny_end = ny_start + LiquidityService._timeframe_delta(timeframe)
            candidates.append(
                LevelCandidate(
                    level_type=f"{timeframe}_SWING_LOW_{rank}",
                    liquidity_side="SSL",
                    price=price,
                    source_timeframe=timeframe,
                    source_period_start_ny=ny_start,
                    source_period_end_ny=ny_end,
                )
            )
        return candidates

    @staticmethod
    def _timeframe_delta(timeframe: str) -> timedelta:
        return {
            "M5": timedelta(minutes=5),
            "M15": timedelta(minutes=15),
            "H1": timedelta(hours=1),
            "H4": timedelta(hours=4),
            "D": timedelta(days=1),
        }.get(timeframe, timedelta(hours=1))

    @staticmethod
    def _high_low_candidates(
        prefix: str,
        source_timeframe: str,
        snapshots: list[MarketSnapshot],
        start: datetime,
        end: datetime,
    ) -> list[LevelCandidate]:
        high_type = f"{prefix}H" if prefix in {"PD", "PW", "PM", "PY"} else f"{prefix}HIGH"
        low_type = f"{prefix}L" if prefix in {"PD", "PW", "PM", "PY"} else f"{prefix}LOW"
        return [
            LevelCandidate(high_type, "BSL", max(snapshot.high for snapshot in snapshots), source_timeframe, start, end),
            LevelCandidate(low_type, "SSL", min(snapshot.low for snapshot in snapshots), source_timeframe, start, end),
        ]

    @staticmethod
    def _upsert_level(
        db: Session,
        symbol: str,
        candidate: LevelCandidate,
        snapshots: list[MarketSnapshot],
        as_of_utc: datetime,
    ) -> LiquidityLevel:
        existing = (
            db.query(LiquidityLevel)
            .filter(
                LiquidityLevel.symbol == symbol,
                LiquidityLevel.level_type == candidate.level_type,
            )
            .first()
        )
        status, reason, touched_at, taken_at = LiquidityService._status_from_price_action(
            candidate,
            snapshots,
            as_of_utc,
        )
        same_source_invalidated = (
            existing is not None
            and existing.status == LiquidityStatus.INVALIDATED.value
            and LiquidityService._same_ny_time(
                existing.source_period_start_ny,
                candidate.source_period_start_ny,
            )
        )
        if same_source_invalidated:
            status = existing.status
            reason = existing.status_reason

        level = existing or LiquidityLevel(symbol=symbol, level_type=candidate.level_type)
        level.liquidity_side = candidate.liquidity_side
        level.price = candidate.price
        level.source_timeframe = candidate.source_timeframe
        level.source_period_start_ny = candidate.source_period_start_ny
        level.source_period_end_ny = candidate.source_period_end_ny
        level.as_of_utc = as_of_utc
        level.status = status
        level.status_reason = reason
        level.touched_at_utc = touched_at
        level.taken_at_utc = taken_at
        if status != LiquidityStatus.INVALIDATED.value:
            level.invalidated_at_utc = None
        if existing is None:
            db.add(level)
        return level

    @staticmethod
    def _status_from_price_action(
        candidate: LevelCandidate,
        snapshots: list[MarketSnapshot],
        as_of_utc: datetime,
    ) -> tuple[str, str, datetime | None, datetime | None]:
        source_end_utc = candidate.source_period_end_ny.astimezone(UTC)
        later = [
            snapshot
            for snapshot in snapshots
            if source_end_utc <= LiquidityService._utc(snapshot.timestamp_utc) <= as_of_utc
        ]
        for snapshot in later:
            taken = (
                snapshot.high > candidate.price
                if candidate.liquidity_side == "BSL"
                else snapshot.low < candidate.price
            )
            if taken:
                event_time = LiquidityService._utc(snapshot.timestamp_utc)
                return (
                    LiquidityStatus.TAKEN.value,
                    f"{candidate.liquidity_side} level penetrated after source period",
                    event_time,
                    event_time,
                )
        for snapshot in later:
            touched = (
                snapshot.high == candidate.price
                if candidate.liquidity_side == "BSL"
                else snapshot.low == candidate.price
            )
            if touched:
                event_time = LiquidityService._utc(snapshot.timestamp_utc)
                return (
                    LiquidityStatus.TOUCHED.value,
                    f"{candidate.liquidity_side} level touched; awaiting penetration",
                    event_time,
                    None,
                )
        return LiquidityStatus.ACTIVE.value, "Level has not been reached after source period", None, None

    @staticmethod
    def _session_date(dt_ny: datetime, session: MarketSession) -> date:
        if session == MarketSession.ASIA and dt_ny.hour >= 21:
            return dt_ny.date() + timedelta(days=1)
        return dt_ny.date()

    @staticmethod
    def _session_window(session: MarketSession, session_date: date) -> tuple[datetime, datetime]:
        if session == MarketSession.ASIA:
            start = datetime.combine(session_date - timedelta(days=1), time(21), tzinfo=NY_TZ)
            end = datetime.combine(session_date, time(5), tzinfo=NY_TZ)
            return start, end
        start = datetime.combine(session_date, time(5), tzinfo=NY_TZ)
        end = datetime.combine(session_date, time(9), tzinfo=NY_TZ)
        return start, end

    @staticmethod
    def _ny_midnight(value: date) -> datetime:
        return datetime.combine(value, time.min, tzinfo=NY_TZ)

    @staticmethod
    def _utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    @staticmethod
    def _same_ny_time(left: datetime, right: datetime) -> bool:
        if left.tzinfo is None:
            left = left.replace(tzinfo=NY_TZ)
        else:
            left = left.astimezone(NY_TZ)
        if right.tzinfo is None:
            right = right.replace(tzinfo=NY_TZ)
        else:
            right = right.astimezone(NY_TZ)
        return left == right
