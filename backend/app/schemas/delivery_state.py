from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class DeliveryStateResponse(BaseModel):
    id: int
    narrative_snapshot_id: int
    symbol: str
    timeframe_layer: str
    quarter: str
    session: str
    state: str
    narrative: str
    confidence_score: Decimal | None
    created_at: datetime

    class Config:
        from_attributes = True
