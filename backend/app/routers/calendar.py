"""Economic-calendar endpoints."""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.calendar import (
    CalendarRefreshRequest,
    CalendarRefreshResponse,
    CalendarSyncRequest,
    CalendarSyncResponse,
    EconomicEventResponse,
)
from app.schemas.ingestion import SchedulerControlRequest, SchedulerStatus
from app.services.calendar_providers import get_calendar_provider
from app.services.calendar_providers.base import CalendarProviderError
from app.services.calendar_scheduler import get_calendar_scheduler
from app.services.calendar_service import CalendarService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/calendar", tags=["calendar"])


@router.post("/refresh", response_model=CalendarRefreshResponse)
def refresh_calendar(
    request: CalendarRefreshRequest,
    db: Session = Depends(get_db),
) -> Any:
    try:
        provider = get_calendar_provider(request.provider)
    except CalendarProviderError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    try:
        return CalendarService.refresh(
            db,
            provider,
            start_utc=request.start_utc,
            end_utc=request.end_utc,
            countries=request.countries or None,
            relevant_keywords=request.relevant_keywords or None,
        )
    except CalendarProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/sync-to-catalyst", response_model=CalendarSyncResponse)
def sync_to_catalyst(request: CalendarSyncRequest, db: Session = Depends(get_db)) -> Any:
    return CalendarService.sync_to_catalyst(
        db, symbol=request.symbol, lookahead_hours=request.lookahead_hours
    )


@router.get("/upcoming", response_model=list[EconomicEventResponse])
def upcoming_events(
    hours: int = Query(48, ge=1, le=720),
    impact: str | None = Query(default=None),
    relevant_only: bool = Query(default=True),
    db: Session = Depends(get_db),
) -> Any:
    return CalendarService.upcoming(
        db, hours=hours, impact=impact, relevant_only=relevant_only
    )


@router.post("/scheduler/start", response_model=SchedulerStatus)
async def calendar_scheduler_start(request: SchedulerControlRequest) -> SchedulerStatus:
    scheduler = get_calendar_scheduler()
    try:
        await scheduler.start(
            provider_name=request.provider,
            interval_seconds=request.interval_seconds,
            sync_symbol=(request.symbols[0] if request.symbols else None),
        )
    except (RuntimeError, CalendarProviderError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return SchedulerStatus(**scheduler.status())


@router.post("/scheduler/stop", response_model=SchedulerStatus)
async def calendar_scheduler_stop() -> SchedulerStatus:
    scheduler = get_calendar_scheduler()
    await scheduler.stop()
    return SchedulerStatus(**scheduler.status())


@router.get("/scheduler/status", response_model=SchedulerStatus)
def calendar_scheduler_status() -> SchedulerStatus:
    return SchedulerStatus(**get_calendar_scheduler().status())
