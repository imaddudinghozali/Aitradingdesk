from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.backtest_run import BacktestRun
from app.schemas.backtest import (
    BacktestBreakdownBucket,
    BacktestObservationResponse,
    BacktestRunRequest,
    BacktestRunResponse,
)
from app.schemas.market import VALID_SYMBOLS
from app.services.backtest_service import BacktestService

router = APIRouter(prefix="/backtests", tags=["backtest-refinement"])


@router.post("/run", response_model=BacktestRunResponse)
def run_backtest(request: BacktestRunRequest, db: Session = Depends(get_db)):
    try:
        return BacktestService.run(db, request)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("", response_model=list[BacktestRunResponse])
def list_backtests(
    symbol: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    if symbol:
        symbol = symbol.upper()
        if symbol not in VALID_SYMBOLS:
            raise HTTPException(status_code=422, detail=f"Symbol must be one of {VALID_SYMBOLS}")
    return BacktestService.list_runs(db, symbol, limit)


@router.get("/{run_id}", response_model=BacktestRunResponse)
def backtest_by_id(run_id: int, db: Session = Depends(get_db)):
    run = db.get(BacktestRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Backtest run not found")
    return run


@router.get("/{run_id}/observations", response_model=list[BacktestObservationResponse])
def backtest_observations(run_id: int, db: Session = Depends(get_db)):
    run = db.get(BacktestRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Backtest run not found")
    return BacktestService.observations(db, run_id)


@router.get("/{run_id}/breakdown", response_model=list[BacktestBreakdownBucket])
def backtest_breakdown(run_id: int, db: Session = Depends(get_db)):
    run = db.get(BacktestRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Backtest run not found")
    return BacktestService.breakdown(db, run_id)
