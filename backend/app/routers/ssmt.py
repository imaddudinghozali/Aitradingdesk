import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.ssmt_event import SsmtEvent
from app.schemas.ssmt import SsmtEvaluateRequest, SsmtEventResponse
from app.services.ssmt_service import SsmtService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ssmt", tags=["ssmt"])


@router.post("/evaluate", response_model=SsmtEventResponse)
def evaluate_ssmt(
    request: SsmtEvaluateRequest,
    db: Session = Depends(get_db),
) -> SsmtEvent:
    try:
        return SsmtService.evaluate(db, request)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Failed to evaluate SSMT XAU/XAG")
        raise HTTPException(status_code=500, detail="Failed to evaluate SSMT XAU/XAG") from exc


@router.get("/current", response_model=SsmtEventResponse)
def current_ssmt(db: Session = Depends(get_db)) -> SsmtEvent:
    event = SsmtService.get_current(db)
    if event is None:
        raise HTTPException(status_code=404, detail="SSMT assessment not found")
    return event
