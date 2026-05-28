from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.dol_assessment import DolAssessment
from app.models.irl_erl_mapping import IrlErlMapping
from app.models.liquidity_level import LiquidityLevel
from app.models.market_snapshot import MarketSnapshot
from app.models.poi_zone import PoiZone
from app.schemas.dol import DeliveryDirection, DolLifecycle
from app.schemas.irl_erl import MappingStatus
from app.schemas.liquidity import LiquidityStatus


@dataclass(frozen=True)
class ImbalanceZone:
    poi_id: int
    poi_type: str
    timeframe: str
    direction: str
    price_low: Decimal
    price_high: Decimal
    status: str


@dataclass(frozen=True)
class MappingLayer:
    narrative_timeframe: str
    direction_timeframes: list[str]
    irl: LiquidityLevel | None
    erl: LiquidityLevel | None
    direction_liquidity: str
    status: MappingStatus
    reason: str
    imbalance: ImbalanceZone | None = None


@dataclass(frozen=True)
class MappingResult:
    mapping: IrlErlMapping
    dol: DolAssessment
    layers: list[MappingLayer]
    conflicts: list[str]
    limitations: list[str]
    imbalance: ImbalanceZone | None = None
    imbalance_role: str | None = None


class IrlErlService:
    READY_DOL = {
        DolLifecycle.ACTIVE.value,
        DolLifecycle.SHIFT_CONFIRMED.value,
    }
    LIMITATIONS = [
        "Intraday IRL currently uses completed session range proxies; H1/H4 swing IRL detection is not yet modeled.",
        "Previous-news liquidity requires a news-event data source and is not modeled yet.",
        "Imbalance flow uses unmitigated FVG/OB POIs on H1/H4; intra-bar imbalance still requires execution-layer review.",
    ]
    IMBALANCE_TIMEFRAMES = ("H4", "H1")
    OPEN_POI_STATUSES = {"pending", "validated_retracement"}

    @staticmethod
    def evaluate(db: Session, symbol: str) -> MappingResult:
        dol = db.query(DolAssessment).filter(DolAssessment.symbol == symbol).first()
        if dol is None:
            raise ValueError("DOL assessment not found. Evaluate DOL before IRL/ERL mapping.")

        levels = {
            level.level_type: level
            for level in db.query(LiquidityLevel)
            .filter(
                LiquidityLevel.symbol == symbol,
                LiquidityLevel.status != LiquidityStatus.INVALIDATED.value,
            )
            .all()
        }
        direction = (
            DeliveryDirection(dol.delivery_direction)
            if dol.delivery_direction
            else None
        )
        side = IrlErlService._side(direction)
        dol_ready = dol.lifecycle_status in IrlErlService.READY_DOL
        primary = db.get(LiquidityLevel, dol.primary_level_id) if dol.primary_level_id else None
        engineered = (
            db.get(LiquidityLevel, dol.engineered_level_id)
            if dol.engineered_level_id
            else None
        )
        conflicts: list[str] = []
        if primary and side and primary.liquidity_side != side:
            conflicts.append(
                f"Primary DOL {primary.level_type} is {primary.liquidity_side}, "
                f"but direction {direction.value} requires {side}."
            )

        monthly_irl = IrlErlService._level(levels, "PMH", "PML", side)
        monthly_erl = IrlErlService._level(levels, "PYH", "PYL", side)
        weekly_irl = IrlErlService._level(levels, "PDH", "PDL", side)
        weekly_erl = IrlErlService._level(levels, "PWH", "PWL", side)
        daily_erl = weekly_irl
        daily_irl = IrlErlService._intraday_irl(levels, side)

        current_price = IrlErlService._latest_price(db, symbol)
        imbalance = IrlErlService._find_imbalance(
            db, symbol, side, primary, current_price
        )
        imbalance_role = IrlErlService._imbalance_role(
            imbalance, side, primary, engineered, current_price
        )

        layers = [
            IrlErlService._layer(
                "Monthly",
                ["Weekly", "Daily"],
                monthly_irl,
                monthly_erl,
                side,
                dol_ready,
                conflicts,
                "Previous-month liquidity is treated as monthly IRL and previous-year liquidity as monthly ERL.",
            ),
            IrlErlService._layer(
                "Weekly",
                ["Daily", "H4", "H1"],
                weekly_irl,
                weekly_erl,
                side,
                dol_ready,
                conflicts,
                "Previous-day liquidity is treated as weekly IRL and previous-week liquidity as weekly ERL.",
            ),
            IrlErlService._layer(
                "Daily",
                ["H4", "H1", "M15", "M5"],
                daily_irl,
                daily_erl,
                side,
                dol_ready,
                conflicts,
                "Completed London/Asia range is a provisional intraday IRL; previous-day liquidity is daily ERL.",
                imbalance=imbalance if imbalance_role == "source_imbalance" else None,
            ),
        ]
        direction_flow = IrlErlService._direction_flow(
            engineered,
            primary,
            weekly_irl,
            daily_irl,
            imbalance,
            imbalance_role,
        )
        overall = IrlErlService._overall_status(dol_ready, layers, conflicts)
        reason = IrlErlService._status_reason(overall, direction_flow, dol)

        mapping = db.query(IrlErlMapping).filter(IrlErlMapping.symbol == symbol).first()
        mapping = mapping or IrlErlMapping(symbol=symbol, dol_assessment_id=dol.id)
        mapping.dol_assessment_id = dol.id
        mapping.direction_flow = direction_flow
        mapping.mapping_status = overall.value
        mapping.weekly_irl_level_id = weekly_irl.id if weekly_irl else None
        mapping.weekly_erl_level_id = weekly_erl.id if weekly_erl else None
        mapping.daily_irl_level_id = daily_irl.id if daily_irl else None
        mapping.daily_erl_level_id = daily_erl.id if daily_erl else None
        mapping.status_reason = reason
        mapping.conflict_summary = " ".join(conflicts) if conflicts else None
        mapping.as_of_utc = dol.as_of_utc
        if mapping.id is None:
            db.add(mapping)
        db.commit()
        db.refresh(mapping)
        return MappingResult(
            mapping,
            dol,
            layers,
            conflicts,
            IrlErlService.LIMITATIONS,
            imbalance=imbalance,
            imbalance_role=imbalance_role,
        )

    @staticmethod
    def get_current(db: Session, symbol: str) -> MappingResult | None:
        mapping = db.query(IrlErlMapping).filter(IrlErlMapping.symbol == symbol).first()
        if mapping is None:
            return None
        dol = db.get(DolAssessment, mapping.dol_assessment_id)
        if dol is None:
            return None
        conflicts = [mapping.conflict_summary] if mapping.conflict_summary else []
        side = IrlErlService._side(
            DeliveryDirection(dol.delivery_direction)
            if dol.delivery_direction
            else None
        )
        dol_ready = dol.lifecycle_status in IrlErlService.READY_DOL
        levels = {
            level.level_type: level
            for level in db.query(LiquidityLevel)
            .filter(LiquidityLevel.symbol == dol.symbol)
            .all()
        }
        monthly_irl = IrlErlService._level(levels, "PMH", "PML", side)
        monthly_erl = IrlErlService._level(levels, "PYH", "PYL", side)
        weekly_irl = db.get(LiquidityLevel, mapping.weekly_irl_level_id) if mapping.weekly_irl_level_id else None
        weekly_erl = db.get(LiquidityLevel, mapping.weekly_erl_level_id) if mapping.weekly_erl_level_id else None
        daily_irl = db.get(LiquidityLevel, mapping.daily_irl_level_id) if mapping.daily_irl_level_id else None
        daily_erl = db.get(LiquidityLevel, mapping.daily_erl_level_id) if mapping.daily_erl_level_id else None
        layers = [
            IrlErlService._layer(
                "Monthly",
                ["Weekly", "Daily"],
                monthly_irl,
                monthly_erl,
                side,
                dol_ready,
                conflicts,
                "Previous-month liquidity is treated as monthly IRL and previous-year liquidity as monthly ERL.",
            ),
            IrlErlService._layer(
                "Weekly",
                ["Daily", "H4", "H1"],
                weekly_irl,
                weekly_erl,
                side,
                dol_ready,
                conflicts,
                "Previous-day liquidity is treated as weekly IRL and previous-week liquidity as weekly ERL.",
            ),
            IrlErlService._layer(
                "Daily",
                ["H4", "H1", "M15", "M5"],
                daily_irl,
                daily_erl,
                side,
                dol_ready,
                conflicts,
                "Completed London/Asia range is a provisional intraday IRL; previous-day liquidity is daily ERL.",
            ),
        ]
        current_price = IrlErlService._latest_price(db, dol.symbol)
        primary = db.get(LiquidityLevel, dol.primary_level_id) if dol.primary_level_id else None
        engineered = db.get(LiquidityLevel, dol.engineered_level_id) if dol.engineered_level_id else None
        imbalance = IrlErlService._find_imbalance(db, dol.symbol, side, primary, current_price)
        imbalance_role = IrlErlService._imbalance_role(
            imbalance, side, primary, engineered, current_price
        )
        if layers and imbalance_role == "source_imbalance":
            tail = layers[-1]
            layers[-1] = MappingLayer(
                narrative_timeframe=tail.narrative_timeframe,
                direction_timeframes=tail.direction_timeframes,
                irl=tail.irl,
                erl=tail.erl,
                direction_liquidity=tail.direction_liquidity,
                status=tail.status,
                reason=tail.reason,
                imbalance=imbalance,
            )
        return MappingResult(
            mapping,
            dol,
            layers,
            conflicts,
            IrlErlService.LIMITATIONS,
            imbalance=imbalance,
            imbalance_role=imbalance_role,
        )

    @staticmethod
    def _side(direction: DeliveryDirection | None) -> str | None:
        if direction == DeliveryDirection.UP:
            return "BSL"
        if direction == DeliveryDirection.DOWN:
            return "SSL"
        return None

    @staticmethod
    def _level(
        levels: dict[str, LiquidityLevel],
        high_type: str,
        low_type: str,
        side: str | None,
    ) -> LiquidityLevel | None:
        if side == "BSL":
            return levels.get(high_type)
        if side == "SSL":
            return levels.get(low_type)
        return None

    @staticmethod
    def _intraday_irl(
        levels: dict[str, LiquidityLevel],
        side: str | None,
    ) -> LiquidityLevel | None:
        if side == "BSL":
            return levels.get("LONDON_HIGH") or levels.get("ASIA_HIGH")
        if side == "SSL":
            return levels.get("LONDON_LOW") or levels.get("ASIA_LOW")
        return None

    @staticmethod
    def _layer(
        narrative: str,
        timeframes: list[str],
        irl: LiquidityLevel | None,
        erl: LiquidityLevel | None,
        side: str | None,
        dol_ready: bool,
        conflicts: list[str],
        basis: str,
        imbalance: ImbalanceZone | None = None,
    ) -> MappingLayer:
        has_irl = irl is not None or imbalance is not None
        if conflicts:
            status = MappingStatus.CONFLICT
            reason = f"{basis} Direction conflicts with primary DOL."
        elif not dol_ready:
            status = MappingStatus.WAITING_DOL
            reason = f"{basis} DOL lifecycle is not ready for directional mapping."
        elif has_irl and erl:
            status = MappingStatus.ALIGNED
            if imbalance is not None and irl is None:
                reason = (
                    f"{basis} ERL is available; intraday IRL substituted by unmitigated "
                    f"{imbalance.timeframe} {imbalance.poi_type} ({imbalance.direction})."
                )
            elif imbalance is not None:
                reason = (
                    f"{basis} Both IRL and ERL are available; an unmitigated "
                    f"{imbalance.timeframe} {imbalance.poi_type} reinforces the imbalance source."
                )
            else:
                reason = f"{basis} Both IRL and ERL are available in the DOL direction."
        else:
            status = MappingStatus.PARTIAL
            reason = f"{basis} One or more directional liquidity levels are unavailable."
        return MappingLayer(
            narrative_timeframe=narrative,
            direction_timeframes=timeframes,
            irl=irl,
            erl=erl,
            direction_liquidity=IrlErlService._direction_label(side),
            status=status,
            reason=reason,
            imbalance=imbalance,
        )

    @staticmethod
    def _direction_label(side: str | None) -> str:
        if side == "BSL":
            return "buyside"
        if side == "SSL":
            return "sellside"
        return "undetermined"

    @staticmethod
    def _direction_flow(
        engineered: LiquidityLevel | None,
        primary: LiquidityLevel | None,
        weekly_irl: LiquidityLevel | None,
        daily_irl: LiquidityLevel | None,
        imbalance: ImbalanceZone | None = None,
        imbalance_role: str | None = None,
    ) -> str:
        if imbalance_role == "source_imbalance" and primary is not None:
            return "imbalance -> liquidity"
        if imbalance_role == "target_imbalance":
            return "liquidity -> imbalance"
        source_role = IrlErlService._role_for_flow(engineered, as_target=False)
        target_role = IrlErlService._role_for_flow(primary, as_target=True)
        if source_role == "ERL" and target_role == "ERL" and (weekly_irl or daily_irl):
            return "ERL -> IRL -> ERL"
        if source_role and target_role and source_role != target_role:
            return f"{source_role} -> {target_role}"
        if source_role == "IRL" and target_role == "IRL":
            return "liquidity -> liquidity"
        if target_role == "ERL" and (weekly_irl or daily_irl):
            return "IRL -> ERL"
        return "liquidity -> liquidity"

    @staticmethod
    def _role_for_flow(level: LiquidityLevel | None, as_target: bool) -> str | None:
        if level is None:
            return None
        if level.level_type in {"PWH", "PWL", "PMH", "PML", "PYH", "PYL", "NEWS_HIGH", "NEWS_LOW"}:
            return "ERL"
        if level.level_type in {"PDH", "PDL"}:
            return "ERL" if as_target else "IRL"
        return "IRL"

    @staticmethod
    def _overall_status(
        dol_ready: bool,
        layers: list[MappingLayer],
        conflicts: list[str],
    ) -> MappingStatus:
        if conflicts:
            return MappingStatus.CONFLICT
        if not dol_ready:
            return MappingStatus.WAITING_DOL
        if all(layer.status == MappingStatus.ALIGNED for layer in layers):
            return MappingStatus.ALIGNED
        return MappingStatus.PARTIAL

    @staticmethod
    def _status_reason(
        status: MappingStatus,
        flow: str,
        dol: DolAssessment,
    ) -> str:
        if status == MappingStatus.ALIGNED:
            return (
                f"Direction Liquidity {flow} is aligned with active DOL "
                f"({dol.delivery_direction}) across available weekly and daily layers."
            )
        if status == MappingStatus.WAITING_DOL:
            return "IRL/ERL levels are mapped provisionally, but DOL is not active or shift-confirmed; No Trade."
        if status == MappingStatus.CONFLICT:
            return "IRL/ERL direction conflicts with primary DOL; No Trade until conflict is resolved."
        return f"Direction Liquidity {flow} is partially mapped; missing levels prevent full multi-timeframe confirmation."

    @staticmethod
    def _latest_price(db: Session, symbol: str) -> Decimal | None:
        snapshot = (
            db.query(MarketSnapshot)
            .filter(MarketSnapshot.symbol == symbol)
            .order_by(MarketSnapshot.timestamp_utc.desc())
            .first()
        )
        return snapshot.close if snapshot else None

    @staticmethod
    def _find_imbalance(
        db: Session,
        symbol: str,
        side: str | None,
        primary: LiquidityLevel | None,
        current_price: Decimal | None,
    ) -> ImbalanceZone | None:
        """Locate the most relevant unmitigated H1/H4 FVG/OB that sits between
        current price and the DOL primary target, in the DOL direction.
        """
        if side is None or current_price is None or primary is None:
            return None
        direction = "bullish" if side == "BSL" else "bearish"
        target_price = primary.price
        candidates = (
            db.query(PoiZone)
            .filter(
                PoiZone.symbol == symbol,
                PoiZone.timeframe.in_(IrlErlService.IMBALANCE_TIMEFRAMES),
                PoiZone.poi_type.in_(("FVG", "OB")),
                PoiZone.direction == direction,
                PoiZone.status.in_(IrlErlService.OPEN_POI_STATUSES),
            )
            .all()
        )
        if not candidates:
            return None

        def _within_band(zone: PoiZone) -> bool:
            if direction == "bullish":
                return zone.price_high <= target_price and zone.price_high <= current_price
            return zone.price_low >= target_price and zone.price_low >= current_price

        relevant = [zone for zone in candidates if _within_band(zone)]
        if not relevant:
            return None

        def _proximity(zone: PoiZone) -> Decimal:
            mid = (zone.price_high + zone.price_low) / 2
            return abs(current_price - mid)

        # Prefer H4 over H1; closest mid to current price wins
        relevant.sort(key=lambda z: (0 if z.timeframe == "H4" else 1, _proximity(z)))
        chosen = relevant[0]
        return ImbalanceZone(
            poi_id=chosen.id,
            poi_type=chosen.poi_type,
            timeframe=chosen.timeframe,
            direction=chosen.direction,
            price_low=chosen.price_low,
            price_high=chosen.price_high,
            status=chosen.status,
        )

    @staticmethod
    def _imbalance_role(
        imbalance: ImbalanceZone | None,
        side: str | None,
        primary: LiquidityLevel | None,
        engineered: LiquidityLevel | None,
        current_price: Decimal | None,
    ) -> str | None:
        """Classify the imbalance as source (`imbalance -> liquidity`) or
        target (`liquidity -> imbalance`).
        """
        if imbalance is None or side is None or current_price is None:
            return None
        if side == "BSL":
            if primary is not None and current_price < primary.price:
                return "source_imbalance"
            if engineered is not None and getattr(engineered, "status", None) == LiquidityStatus.TAKEN.value:
                return "target_imbalance"
            return "source_imbalance"
        if side == "SSL":
            if primary is not None and current_price > primary.price:
                return "source_imbalance"
            if engineered is not None and getattr(engineered, "status", None) == LiquidityStatus.TAKEN.value:
                return "target_imbalance"
            return "source_imbalance"
        return None
