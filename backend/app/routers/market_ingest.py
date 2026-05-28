"""Live market data ingestion + scheduler control endpoints."""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.schemas.ingestion import (
    IngestionRunRequest,
    IngestionRunResult,
    SchedulerControlRequest,
    SchedulerStatus,
)
from app.services.market_ingestion_service import (
    IngestionOutcome,
    MarketIngestionService,
)
from app.services.market_providers import get_provider
from app.services.market_providers.base import ProviderError
from app.services.market_scheduler import get_scheduler

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/market/ingest", tags=["market-ingest"])


def _resolve_symbols(request: IngestionRunRequest) -> list[str]:
    if request.symbols:
        return request.symbols
    settings = get_settings()
    return [s.strip().upper() for s in (settings.market_ingest_symbols or "").split(",") if s.strip()]


def _resolve_timeframes(request: IngestionRunRequest) -> list[str]:
    if request.timeframes:
        return request.timeframes
    settings = get_settings()
    return [t.strip().upper() for t in (settings.market_ingest_timeframes or "").split(",") if t.strip()]


@router.post("/run", response_model=list[IngestionRunResult])
def run_ingestion(
    request: IngestionRunRequest,
    db: Session = Depends(get_db),
) -> list[IngestionOutcome]:
    symbols = _resolve_symbols(request)
    timeframes = _resolve_timeframes(request)
    if not symbols or not timeframes:
        raise HTTPException(
            status_code=422,
            detail="symbols and timeframes must be provided (request body or env defaults).",
        )
    try:
        provider = get_provider(request.provider)
    except ProviderError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return MarketIngestionService.run_batch(
        db,
        provider,
        symbols,
        timeframes,
        start_utc=request.start_utc,
        end_utc=request.end_utc,
        limit=request.limit,
    )


@router.get("/runs", response_model=list[IngestionRunResult])
def list_runs(limit: int = 50, db: Session = Depends(get_db)) -> Any:
    if limit < 1 or limit > 500:
        raise HTTPException(status_code=422, detail="limit must be between 1 and 500")
    return MarketIngestionService.recent_runs(db, limit=limit)


@router.get("/runs/latest/{symbol}/{timeframe}", response_model=IngestionRunResult)
def latest_run(symbol: str, timeframe: str, db: Session = Depends(get_db)) -> Any:
    run = MarketIngestionService.latest_run(db, symbol, timeframe)
    if run is None:
        raise HTTPException(status_code=404, detail="No ingestion run recorded yet")
    return run


@router.post("/scheduler/start", response_model=SchedulerStatus)
async def scheduler_start(request: SchedulerControlRequest) -> SchedulerStatus:
    scheduler = get_scheduler()
    try:
        await scheduler.start(
            provider_name=request.provider,
            symbols=request.symbols or None,
            timeframes=request.timeframes or None,
            interval_seconds=request.interval_seconds,
        )
    except (RuntimeError, ProviderError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return SchedulerStatus(**scheduler.status())


@router.post("/scheduler/stop", response_model=SchedulerStatus)
async def scheduler_stop() -> SchedulerStatus:
    scheduler = get_scheduler()
    await scheduler.stop()
    return SchedulerStatus(**scheduler.status())


@router.get("/scheduler/status", response_model=SchedulerStatus)
def scheduler_status() -> SchedulerStatus:
    return SchedulerStatus(**get_scheduler().status())
