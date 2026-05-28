import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.liquidity_level import LiquidityLevel
from app.schemas.irl_erl import (
    ImbalanceZoneResponse,
    IrlErlEvaluateRequest,
    IrlErlMappingResponse,
    MappedLiquidityLevel,
    MappingLayerResponse,
    MappingStatus,
)
from app.schemas.market import VALID_SYMBOLS
from app.services.irl_erl_service import (
    ImbalanceZone,
    IrlErlService,
    MappingLayer,
    MappingResult,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/direction-liquidity", tags=["direction-liquidity"])


@router.post("/evaluate", response_model=IrlErlMappingResponse)
def evaluate_irl_erl(
    request: IrlErlEvaluateRequest,
    db: Session = Depends(get_db),
) -> IrlErlMappingResponse:
    try:
        result = IrlErlService.evaluate(db, request.symbol)
        return _response(result)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Failed to evaluate IRL/ERL direction liquidity")
        raise HTTPException(status_code=500, detail="Failed to evaluate IRL/ERL mapping") from exc


@router.get("/current/{symbol}", response_model=IrlErlMappingResponse)
def current_irl_erl(symbol: str, db: Session = Depends(get_db)) -> IrlErlMappingResponse:
    symbol = symbol.upper()
    if symbol not in VALID_SYMBOLS:
        raise HTTPException(status_code=422, detail=f"Symbol must be one of {VALID_SYMBOLS}")
    result = IrlErlService.get_current(db, symbol)
    if result is None:
        raise HTTPException(status_code=404, detail="IRL/ERL mapping not found")
    return _response(result)


def _response(result: MappingResult) -> IrlErlMappingResponse:
    mapping = result.mapping
    execution_status = (
        "Narrative Ready - wait for later execution confirmation layers"
        if mapping.mapping_status == MappingStatus.ALIGNED.value
        else "No Trade - direction liquidity is not fully aligned"
    )
    return IrlErlMappingResponse(
        id=mapping.id,
        symbol=mapping.symbol,
        dol_lifecycle_status=result.dol.lifecycle_status,
        delivery_direction=result.dol.delivery_direction,
        direction_flow=mapping.direction_flow,
        mapping_status=mapping.mapping_status,
        layers=[_layer_response(layer) for layer in result.layers],
        conflict_flags=result.conflicts,
        limitations=result.limitations,
        status_reason=mapping.status_reason,
        execution_status=execution_status,
        imbalance=_imbalance_response(result.imbalance),
        imbalance_role=result.imbalance_role,
        as_of_utc=mapping.as_of_utc,
        updated_at=mapping.updated_at,
    )


def _layer_response(layer: MappingLayer) -> MappingLayerResponse:
    return MappingLayerResponse(
        narrative_timeframe=layer.narrative_timeframe,
        direction_timeframes=layer.direction_timeframes,
        irl=_level_response(layer.irl, "IRL", layer.reason),
        erl=_level_response(layer.erl, "ERL", layer.reason),
        direction_liquidity=layer.direction_liquidity,
        status=layer.status,
        reason=layer.reason,
        imbalance=_imbalance_response(layer.imbalance),
    )


def _imbalance_response(zone: ImbalanceZone | None) -> ImbalanceZoneResponse | None:
    if zone is None:
        return None
    return ImbalanceZoneResponse(
        poi_id=zone.poi_id,
        poi_type=zone.poi_type,
        timeframe=zone.timeframe,
        direction=zone.direction,
        price_low=zone.price_low,
        price_high=zone.price_high,
        status=zone.status,
    )


def _level_response(
    level: LiquidityLevel | None,
    role: str,
    basis: str,
) -> MappedLiquidityLevel | None:
    if level is None:
        return None
    return MappedLiquidityLevel(
        level_id=level.id,
        level_type=level.level_type,
        role=role,
        liquidity_side=level.liquidity_side,
        price=level.price,
        status=level.status,
        basis=basis,
    )
