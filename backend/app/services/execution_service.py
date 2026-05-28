from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.delivery_quality_assessment import DeliveryQualityAssessment
from app.models.dol_assessment import DolAssessment
from app.models.execution_assessment import ExecutionAssessment
from app.models.irl_erl_mapping import IrlErlMapping
from app.models.liquidity_level import LiquidityLevel
from app.models.market_snapshot import MarketSnapshot
from app.models.mmxm_assessment import MmxmAssessment
from app.models.narrative_ledger import NarrativeLedger
from app.models.news_catalyst_event import NewsCatalystEvent
from app.models.poi_zone import PoiZone
from app.models.quarter_readiness import QuarterReadinessAssessment
from app.models.ssmt_event import SsmtEvent
from app.schemas.execution import ExecutionEvaluateRequest, PoiScanRequest
from app.services.delivery_quality_service import DeliveryQualityService


class PoiService:
    @staticmethod
    def scan(db: Session, request: PoiScanRequest) -> list[PoiZone]:
        candles = PoiService._candles(db, request.symbol, request.timeframe, request.as_of_utc)
        if not candles:
            raise ValueError(f"No {request.timeframe} market snapshots found for {request.symbol}.")
        cutoff = PoiService._utc(request.as_of_utc or candles[-1].timestamp_utc)
        for index in range(2, len(candles)):
            left, impulse, right = candles[index - 2 : index + 1]
            if right.low > left.high and impulse.close > impulse.open:
                PoiService._upsert(
                    db, request.symbol, request.timeframe, "FVG", "bullish",
                    left.high, right.low, right, candles, cutoff,
                )
                if left.close < left.open:
                    PoiService._upsert(
                        db, request.symbol, request.timeframe, "OB", "bullish",
                        min(left.open, left.close), max(left.open, left.close), right, candles, cutoff,
                    )
            if right.high < left.low and impulse.close < impulse.open:
                PoiService._upsert(
                    db, request.symbol, request.timeframe, "FVG", "bearish",
                    right.high, left.low, right, candles, cutoff,
                )
                if left.close > left.open:
                    PoiService._upsert(
                        db, request.symbol, request.timeframe, "OB", "bearish",
                        min(left.open, left.close), max(left.open, left.close), right, candles, cutoff,
                    )
        primary = (
            db.query(PoiZone)
            .filter(
                PoiZone.symbol == request.symbol,
                PoiZone.timeframe == request.timeframe,
                PoiZone.poi_type.in_(["FVG", "OB"]),
            )
            .all()
        )
        for zone in primary:
            PoiService._update_status(zone, candles, cutoff)
            if zone.poi_type == "OB" and zone.status == "validated_retracement":
                mitigation = PoiService._upsert(
                    db,
                    zone.symbol,
                    zone.timeframe,
                    "MITIGATION",
                    zone.direction,
                    zone.price_low,
                    zone.price_high,
                    db.get(MarketSnapshot, zone.source_snapshot_id),
                    candles,
                    cutoff,
                )
                PoiService._update_status(mitigation, candles, cutoff)
            if zone.status == "invalidated":
                inversion_type = "IFVG" if zone.poi_type == "FVG" else "BREAKER"
                invalidation_candle = PoiService._at_time(candles, zone.invalidated_at_utc)
                if invalidation_candle is not None:
                    inverse = PoiService._upsert(
                        db,
                        zone.symbol,
                        zone.timeframe,
                        inversion_type,
                        "bearish" if zone.direction == "bullish" else "bullish",
                        zone.price_low,
                        zone.price_high,
                        invalidation_candle,
                        candles,
                        cutoff,
                    )
                    PoiService._update_status(inverse, candles, cutoff)
        db.commit()
        zones = (
            db.query(PoiZone)
            .filter(PoiZone.symbol == request.symbol, PoiZone.timeframe == request.timeframe)
            .order_by(PoiZone.created_at.desc(), PoiZone.id.desc())
            .all()
        )
        for zone in zones:
            db.refresh(zone)
        return zones

    @staticmethod
    def _upsert(
        db: Session,
        symbol: str,
        timeframe: str,
        poi_type: str,
        direction: str,
        price_low: Decimal,
        price_high: Decimal,
        source: MarketSnapshot,
        candles: list[MarketSnapshot],
        cutoff: datetime,
    ) -> PoiZone:
        zone = (
            db.query(PoiZone)
            .filter(
                PoiZone.symbol == symbol,
                PoiZone.timeframe == timeframe,
                PoiZone.poi_type == poi_type,
                PoiZone.direction == direction,
                PoiZone.source_snapshot_id == source.id,
            )
            .first()
            or PoiZone(
                symbol=symbol,
                timeframe=timeframe,
                poi_type=poi_type,
                direction=direction,
                price_low=price_low,
                price_high=price_high,
                source_snapshot_id=source.id,
                status="active",
                status_reason="POI zone detected; awaiting retracement and reaction.",
                as_of_utc=cutoff,
            )
        )
        zone.price_low = price_low
        zone.price_high = price_high
        zone.as_of_utc = cutoff
        if zone.id is None:
            db.add(zone)
            db.flush()
        PoiService._update_status(zone, candles, cutoff)
        return zone

    @staticmethod
    def _update_status(zone: PoiZone, candles: list[MarketSnapshot], cutoff: datetime) -> None:
        source = next((candle for candle in candles if candle.id == zone.source_snapshot_id), None)
        if source is None:
            return
        subsequent = [
            candle for candle in candles
            if PoiService._utc(source.timestamp_utc) < PoiService._utc(candle.timestamp_utc) <= cutoff
        ]
        zone.status = "active"
        zone.touched_at_utc = None
        zone.reaction_confirmed = False
        zone.invalidated_at_utc = None
        zone.status_reason = "POI zone detected; awaiting retracement and reaction."
        for candle in subsequent:
            invalid = (
                candle.close < zone.price_low
                if zone.direction == "bullish"
                else candle.close > zone.price_high
            )
            if invalid:
                zone.status = "invalidated"
                zone.invalidated_at_utc = candle.timestamp_utc
                zone.status_reason = (
                    f"{zone.poi_type} invalidated by close through its far boundary; "
                    "evaluate inversion POI only after subsequent reaction."
                )
                return
            touched = candle.low <= zone.price_high and candle.high >= zone.price_low
            if touched and zone.touched_at_utc is None:
                zone.touched_at_utc = candle.timestamp_utc
                zone.status = "touched"
                zone.status_reason = f"{zone.poi_type} retracement touched; awaiting directional reaction."
            reaction = (
                touched and candle.close > zone.price_high and candle.close > candle.open
                if zone.direction == "bullish"
                else touched and candle.close < zone.price_low and candle.close < candle.open
            )
            if reaction and not zone.reaction_confirmed:
                zone.status = "validated_retracement"
                zone.touched_at_utc = candle.timestamp_utc
                zone.reaction_confirmed = True
                zone.status_reason = (
                    f"{zone.poi_type} retracement produced {zone.direction} rejection; "
                    "await MSS/CISD confirmation."
                )

    @staticmethod
    def _candles(
        db: Session, symbol: str, timeframe: str, as_of_utc: datetime | None
    ) -> list[MarketSnapshot]:
        cutoff = PoiService._utc(as_of_utc) if as_of_utc else None
        return [
            candle
            for candle in (
                db.query(MarketSnapshot)
                .filter(MarketSnapshot.symbol == symbol, MarketSnapshot.timeframe == timeframe)
                .order_by(MarketSnapshot.timestamp_utc.asc(), MarketSnapshot.id.asc())
                .all()
            )
            if cutoff is None or PoiService._utc(candle.timestamp_utc) <= cutoff
        ]

    @staticmethod
    def _at_time(candles: list[MarketSnapshot], value: datetime | None) -> MarketSnapshot | None:
        if value is None:
            return None
        timestamp = PoiService._utc(value)
        return next((c for c in candles if PoiService._utc(c.timestamp_utc) == timestamp), None)

    @staticmethod
    def _utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)


class ExecutionService:
    READY_QUARTERS = {"Expansion Ready", "Expansion Active"}
    READY_LEDGER = {"active", "continuing"}

    @staticmethod
    def evaluate(db: Session, request: ExecutionEvaluateRequest) -> ExecutionAssessment:
        zones = PoiService.scan(
            db,
            PoiScanRequest(
                symbol=request.symbol,
                timeframe=request.timeframe,
                as_of_utc=request.as_of_utc,
            ),
        )
        dol = db.query(DolAssessment).filter(DolAssessment.symbol == request.symbol).first()
        ledger = (
            db.query(NarrativeLedger)
            .filter(NarrativeLedger.symbol == request.symbol)
            .order_by(NarrativeLedger.created_at.desc(), NarrativeLedger.id.desc())
            .first()
        )
        if dol is None or ledger is None:
            raise ValueError("Active DOL and narrative ledger are required before execution confirmation.")
        market = ExecutionService._latest_market(db, request.symbol, request.timeframe, request.as_of_utc)
        quarter = db.query(QuarterReadinessAssessment).filter(
            QuarterReadinessAssessment.symbol == request.symbol
        ).first()
        mapping = db.query(IrlErlMapping).filter(IrlErlMapping.symbol == request.symbol).first()
        ssmt = (
            db.query(SsmtEvent)
            .order_by(SsmtEvent.as_of_utc.desc(), SsmtEvent.id.desc())
            .first()
            if request.symbol == "XAUUSD"
            else None
        )
        mmxm = db.query(MmxmAssessment).filter(MmxmAssessment.symbol == request.symbol).first()
        quality = db.query(DeliveryQualityAssessment).filter(
            DeliveryQualityAssessment.symbol == request.symbol
        ).first()
        expected_direction = "bullish" if ledger.delivery_direction == "delivery_up" else "bearish"
        poi = ExecutionService._select_poi(
            zones, expected_direction, request.poi_id, ledger.activated_at_utc
        )
        if poi is not None and poi.reaction_confirmed:
            quality = DeliveryQualityService.evaluate(
                db,
                request.symbol,
                request.timeframe,
                request.as_of_utc,
                valid_retracement=True,
                poi_reference=f"{poi.timeframe} {poi.poi_type} #{poi.id}",
            )
        mss, cisd, trigger = ExecutionService._confirmation(
            db, request.symbol, request.timeframe, market, poi, expected_direction
        )
        target = db.get(LiquidityLevel, ledger.target_level_id)
        risk_values = ExecutionService._risk(
            market.close,
            ledger.invalidation_price,
            target.price if target else None,
            ledger.delivery_direction,
            request.minimum_rr,
        )
        blockers = ExecutionService._blockers(
            db, request.symbol, dol, mapping, ssmt, mmxm, ledger, quarter, quality, poi, mss, cisd, risk_values
        )
        status = "Valid Setup" if not blockers else "No Trade"
        setup_context = (
            f"{ledger.delivery_direction} narrative toward {ledger.target_liquidity} with "
            f"defined invalidation at {ledger.invalidation_level}; "
            f"POI is {poi.timeframe} {poi.poi_type} #{poi.id}."
            if poi
            else (
                f"{ledger.delivery_direction} narrative toward {ledger.target_liquidity} with "
                f"defined invalidation at {ledger.invalidation_level}; execution POI is waiting."
            )
        )
        validation_required = (
            "All backend confirmation gates passed; discretionary review required and no order is emitted."
            if not blockers
            else (
                " ".join(blockers)
                + f" Re-evaluate after conditions change; watch target {ledger.target_liquidity} "
                f"and invalidation {ledger.invalidation_level}."
            )
        )
        assessment = ExecutionAssessment(
            symbol=request.symbol,
            timeframe=request.timeframe,
            dol_assessment_id=dol.id,
            narrative_ledger_id=ledger.id,
            delivery_direction=ledger.delivery_direction,
            setup_context=setup_context,
            poi_confirmation="Waiting.",
            trigger_confirmation="Waiting.",
            invalidation_price=ledger.invalidation_price,
            minimum_rr=request.minimum_rr,
            risk_status="waiting",
            execution_status="No Trade",
            no_trade_reason="Waiting for evaluation.",
            validation_required="Waiting.",
            as_of_utc=market.timestamp_utc,
        )
        assessment.timeframe = request.timeframe
        assessment.dol_assessment_id = dol.id
        assessment.narrative_ledger_id = ledger.id
        assessment.quarter_readiness_id = quarter.id if quarter else None
        assessment.delivery_quality_assessment_id = quality.id if quality else None
        assessment.poi_zone_id = poi.id if poi else None
        assessment.delivery_direction = ledger.delivery_direction
        assessment.setup_context = setup_context
        assessment.poi_confirmation = (
            f"{poi.poi_type} #{poi.id} {poi.status}: {poi.status_reason}"
            if poi else "No aligned validated POI detected on execution timeframe."
        )
        assessment.mss_confirmed = mss
        assessment.cisd_confirmed = cisd
        assessment.trigger_confirmation = trigger
        assessment.entry_reference = market.close
        assessment.invalidation_price = ledger.invalidation_price
        assessment.target_price = target.price if target else None
        assessment.risk_points = risk_values["risk"]
        assessment.reward_points = risk_values["reward"]
        assessment.rr_ratio = risk_values["rr"]
        assessment.minimum_rr = request.minimum_rr
        assessment.risk_status = risk_values["status"]
        assessment.execution_status = status
        assessment.no_trade_reason = (
            "None - confirmation gates passed; this is setup context only and no order is emitted."
            if not blockers else " ".join(blockers)
        )
        assessment.validation_required = validation_required
        assessment.as_of_utc = market.timestamp_utc
        db.add(assessment)
        db.commit()
        db.refresh(assessment)
        return assessment

    @staticmethod
    def get_current(db: Session, symbol: str) -> ExecutionAssessment | None:
        return (
            db.query(ExecutionAssessment)
            .filter(ExecutionAssessment.symbol == symbol)
            .order_by(ExecutionAssessment.as_of_utc.desc(), ExecutionAssessment.id.desc())
            .first()
        )

    @staticmethod
    def _select_poi(
        zones: list[PoiZone],
        direction: str,
        poi_id: int | None,
        eligible_after: datetime,
    ) -> PoiZone | None:
        def eligible(zone: PoiZone) -> bool:
            return (
                zone.direction == direction
                and zone.touched_at_utc is not None
                and PoiService._utc(zone.touched_at_utc) >= PoiService._utc(eligible_after)
            )

        if poi_id is not None:
            return next((zone for zone in zones if zone.id == poi_id and eligible(zone)), None)
        return next(
            (
                zone for zone in zones
                if eligible(zone) and zone.status == "validated_retracement"
            ),
            None,
        )

    @staticmethod
    def _confirmation(
        db: Session,
        symbol: str,
        timeframe: str,
        market: MarketSnapshot,
        poi: PoiZone | None,
        direction: str,
    ) -> tuple[bool, bool, str]:
        if poi is None or not poi.reaction_confirmed or poi.touched_at_utc is None:
            return False, False, "Waiting - valid POI retracement and rejection are required first."
        candles = PoiService._candles(db, symbol, timeframe, market.timestamp_utc)
        touch_time = PoiService._utc(poi.touched_at_utc)
        before = [c for c in candles if PoiService._utc(c.timestamp_utc) < touch_time][-5:]
        after = [c for c in candles if PoiService._utc(c.timestamp_utc) > touch_time]
        if not before or not after:
            return False, False, "Waiting - post-POI displacement is not available."
        boundary = (
            max(candle.high for candle in before)
            if direction == "bullish"
            else min(candle.low for candle in before)
        )
        trigger = next(
            (
                candle for candle in after
                if ExecutionService._body_ratio(candle) >= Decimal("0.55")
                and (
                    candle.close > boundary and candle.close > candle.open
                    if direction == "bullish"
                    else candle.close < boundary and candle.close < candle.open
                )
            ),
            None,
        )
        if trigger is None:
            return False, False, f"Waiting - no strong {direction} close beyond structure {boundary}."
        return (
            True,
            True,
            f"MSS and CISD confirmed by {timeframe} close at {trigger.close} beyond structure {boundary} after POI reaction.",
        )

    @staticmethod
    def _risk(
        entry: Decimal,
        invalidation: Decimal,
        target: Decimal | None,
        direction: str,
        minimum_rr: Decimal,
    ) -> dict[str, Decimal | str | None]:
        if target is None:
            return {"risk": None, "reward": None, "rr": None, "status": "missing_target"}
        risk = entry - invalidation if direction == "delivery_up" else invalidation - entry
        reward = target - entry if direction == "delivery_up" else entry - target
        if risk <= 0 or reward <= 0:
            return {"risk": risk, "reward": reward, "rr": None, "status": "invalid_geometry"}
        rr = reward / risk
        return {
            "risk": risk,
            "reward": reward,
            "rr": rr,
            "status": "sufficient" if rr >= minimum_rr else "below_minimum",
        }

    @staticmethod
    def _blockers(
        db: Session,
        symbol: str,
        dol: DolAssessment,
        mapping: IrlErlMapping | None,
        ssmt: SsmtEvent | None,
        mmxm: MmxmAssessment | None,
        ledger: NarrativeLedger,
        quarter: QuarterReadinessAssessment | None,
        quality: DeliveryQualityAssessment | None,
        poi: PoiZone | None,
        mss: bool,
        cisd: bool,
        risk: dict[str, Decimal | str | None],
    ) -> list[str]:
        blockers: list[str] = []
        if symbol != "XAUUSD":
            blockers.append("No Trade - XAGUSD is confirmation context only; execution setup is restricted to XAUUSD.")
        if dol.lifecycle_status not in {"Active", "Shift Confirmed"}:
            blockers.append(f"No Trade - DOL status is {dol.lifecycle_status}.")
        if mapping is None or mapping.mapping_status != "aligned":
            blockers.append("No Trade - direction liquidity mapping is not aligned to active DOL.")
        expected_ssmt = "bullish" if ledger.delivery_direction == "delivery_up" else "bearish"
        if (
            ssmt is None
            or ssmt.ssmt_status != f"valid_{expected_ssmt}"
            or ssmt.ssmt_dol_alignment != "aligned"
        ):
            blockers.append("No Trade - valid XAU/XAG SSMT confluence is not aligned to active delivery.")
        if mmxm is None:
            blockers.append("No Trade - MMXM/session timing context has not been evaluated.")
        elif mmxm.timing_conflict.startswith("Timing conflict"):
            blockers.append(f"No Trade - {mmxm.timing_conflict}")
        if ledger.continuation_status not in ExecutionService.READY_LEDGER or ledger.reset_required:
            blockers.append(f"No Trade - narrative status is {ledger.continuation_status}.")
        if (
            quarter is None
            or quarter.quarter_status not in ExecutionService.READY_QUARTERS
            or not quarter.quarter_execution_allowed
        ):
            blockers.append("No Trade - quarter is not ready for execution confirmation.")
        if quality is None or quality.expansion_status != "valid":
            blockers.append("No Trade - expansion quality is not valid with confirmed retracement.")
        if poi is None or poi.status != "validated_retracement":
            blockers.append("No Trade - no validated OB/FVG/IFVG/Breaker/Mitigation POI retracement exists.")
        if not mss or not cisd:
            blockers.append("No Trade - CISD/MSS has not been confirmed on the execution timeframe.")
        if risk["status"] != "sufficient":
            blockers.append("No Trade - minimum RR policy is not satisfied.")
        news = NewsCatalystServiceCurrent.current(db, dol.symbol)
        if news is not None and news.impact == "high" and news.catalyst_status in {
            "waiting_release", "inconclusive"
        }:
            blockers.append(f"No Trade - news catalyst status is {news.catalyst_status}.")
        return blockers

    @staticmethod
    def _latest_market(
        db: Session, symbol: str, timeframe: str, as_of_utc: datetime | None
    ) -> MarketSnapshot:
        candles = PoiService._candles(db, symbol, timeframe, as_of_utc)
        if not candles:
            raise ValueError(f"No {timeframe} market snapshots found for {symbol}.")
        return candles[-1]

    @staticmethod
    def _body_ratio(candle: MarketSnapshot) -> Decimal:
        candle_range = candle.high - candle.low
        return Decimal(0) if candle_range <= 0 else abs(candle.close - candle.open) / candle_range


class NewsCatalystServiceCurrent:
    @staticmethod
    def current(db: Session, symbol: str) -> NewsCatalystEvent | None:
        return (
            db.query(NewsCatalystEvent)
            .filter(NewsCatalystEvent.symbol == symbol)
            .order_by(NewsCatalystEvent.scheduled_at_utc.desc(), NewsCatalystEvent.id.desc())
            .first()
        )
