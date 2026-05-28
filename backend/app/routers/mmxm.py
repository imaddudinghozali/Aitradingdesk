import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.mmxm_assessment import MmxmAssessment
from app.schemas.market import VALID_SYMBOLS
from app.schemas.mmxm import MmxmAssessmentResponse, MmxmEvaluateRequest
from app.services.mmxm_service import MmxmService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/mmxm", tags=["mmxm"])


@router.post("/evaluate", response_model=MmxmAssessmentResponse)
def evaluate_mmxm(
    request: MmxmEvaluateRequest,
    db: Session = Depends(get_db),
) -> MmxmAssessment:
    try:
        return MmxmService.evaluate(db, request.symbol, request.timeframe, request.as_of_utc)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Failed to evaluate MMXM/Judas")
        raise HTTPException(status_code=500, detail="Failed to evaluate MMXM/Judas") from exc


@router.get("/current/{symbol}", response_model=MmxmAssessmentResponse)
def current_mmxm(symbol: str, db: Session = Depends(get_db)) -> MmxmAssessment:
    symbol = symbol.upper()
    if symbol not in VALID_SYMBOLS:
        raise HTTPException(status_code=422, detail=f"Symbol must be one of {VALID_SYMBOLS}")
    assessment = MmxmService.get_current(db, symbol)
    if assessment is None:
        raise HTTPException(status_code=404, detail="MMXM assessment not found")
    return assessment
