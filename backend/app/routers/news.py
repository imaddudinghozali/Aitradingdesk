import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.market import VALID_SYMBOLS
from app.schemas.news import NewsCatalystEvaluateRequest, NewsCatalystResponse
from app.services.news_service import NewsCatalystService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/news-catalyst", tags=["news-catalyst"])


@router.post("/evaluate", response_model=NewsCatalystResponse)
def evaluate_news_catalyst(
    request: NewsCatalystEvaluateRequest, db: Session = Depends(get_db)
):
    try:
        return NewsCatalystService.evaluate(db, request)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Failed to evaluate news catalyst")
        raise HTTPException(status_code=500, detail="Failed to evaluate news catalyst") from exc


@router.get("/current/{symbol}", response_model=NewsCatalystResponse)
def current_news_catalyst(symbol: str, db: Session = Depends(get_db)):
    symbol = symbol.upper()
    if symbol not in VALID_SYMBOLS:
        raise HTTPException(status_code=422, detail=f"Symbol must be one of {VALID_SYMBOLS}")
    event = NewsCatalystService.get_current(db, symbol)
    if event is None:
        raise HTTPException(status_code=404, detail="News catalyst assessment not found")
    return event
