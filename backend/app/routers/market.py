"""Market data router."""

import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.market import MarketDataInput, MarketSnapshotResponse, MarketSnapshotBatch
from app.services.market_service import MarketService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/market", tags=["market"])


@router.post("/ohlc", response_model=MarketSnapshotResponse, status_code=201)
def create_market_data(
    data: MarketDataInput,
    db: Session = Depends(get_db),
) -> MarketSnapshotResponse:
    """Create a new market OHLC snapshot.
    
    Accepts OHLC data and stores it with normalized timestamps (UTC and NY time).
    """
    try:
        snapshot = MarketService.create_snapshot(db, data)
        return snapshot
    except Exception as exc:
        logger.error(f"Failed to create market snapshot: {exc}")
        raise HTTPException(
            status_code=400,
            detail=f"Failed to create snapshot: {str(exc)}"
        ) from exc


@router.post("/ohlc/batch", response_model=list[MarketSnapshotResponse], status_code=201)
def create_market_batch(
    batch: MarketSnapshotBatch,
    db: Session = Depends(get_db),
) -> list[MarketSnapshotResponse]:
    """Create multiple market snapshots in one request.
    
    Batch operation for bulk data ingestion.
    """
    snapshots = []
    try:
        for data in batch.snapshots:
            snapshot = MarketService.create_snapshot(db, data)
            snapshots.append(snapshot)
        return snapshots
    except Exception as exc:
        logger.error(f"Failed to create batch snapshots: {exc}")
        raise HTTPException(
            status_code=400,
            detail=f"Failed to create batch: {str(exc)}"
        ) from exc


@router.get("/latest/{symbol}/{timeframe}", response_model=MarketSnapshotResponse | None)
def get_latest_snapshot(
    symbol: str,
    timeframe: str,
    db: Session = Depends(get_db),
) -> MarketSnapshotResponse | None:
    """Get the latest market snapshot for a symbol/timeframe.
    
    Args:
        symbol: Symbol (XAUUSD, XAGUSD)
        timeframe: Timeframe (M5, M15, H1, H4, D, W, M)
    """
    try:
        snapshot = MarketService.get_latest(db, symbol, timeframe)
        if not snapshot:
            raise HTTPException(
                status_code=404,
                detail=f"No data found for {symbol} {timeframe}"
            )
        return snapshot
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Failed to retrieve latest snapshot: {exc}")
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve snapshot"
        ) from exc


@router.get("/snapshots", response_model=list[MarketSnapshotResponse])
def get_snapshots(
    symbol: str = Query("XAUUSD", description="Symbol: XAUUSD or XAGUSD"),
    timeframe: str = Query("H1", description="Timeframe: M5, M15, H1, H4, D, W, M"),
    limit: int = Query(100, ge=1, le=1000, description="Max results"),
    db: Session = Depends(get_db),
) -> list[MarketSnapshotResponse]:
    """Get recent market snapshots with optional filters.
    
    Args:
        symbol: Symbol to query
        timeframe: Timeframe to query
        limit: Maximum number of snapshots
    """
    try:
        snapshots = MarketService.get_snapshots(db, symbol, timeframe, limit)
        if not snapshots:
            raise HTTPException(
                status_code=404,
                detail=f"No data found for {symbol} {timeframe}"
            )
        return snapshots
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Failed to retrieve snapshots: {exc}")
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve snapshots"
        ) from exc


@router.get("/symbols", response_model=list[str])
def get_symbols(db: Session = Depends(get_db)) -> list[str]:
    """Get all available symbols in the database."""
    try:
        symbols = MarketService.get_all_symbols(db)
        if not symbols:
            return []
        return symbols
    except Exception as exc:
        logger.error(f"Failed to retrieve symbols: {exc}")
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve symbols"
        ) from exc


@router.get("/timeframes/{symbol}", response_model=list[str])
def get_timeframes(symbol: str, db: Session = Depends(get_db)) -> list[str]:
    """Get all available timeframes for a symbol."""
    try:
        timeframes = MarketService.get_all_timeframes(db, symbol)
        if not timeframes:
            raise HTTPException(
                status_code=404,
                detail=f"No data found for {symbol}"
            )
        return timeframes
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Failed to retrieve timeframes: {exc}")
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve timeframes"
        ) from exc


@router.get("/status", response_model=dict)
def market_status(db: Session = Depends(get_db)) -> dict:
    """Get market data status (available symbols and timeframes)."""
    try:
        symbols = MarketService.get_all_symbols(db)
        status = {
            "status": "ok",
            "symbols": symbols,
            "timeframes_per_symbol": {}
        }
        
        for symbol in symbols:
            timeframes = MarketService.get_all_timeframes(db, symbol)
            status["timeframes_per_symbol"][symbol] = timeframes
        
        return status
    except Exception as exc:
        logger.error(f"Failed to get market status: {exc}")
        raise HTTPException(
            status_code=500,
            detail="Failed to get market status"
        ) from exc
