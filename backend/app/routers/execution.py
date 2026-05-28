import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.execution import (
    ExecutionAssessmentResponse,
    ExecutionEvaluateRequest,
    PoiScanRequest,
    PoiZoneResponse,
)
from app.schemas.market import VALID_SYMBOLS
from app.services.execution_service import ExecutionService, PoiService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/execution", tags=["execution-confirmation"])


@router.post("/pois/scan", response_model=list[PoiZoneResponse])
def scan_pois(request: PoiScanRequest, db: Session = Depends(get_db)):
    try:
        return PoiService.scan(db, request)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Failed to scan POI zones")
        raise HTTPException(status_code=500, detail="Failed to scan POI zones") from exc


@router.post("/evaluate", response_model=ExecutionAssessmentResponse)
def evaluate_execution(request: ExecutionEvaluateRequest, db: Session = Depends(get_db)):
    try:
        return ExecutionService.evaluate(db, request)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Failed to evaluate execution confirmation")
        raise HTTPException(status_code=500, detail="Failed to evaluate execution confirmation") from exc


@router.get("/current/{symbol}", response_model=ExecutionAssessmentResponse)
def current_execution(symbol: str, db: Session = Depends(get_db)):
    symbol = symbol.upper()
    if symbol not in VALID_SYMBOLS:
        raise HTTPException(status_code=422, detail=f"Symbol must be one of {VALID_SYMBOLS}")
    assessment = ExecutionService.get_current(db, symbol)
    if assessment is None:
        raise HTTPException(status_code=404, detail="Execution assessment not found")
    return assessment
