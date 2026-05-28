"""Raw-candle replay endpoints."""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.replay_run import ReplayRun
from app.schemas.market import VALID_SYMBOLS
from app.schemas.replay import (
    ReplayDecisionResponse,
    ReplayRunRequest,
    ReplayRunResponse,
)
from app.services.replay_policies import get_replay_policy
from app.services.replay_service import ReplayService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/replay", tags=["replay"])


@router.post("/run", response_model=ReplayRunResponse)
def run_replay(request: ReplayRunRequest, db: Session = Depends(get_db)) -> Any:
    try:
        policy = get_replay_policy(request.policy)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    try:
        return ReplayService.run(
            db,
            symbol=request.symbol,
            timeframe=request.timeframe,
            start_utc=request.start_utc,
            end_utc=request.end_utc,
            policy=policy,
            step_bars=request.step_bars,
            horizon_bars=request.horizon_bars,
            secondary_symbol=request.secondary_symbol,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("", response_model=list[ReplayRunResponse])
def list_replays(
    symbol: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> Any:
    if symbol:
        symbol = symbol.upper()
        if symbol not in VALID_SYMBOLS:
            raise HTTPException(status_code=422, detail=f"Symbol must be one of {VALID_SYMBOLS}")
    return ReplayService.list_runs(db, symbol, limit)


@router.get("/{run_id}", response_model=ReplayRunResponse)
def replay_by_id(run_id: int, db: Session = Depends(get_db)) -> Any:
    run = db.get(ReplayRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Replay run not found")
    return run


@router.get("/{run_id}/decisions", response_model=list[ReplayDecisionResponse])
def replay_decisions(run_id: int, db: Session = Depends(get_db)) -> Any:
    run = db.get(ReplayRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Replay run not found")
    return ReplayService.decisions(db, run_id)
