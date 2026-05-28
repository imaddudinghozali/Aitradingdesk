import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.liquidity import (
    LiquidityLevelResponse,
    LiquidityMapResponse,
    LiquidityRefreshRequest,
    LiquidityStatus,
    LiquidityStatusUpdate,
)
from app.schemas.market import VALID_SYMBOLS
from app.services.liquidity_service import LiquidityService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/liquidity", tags=["liquidity"])


@router.post("/refresh", response_model=LiquidityMapResponse)
def refresh_liquidity_levels(
    request: LiquidityRefreshRequest,
    db: Session = Depends(get_db),
) -> LiquidityMapResponse:
    try:
        as_of_utc, levels, missing = LiquidityService.refresh_levels(db, request)
        return LiquidityMapResponse(
            symbol=request.symbol,
            as_of_utc=as_of_utc,
            levels=levels,
            missing_level_types=missing,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Failed to refresh liquidity levels")
        raise HTTPException(status_code=500, detail="Failed to refresh liquidity levels") from exc


@router.get("/levels", response_model=list[LiquidityLevelResponse])
def get_liquidity_levels(
    symbol: str = Query("XAUUSD", description="XAUUSD or XAGUSD"),
    status: LiquidityStatus | None = Query(None),
    db: Session = Depends(get_db),
) -> list[LiquidityLevelResponse]:
    symbol = symbol.upper()
    if symbol not in VALID_SYMBOLS:
        raise HTTPException(status_code=422, detail=f"Symbol must be one of {VALID_SYMBOLS}")
    return LiquidityService.list_levels(db, symbol, status)


@router.patch("/levels/{level_id}/status", response_model=LiquidityLevelResponse)
def update_liquidity_status(
    level_id: int,
    update: LiquidityStatusUpdate,
    db: Session = Depends(get_db),
) -> LiquidityLevelResponse:
    level = LiquidityService.update_status(db, level_id, update)
    if level is None:
        raise HTTPException(status_code=404, detail="Liquidity level not found")
    return level
