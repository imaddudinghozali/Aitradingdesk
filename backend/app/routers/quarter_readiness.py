import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.quarter_readiness import QuarterReadinessAssessment
from app.schemas.market import VALID_SYMBOLS
from app.schemas.quarter_readiness import QuarterEvaluateRequest, QuarterReadinessResponse
from app.services.quarter_readiness_service import QuarterReadinessService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/quarter-readiness", tags=["quarter-readiness"])


@router.post("/evaluate", response_model=QuarterReadinessResponse)
def evaluate_quarter_readiness(
    request: QuarterEvaluateRequest,
    db: Session = Depends(get_db),
) -> QuarterReadinessAssessment:
    try:
        return QuarterReadinessService.evaluate(db, request.symbol, request.as_of_utc)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Failed to evaluate quarter readiness")
        raise HTTPException(status_code=500, detail="Failed to evaluate quarter readiness") from exc


@router.get("/current/{symbol}", response_model=QuarterReadinessResponse)
def current_quarter_readiness(
    symbol: str,
    db: Session = Depends(get_db),
) -> QuarterReadinessAssessment:
    symbol = symbol.upper()
    if symbol not in VALID_SYMBOLS:
        raise HTTPException(status_code=422, detail=f"Symbol must be one of {VALID_SYMBOLS}")
    assessment = QuarterReadinessService.get_current(db, symbol)
    if assessment is None:
        raise HTTPException(status_code=404, detail="Quarter readiness assessment not found")
    return assessment
