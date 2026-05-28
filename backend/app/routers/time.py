import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException

from app.schemas.time_ladder import QuarterLadderResponse
from app.services.quarter_ladder_service import build_ladder

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/time", tags=["time"])


@router.get("/quarter-ladder", response_model=QuarterLadderResponse)
def quarter_ladder(as_of_utc: datetime | None = None) -> QuarterLadderResponse:
    try:
        return build_ladder(as_of_utc)
    except Exception as exc:
        logger.exception("Failed to build quarter ladder")
        raise HTTPException(status_code=500, detail="Failed to build quarter ladder") from exc
