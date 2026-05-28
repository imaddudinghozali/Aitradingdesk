import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.dol_assessment import DolAssessment
from app.models.liquidity_level import LiquidityLevel
from app.schemas.dol import (
    DolAssessmentResponse,
    DolEvaluateRequest,
    DolLifecycle,
    DolObjectiveResponse,
    MultiTfDolResponse,
)
from app.schemas.market import VALID_SYMBOLS
from app.services.dol_service import DolService
from app.services.multitf_dol_service import MultiTfDolService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/dol", tags=["dol"])


@router.post("/evaluate", response_model=DolAssessmentResponse)
def evaluate_dol(
    request: DolEvaluateRequest,
    db: Session = Depends(get_db),
) -> DolAssessmentResponse:
    try:
        assessment = DolService.evaluate(db, request.symbol, request.as_of_utc)
        return _response(db, assessment)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Failed to evaluate DOL")
        raise HTTPException(status_code=500, detail="Failed to evaluate DOL") from exc


@router.get("/current/{symbol}", response_model=DolAssessmentResponse)
def current_dol(symbol: str, db: Session = Depends(get_db)) -> DolAssessmentResponse:
    symbol = symbol.upper()
    if symbol not in VALID_SYMBOLS:
        raise HTTPException(status_code=422, detail=f"Symbol must be one of {VALID_SYMBOLS}")
    assessment = DolService.get_current(db, symbol)
    if assessment is None:
        raise HTTPException(status_code=404, detail="DOL assessment not found")
    return _response(db, assessment)


@router.get("/multitf/{symbol}", response_model=MultiTfDolResponse)
def multitf_dol(
    symbol: str,
    as_of_utc: datetime | None = Query(None),
    db: Session = Depends(get_db),
) -> MultiTfDolResponse:
    symbol = symbol.upper()
    if symbol not in VALID_SYMBOLS:
        raise HTTPException(status_code=422, detail=f"Symbol must be one of {VALID_SYMBOLS}")
    try:
        context = MultiTfDolService.evaluate(db, symbol, as_of_utc)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Failed to evaluate multi-timeframe DOL context")
        raise HTTPException(status_code=500, detail="Failed to evaluate multi-timeframe DOL context") from exc
    return MultiTfDolResponse.model_validate(context, from_attributes=True)


def _response(db: Session, assessment: DolAssessment) -> DolAssessmentResponse:
    lifecycle = DolLifecycle(assessment.lifecycle_status)
    execution_status = (
        "Narrative Ready - wait for later execution confirmation layers"
        if lifecycle in {DolLifecycle.ACTIVE, DolLifecycle.SHIFT_CONFIRMED}
        else "No Trade - DOL is not confirmed for execution"
    )
    return DolAssessmentResponse(
        id=assessment.id,
        symbol=assessment.symbol,
        lifecycle_status=lifecycle,
        delivery_direction=assessment.delivery_direction,
        primary_dol=_objective(db, assessment.primary_level_id),
        secondary_dol=_objective(db, assessment.secondary_level_id),
        htf_objective=_objective(db, assessment.htf_level_id),
        intraday_objective=_objective(db, assessment.intraday_level_id),
        engineered_liquidity=_objective(db, assessment.engineered_level_id),
        source_sweep_event_id=assessment.source_sweep_event_id,
        objective_quality=assessment.objective_quality,
        status_reason=assessment.status_reason,
        old_objective_resolved=assessment.old_objective_resolved,
        displacement_confirmed=assessment.displacement_confirmed,
        timing_confirmed=assessment.timing_confirmed,
        prior_narrative_resolved=assessment.prior_narrative_resolved,
        execution_status=execution_status,
        as_of_utc=assessment.as_of_utc,
        updated_at=assessment.updated_at,
    )


def _objective(db: Session, level_id: int | None) -> DolObjectiveResponse | None:
    if level_id is None:
        return None
    level = db.get(LiquidityLevel, level_id)
    if level is None:
        return None
    return DolObjectiveResponse(
        level_id=level.id,
        level_type=level.level_type,
        liquidity_side=level.liquidity_side,
        price=level.price,
        liquidity_status=level.status,
    )
