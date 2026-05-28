from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.alert_record import AlertRecord
from app.schemas.alert import AlertResponse
from app.schemas.market import VALID_SYMBOLS
from app.services.alert_service import AlertService

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("", response_model=list[AlertResponse])
def list_alerts(
    symbol: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    if symbol is not None:
        symbol = symbol.upper()
        if symbol not in VALID_SYMBOLS:
            raise HTTPException(status_code=422, detail=f"Symbol must be one of {VALID_SYMBOLS}")
    return AlertService.list_records(db, symbol, limit)


@router.get("/{alert_id}", response_model=AlertResponse)
def alert_by_id(alert_id: int, db: Session = Depends(get_db)):
    alert = db.get(AlertRecord, alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    return alert
