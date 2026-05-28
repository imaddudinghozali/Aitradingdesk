from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.delivery_quality_assessment import DeliveryQualityAssessment
from app.models.dol_assessment import DolAssessment
from app.models.liquidity_level import LiquidityLevel
from app.models.market_snapshot import MarketSnapshot
from app.models.news_catalyst_event import NewsCatalystEvent
from app.schemas.news import NewsCatalystEvaluateRequest
from app.utils.timezone import NY_TZ


class NewsCatalystService:
    @staticmethod
    def evaluate(db: Session, request: NewsCatalystEvaluateRequest) -> NewsCatalystEvent:
        dol = db.query(DolAssessment).filter(DolAssessment.symbol == request.symbol).first()
        if dol is None:
            raise ValueError("DOL assessment not found. Evaluate DOL before news catalyst.")
        cutoff = NewsCatalystService._utc(
            request.as_of_utc or NewsCatalystService._latest_time(db, request.symbol)
        )
        scheduled = NewsCatalystService._utc(request.scheduled_at_utc)
        pre_candles = NewsCatalystService._pre_news_candles(db, request.symbol, scheduled)
        high = max((candle.high for candle in pre_candles), default=None)
        low = min((candle.low for candle in pre_candles), default=None)
        existing = next(
            (
                event
                for event in db.query(NewsCatalystEvent)
                .filter(
                    NewsCatalystEvent.symbol == request.symbol,
                    NewsCatalystEvent.event_name == request.event_name.upper(),
                )
                .all()
                if NewsCatalystService._utc(event.scheduled_at_utc) == scheduled
            ),
            None,
        )
        assessment = existing or NewsCatalystEvent(
                symbol=request.symbol,
                dol_assessment_id=dol.id,
                event_name=request.event_name.upper(),
                impact=request.impact,
                scheduled_at_utc=scheduled,
                news_phase="waiting",
                catalyst_status="waiting",
                direction_alignment="waiting",
                status_reason="Waiting for evaluation.",
                post_news_expectation="Waiting for scheduled event.",
                no_trade_reason="No Trade until news context is evaluated.",
                as_of_utc=cutoff,
            )
        assessment.dol_assessment_id = dol.id
        assessment.impact = request.impact
        assessment.pre_news_high = high
        assessment.pre_news_low = low
        assessment.direction_alignment = (
            "aligned" if dol.lifecycle_status in {"Active", "Shift Confirmed"} else "waiting_dol"
        )
        if cutoff < scheduled:
            assessment.news_phase = "pre_news_accumulation"
            assessment.catalyst_status = "waiting_release"
            assessment.status_reason = (
                f"{assessment.event_name} is scheduled; pre-news movement is treated as "
                "possible liquidity engineering, not directional confirmation."
            )
            assessment.post_news_expectation = (
                f"After release, require clean displacement toward {dol.delivery_direction} "
                "and a validated retracement/POI."
            )
            assessment.no_trade_reason = (
                f"No Trade - high-impact {assessment.event_name} is pending; wait for post-news delivery."
            )
        else:
            quality = (
                db.query(DeliveryQualityAssessment)
                .filter(DeliveryQualityAssessment.symbol == request.symbol)
                .first()
            )
            if quality and quality.expansion_status == "valid":
                assessment.news_phase = "post_news_repricing"
                assessment.catalyst_status = "aligned_continuation"
                assessment.status_reason = (
                    "Post-news delivery has clean expansion with confirmed retracement "
                    "aligned to the active DOL."
                )
            else:
                assessment.news_phase = "post_news_repricing"
                assessment.catalyst_status = "inconclusive"
                assessment.status_reason = (
                    "Post-news delivery is inconclusive: clean displacement with validated "
                    "retracement has not been confirmed."
                )
            assessment.post_news_expectation = (
                "Continue only after backend delivery quality and later execution confirmation remain aligned."
            )
            assessment.no_trade_reason = (
                "No Trade - post-news catalyst alone is not execution confirmation."
            )
            NewsCatalystService._store_previous_news_levels(
                db, request.symbol, high, low, scheduled, cutoff
            )
        assessment.as_of_utc = cutoff
        if assessment.id is None:
            db.add(assessment)
        db.commit()
        db.refresh(assessment)
        return assessment

    @staticmethod
    def get_current(db: Session, symbol: str) -> NewsCatalystEvent | None:
        return (
            db.query(NewsCatalystEvent)
            .filter(NewsCatalystEvent.symbol == symbol)
            .order_by(NewsCatalystEvent.scheduled_at_utc.desc(), NewsCatalystEvent.id.desc())
            .first()
        )

    @staticmethod
    def _latest_time(db: Session, symbol: str) -> datetime:
        latest = (
            db.query(MarketSnapshot)
            .filter(MarketSnapshot.symbol == symbol)
            .order_by(MarketSnapshot.timestamp_utc.desc())
            .first()
        )
        if latest is None:
            raise ValueError(f"No market snapshots found for {symbol}")
        return latest.timestamp_utc

    @staticmethod
    def _pre_news_candles(
        db: Session, symbol: str, scheduled: datetime
    ) -> list[MarketSnapshot]:
        start = scheduled - timedelta(hours=4)
        return [
            candle
            for candle in db.query(MarketSnapshot)
            .filter(MarketSnapshot.symbol == symbol, MarketSnapshot.timeframe == "M15")
            .order_by(MarketSnapshot.timestamp_utc.asc())
            .all()
            if start <= NewsCatalystService._utc(candle.timestamp_utc) < scheduled
        ]

    @staticmethod
    def _store_previous_news_levels(
        db: Session,
        symbol: str,
        high: Decimal | None,
        low: Decimal | None,
        scheduled: datetime,
        cutoff: datetime,
    ) -> None:
        if high is None or low is None:
            return
        for level_type, side, price in (
            ("NEWS_HIGH", "BSL", high),
            ("NEWS_LOW", "SSL", low),
        ):
            level = (
                db.query(LiquidityLevel)
                .filter(LiquidityLevel.symbol == symbol, LiquidityLevel.level_type == level_type)
                .first()
                or LiquidityLevel(symbol=symbol, level_type=level_type)
            )
            level.liquidity_side = side
            level.price = price
            level.status = "active"
            level.source_timeframe = "news"
            level.source_period_start_ny = (scheduled - timedelta(hours=4)).astimezone(NY_TZ)
            level.source_period_end_ny = scheduled.astimezone(NY_TZ)
            level.as_of_utc = cutoff
            level.status_reason = "Previous high-impact news pre-release range liquidity."
            if level.id is None:
                db.add(level)

    @staticmethod
    def _utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
