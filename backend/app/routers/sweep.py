import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.market import VALID_SYMBOLS
from app.schemas.sweep import SweepEventResponse, SweepScanRequest, SweepScanResponse, SweepStatus
from app.services.sweep_service import SweepService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/sweeps", tags=["sweeps"])


@router.post("/scan", response_model=SweepScanResponse)
def scan_sweeps(
    request: SweepScanRequest,
    db: Session = Depends(get_db),
) -> SweepScanResponse:
    try:
        as_of_utc, events, waiting_reasons = SweepService.scan(db, request)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Failed to scan sweep events")
        raise HTTPException(status_code=500, detail="Failed to scan sweep events") from exc

    confirmed_statuses = {
        SweepStatus.VALID_SWEEP.value,
        SweepStatus.TURTLE_SOUP.value,
        SweepStatus.MANIPULATION_SWEEP.value,
    }
    no_trade_required = bool(waiting_reasons) or not any(
        event.sweep_status in confirmed_statuses for event in events
    )
    return SweepScanResponse(
        symbol=request.symbol,
        timeframe=request.timeframe,
        as_of_utc=as_of_utc,
        events=events,
        no_trade_required=no_trade_required,
        waiting_reasons=waiting_reasons,
    )


@router.get("/events", response_model=list[SweepEventResponse])
def get_sweep_events(
    symbol: str = Query("XAUUSD", description="XAUUSD or XAGUSD"),
    status: SweepStatus | None = Query(None),
    db: Session = Depends(get_db),
) -> list[SweepEventResponse]:
    symbol = symbol.upper()
    if symbol not in VALID_SYMBOLS:
        raise HTTPException(status_code=422, detail=f"Symbol must be one of {VALID_SYMBOLS}")
    return SweepService.list_events(db, symbol, status)
