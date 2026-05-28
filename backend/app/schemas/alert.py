from datetime import datetime

from pydantic import BaseModel


class AlertResponse(BaseModel):
    id: int
    narrative_snapshot_id: int | None
    execution_assessment_id: int | None
    event_type: str
    symbol: str
    message: str
    severity: str
    sent_to_telegram: bool
    telegram_message_id: str | None
    sent_at_utc: datetime | None
    created_at: datetime

    class Config:
        from_attributes = True
