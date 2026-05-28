import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models.narrative_snapshot import NarrativeSnapshot
from app.schemas.market import VALID_SYMBOLS
from app.schemas.narrative import (
    NarrativeGenerateRequest,
    NarrativeSnapshotResponse,
    TelegramSendRequest,
)
from app.services.narrative_service import NarrativeService
from app.services.alert_service import AlertService
from app.services.telegram_service import TelegramService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/narratives", tags=["narratives"])


@router.post("/generate", response_model=NarrativeSnapshotResponse)
def generate_narrative(
    request: NarrativeGenerateRequest,
    db: Session = Depends(get_db),
) -> NarrativeSnapshot:
    try:
        return NarrativeService.generate(db, request)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Failed to generate narrative")
        raise HTTPException(status_code=500, detail="Failed to generate narrative") from exc


@router.get("/latest/{symbol}", response_model=NarrativeSnapshotResponse)
def latest_narrative(symbol: str, db: Session = Depends(get_db)) -> NarrativeSnapshot:
    symbol = symbol.upper()
    if symbol not in VALID_SYMBOLS:
        raise HTTPException(status_code=422, detail=f"Symbol must be one of {VALID_SYMBOLS}")
    narrative = NarrativeService.get_latest(db, symbol)
    if narrative is None:
        raise HTTPException(status_code=404, detail="Narrative snapshot not found")
    return narrative


@router.get("/{narrative_id}", response_model=NarrativeSnapshotResponse)
def narrative_by_id(narrative_id: int, db: Session = Depends(get_db)) -> NarrativeSnapshot:
    narrative = db.get(NarrativeSnapshot, narrative_id)
    if narrative is None:
        raise HTTPException(status_code=404, detail="Narrative snapshot not found")
    return narrative


@router.post("/{narrative_id}/telegram", response_model=NarrativeSnapshotResponse)
def send_narrative_to_telegram(
    narrative_id: int,
    request: TelegramSendRequest,
    db: Session = Depends(get_db),
) -> NarrativeSnapshot:
    narrative = db.get(NarrativeSnapshot, narrative_id)
    if narrative is None:
        raise HTTPException(status_code=404, detail="Narrative snapshot not found")
    try:
        message_id = TelegramService.send_message(
            get_settings(),
            NarrativeService.render_telegram(narrative),
            request.chat_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    narrative.telegram_status = "sent"
    narrative.telegram_message_id = message_id
    AlertService.mark_telegram_sent(db, narrative.id, message_id)
    db.commit()
    db.refresh(narrative)
    return narrative
