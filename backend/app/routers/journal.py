from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.trade_journal_entry import TradeJournalEntry
from app.schemas.journal import (
    JournalCreateRequest,
    JournalEntryResponse,
    JournalPerformanceResponse,
    JournalUpdateRequest,
)
from app.schemas.market import VALID_SYMBOLS
from app.services.journal_service import JournalService

router = APIRouter(prefix="/journal", tags=["journal-review"])


@router.post("", response_model=JournalEntryResponse)
def create_entry(request: JournalCreateRequest, db: Session = Depends(get_db)):
    try:
        return JournalService.create(db, request)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("", response_model=list[JournalEntryResponse])
def list_entries(
    symbol: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    if symbol:
        symbol = symbol.upper()
        if symbol not in VALID_SYMBOLS:
            raise HTTPException(status_code=422, detail=f"Symbol must be one of {VALID_SYMBOLS}")
    return JournalService.list_entries(db, symbol, limit)


@router.get("/performance", response_model=JournalPerformanceResponse)
def journal_performance(symbol: str | None = None, db: Session = Depends(get_db)):
    if symbol:
        symbol = symbol.upper()
        if symbol not in VALID_SYMBOLS:
            raise HTTPException(status_code=422, detail=f"Symbol must be one of {VALID_SYMBOLS}")
    return JournalService.performance(db, symbol)


@router.get("/{entry_id}", response_model=JournalEntryResponse)
def entry_by_id(entry_id: int, db: Session = Depends(get_db)):
    entry = db.get(TradeJournalEntry, entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Journal entry not found")
    return entry


@router.patch("/{entry_id}", response_model=JournalEntryResponse)
def update_entry(entry_id: int, request: JournalUpdateRequest, db: Session = Depends(get_db)):
    entry = db.get(TradeJournalEntry, entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Journal entry not found")
    return JournalService.update(db, entry, request)
