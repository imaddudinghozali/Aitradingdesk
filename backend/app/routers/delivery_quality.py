import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.delivery_quality_assessment import DeliveryQualityAssessment
from app.schemas.delivery_quality import (
    DeliveryQualityAssessmentResponse,
    DeliveryQualityEvaluateRequest,
)
from app.schemas.market import VALID_SYMBOLS
from app.services.delivery_quality_service import DeliveryQualityService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/delivery-quality", tags=["delivery-quality"])


@router.post("/evaluate", response_model=DeliveryQualityAssessmentResponse)
def evaluate_delivery_quality(
    request: DeliveryQualityEvaluateRequest,
    db: Session = Depends(get_db),
) -> DeliveryQualityAssessment:
    try:
        return DeliveryQualityService.evaluate(
            db,
            request.symbol,
            request.timeframe,
            request.as_of_utc,
            request.valid_retracement,
            request.poi_reference,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Failed to evaluate delivery quality")
        raise HTTPException(status_code=500, detail="Failed to evaluate delivery quality") from exc


@router.get("/current/{symbol}", response_model=DeliveryQualityAssessmentResponse)
def current_delivery_quality(symbol: str, db: Session = Depends(get_db)) -> DeliveryQualityAssessment:
    symbol = symbol.upper()
    if symbol not in VALID_SYMBOLS:
        raise HTTPException(status_code=422, detail=f"Symbol must be one of {VALID_SYMBOLS}")
    assessment = DeliveryQualityService.get_current(db, symbol)
    if assessment is None:
        raise HTTPException(status_code=404, detail="Delivery quality assessment not found")
    return assessment
