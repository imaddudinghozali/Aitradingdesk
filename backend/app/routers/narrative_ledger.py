import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.narrative_ledger import NarrativeLedger
from app.schemas.market import VALID_SYMBOLS
from app.schemas.narrative_ledger import NarrativeLedgerEvaluateRequest, NarrativeLedgerResponse
from app.services.narrative_ledger_service import NarrativeLedgerService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/narrative-ledger", tags=["narrative-ledger"])


@router.post("/evaluate", response_model=NarrativeLedgerResponse)
def evaluate_narrative_ledger(
    request: NarrativeLedgerEvaluateRequest,
    db: Session = Depends(get_db),
) -> NarrativeLedger:
    try:
        return NarrativeLedgerService.evaluate(
            db,
            request.symbol,
            request.timeframe,
            request.as_of_utc,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Failed to evaluate narrative ledger")
        raise HTTPException(status_code=500, detail="Failed to evaluate narrative ledger") from exc


@router.get("/current/{symbol}", response_model=NarrativeLedgerResponse)
def current_narrative_ledger(
    symbol: str,
    db: Session = Depends(get_db),
) -> NarrativeLedger:
    symbol = symbol.upper()
    if symbol not in VALID_SYMBOLS:
        raise HTTPException(status_code=422, detail=f"Symbol must be one of {VALID_SYMBOLS}")
    ledger = NarrativeLedgerService.get_current(db, symbol)
    if ledger is None:
        raise HTTPException(status_code=404, detail="Narrative ledger not found")
    return ledger
