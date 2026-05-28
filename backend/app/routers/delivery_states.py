from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.delivery_state import DeliveryStateResponse
from app.schemas.market import VALID_SYMBOLS
from app.services.delivery_state_service import DeliveryStateService

router = APIRouter(prefix="/delivery-states", tags=["delivery-states"])


@router.get("/latest/{symbol}", response_model=list[DeliveryStateResponse])
def latest_delivery_states(symbol: str, db: Session = Depends(get_db)):
    symbol = symbol.upper()
    if symbol not in VALID_SYMBOLS:
        raise HTTPException(status_code=422, detail=f"Symbol must be one of {VALID_SYMBOLS}")
    states = DeliveryStateService.latest_snapshot_states(db, symbol)
    if not states:
        raise HTTPException(status_code=404, detail="Delivery states not found")
    return states
