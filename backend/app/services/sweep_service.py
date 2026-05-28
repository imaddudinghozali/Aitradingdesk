from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models.liquidity_level import LiquidityLevel
from app.models.market_snapshot import MarketSnapshot
from app.models.sweep_event import SweepEvent
from app.schemas.liquidity import LiquidityStatus
from app.schemas.sweep import NarrativeAlignment, SweepScanRequest, SweepStatus
from app.utils.timezone import NY_TZ


class SweepService:
    RELEVANT_SESSIONS = {"London", "NY AM"}
    OPPOSITE_TARGET = {
        "PDH": "PDL",
        "PDL": "PDH",
        "PWH": "PWL",
        "PWL": "PWH",
        "ASIA_HIGH": "ASIA_LOW",
        "ASIA_LOW": "ASIA_HIGH",
        "LONDON_HIGH": "LONDON_LOW",
        "LONDON_LOW": "LONDON_HIGH",
    }

    @staticmethod
    def scan(
        db: Session,
        request: SweepScanRequest,
    ) -> tuple[datetime, list[SweepEvent], list[str]]:
        levels = (
            db.query(LiquidityLevel)
            .filter(
                LiquidityLevel.symbol == request.symbol,
                LiquidityLevel.status != LiquidityStatus.INVALIDATED.value,
            )
            .order_by(LiquidityLevel.level_type.asc())
            .all()
        )
        if not levels:
            raise ValueError("No active liquidity levels found. Refresh liquidity levels first.")

        latest = (
            db.query(MarketSnapshot)
            .filter(
                MarketSnapshot.symbol == request.symbol,
                MarketSnapshot.timeframe == request.timeframe,
            )
            .order_by(MarketSnapshot.timestamp_utc.desc())
            .first()
        )
        if latest is None:
            raise ValueError(f"No {request.timeframe} snapshots found for {request.symbol}")

        as_of_utc = SweepService._utc(request.as_of_utc or latest.timestamp_utc)
        events: list[SweepEvent] = []
        for level in levels:
            event = SweepService._scan_level(db, level, request, as_of_utc)
            if event is not None:
                events.append(event)
        db.commit()
        for event in events:
            db.refresh(event)

        waiting_reasons = [
            f"{event.level_type}: {event.reason}"
            for event in events
            if event.sweep_status in {
                SweepStatus.FALSE_TOUCH.value,
                SweepStatus.LIQUIDITY_TAP.value,
            }
        ]
        return as_of_utc, events, waiting_reasons

    @staticmethod
    def list_events(
        db: Session,
        symbol: str,
        status: SweepStatus | None = None,
    ) -> list[SweepEvent]:
        query = db.query(SweepEvent).filter(SweepEvent.symbol == symbol.upper())
        if status:
            query = query.filter(SweepEvent.sweep_status == status.value)
        return query.order_by(SweepEvent.detected_at_utc.desc()).all()

    @staticmethod
    def _scan_level(
        db: Session,
        level: LiquidityLevel,
        request: SweepScanRequest,
        as_of_utc: datetime,
    ) -> SweepEvent | None:
        source_end = SweepService._stored_ny_to_utc(level.source_period_end_ny)
        snapshots = (
            db.query(MarketSnapshot)
            .filter(
                MarketSnapshot.symbol == level.symbol,
                MarketSnapshot.timeframe == request.timeframe,
            )
            .order_by(MarketSnapshot.timestamp_utc.asc())
            .all()
        )
        eligible = [
            snapshot
            for snapshot in snapshots
            if source_end <= SweepService._utc(snapshot.timestamp_utc) <= as_of_utc
        ]
        penetrations = [
            index
            for index, snapshot in enumerate(eligible)
            if SweepService._penetrated(level, snapshot)
        ]
        touches = [
            index
            for index, snapshot in enumerate(eligible)
            if SweepService._interacts(level, snapshot)
        ]
        interaction_index = penetrations[0] if penetrations else (touches[-1] if touches else None)
        if interaction_index is None:
            return None

        interaction = eligible[interaction_index]
        confirmation = (
            eligible[interaction_index + 1]
            if interaction_index + 1 < len(eligible)
            else None
        )
        classified = SweepService._classify(
            level,
            interaction,
            confirmation,
            request.narrative_alignment,
        )
        existing = (
            db.query(SweepEvent)
            .filter(
                SweepEvent.liquidity_level_id == level.id,
                SweepEvent.interaction_snapshot_id == interaction.id,
            )
            .first()
        )
        event = existing or SweepEvent(
            liquidity_level_id=level.id,
            interaction_snapshot_id=interaction.id,
            symbol=level.symbol,
            level_type=level.level_type,
            liquidity_side=level.liquidity_side,
            level_price=level.price,
        )
        event.confirmation_snapshot_id = confirmation.id if confirmation else None
        event.session = interaction.session
        event.session_anchor = interaction.session_anchor
        event.daily_quarter = interaction.daily_quarter
        event.micro_quarter_90m = interaction.micro_quarter_90m
        event.sweep_status = classified["sweep_status"]
        event.confirmation_status = classified["confirmation_status"]
        event.displacement_detected = classified["displacement_detected"]
        event.relevant_timing = classified["relevant_timing"]
        event.narrative_alignment = request.narrative_alignment.value
        event.reason = classified["reason"]
        event.target_liquidity = SweepService.OPPOSITE_TARGET.get(level.level_type)
        event.detected_at_utc = SweepService._utc(interaction.timestamp_utc)
        if existing is None:
            db.add(event)
        return event

    @staticmethod
    def _classify(
        level: LiquidityLevel,
        interaction: MarketSnapshot,
        confirmation: MarketSnapshot | None,
        alignment: NarrativeAlignment,
    ) -> dict[str, str | bool]:
        penetrated = SweepService._penetrated(level, interaction)
        reclaimed = SweepService._reclaimed(level, interaction)
        timing = (
            interaction.session in SweepService.RELEVANT_SESSIONS
            and interaction.daily_quarter in {"Q2", "Q3"}
        )
        reversal = confirmation is not None and SweepService._reversal_displacement(
            level, interaction, confirmation
        )
        continuation = confirmation is not None and SweepService._continuation_displacement(
            level, interaction, confirmation
        )

        if not penetrated:
            if confirmation is None:
                return SweepService._result(
                    SweepStatus.LIQUIDITY_TAP,
                    "waiting_confirmation",
                    False,
                    timing,
                    "Level touched but liquidity not taken; waiting for the next candle.",
                )
            return SweepService._result(
                SweepStatus.FALSE_TOUCH,
                "rejected_as_sweep",
                False,
                timing,
                "Price reached the level without taking liquidity; not valid sweep confirmation.",
            )

        if (
            timing
            and alignment == NarrativeAlignment.ALIGNED
            and reversal
        ):
            return SweepService._result(
                SweepStatus.MANIPULATION_SWEEP,
                "confirmed_reversal_displacement",
                True,
                timing,
                "Liquidity taken during relevant session and displaced opposite the sweep in alignment with narrative.",
            )

        if reclaimed:
            return SweepService._result(
                SweepStatus.TURTLE_SOUP,
                "wick_reclaim_confirmed",
                reversal,
                timing,
                "Price penetrated liquidity but closed back through the level on the interaction candle.",
            )

        if continuation and SweepService._closed_beyond(level, interaction):
            return SweepService._result(
                SweepStatus.TRUE_BREAKOUT_BREAKDOWN,
                "continuation_displacement",
                True,
                timing,
                "Price closed beyond liquidity and the next candle continued in the breakout direction.",
            )

        if reversal and timing:
            return SweepService._result(
                SweepStatus.VALID_SWEEP,
                "confirmed_reversal_displacement",
                True,
                timing,
                "Liquidity taken with reversal displacement during a relevant session.",
            )

        return SweepService._result(
            SweepStatus.LIQUIDITY_TAP,
            "waiting_confirmation",
            False,
            timing,
            "Liquidity taken but valid displacement or relevant timing confirmation is still missing.",
        )

    @staticmethod
    def _result(
        status: SweepStatus,
        confirmation_status: str,
        displacement: bool,
        timing: bool,
        reason: str,
    ) -> dict[str, str | bool]:
        return {
            "sweep_status": status.value,
            "confirmation_status": confirmation_status,
            "displacement_detected": displacement,
            "relevant_timing": timing,
            "reason": reason,
        }

    @staticmethod
    def _interacts(level: LiquidityLevel, snapshot: MarketSnapshot) -> bool:
        if level.liquidity_side == "BSL":
            return snapshot.high >= level.price
        return snapshot.low <= level.price

    @staticmethod
    def _penetrated(level: LiquidityLevel, snapshot: MarketSnapshot) -> bool:
        if level.liquidity_side == "BSL":
            return snapshot.high > level.price
        return snapshot.low < level.price

    @staticmethod
    def _reclaimed(level: LiquidityLevel, snapshot: MarketSnapshot) -> bool:
        if level.liquidity_side == "BSL":
            return snapshot.high > level.price and snapshot.close < level.price
        return snapshot.low < level.price and snapshot.close > level.price

    @staticmethod
    def _closed_beyond(level: LiquidityLevel, snapshot: MarketSnapshot) -> bool:
        if level.liquidity_side == "BSL":
            return snapshot.close > level.price
        return snapshot.close < level.price

    @staticmethod
    def _reversal_displacement(
        level: LiquidityLevel,
        interaction: MarketSnapshot,
        confirmation: MarketSnapshot,
    ) -> bool:
        if level.liquidity_side == "BSL":
            return confirmation.close < interaction.low
        return confirmation.close > interaction.high

    @staticmethod
    def _continuation_displacement(
        level: LiquidityLevel,
        interaction: MarketSnapshot,
        confirmation: MarketSnapshot,
    ) -> bool:
        if level.liquidity_side == "BSL":
            return confirmation.close > interaction.high
        return confirmation.close < interaction.low

    @staticmethod
    def _utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    @staticmethod
    def _stored_ny_to_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            value = value.replace(tzinfo=NY_TZ)
        return value.astimezone(UTC)
