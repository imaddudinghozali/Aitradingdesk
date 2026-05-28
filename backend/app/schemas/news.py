from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator

from app.schemas.market import VALID_SYMBOLS


class NewsCatalystEvaluateRequest(BaseModel):
    symbol: str = Field(default="XAUUSD", description="XAUUSD or XAGUSD")
    event_name: str = Field(min_length=2, max_length=80, examples=["CPI"])
    impact: str = Field(default="high")
    scheduled_at_utc: datetime
    as_of_utc: datetime | None = None

    @field_validator("symbol")
    @classmethod
    def validate_symbol(cls, value: str) -> str:
        value = value.upper()
        if value not in VALID_SYMBOLS:
            raise ValueError(f"Symbol must be one of {VALID_SYMBOLS}")
        return value

    @field_validator("impact")
    @classmethod
    def validate_impact(cls, value: str) -> str:
        value = value.lower()
        if value not in {"high", "medium"}:
            raise ValueError("News impact must be high or medium.")
        return value


class NewsCatalystResponse(BaseModel):
    id: int
    symbol: str
    event_name: str
    impact: str
    scheduled_at_utc: datetime
    news_phase: str
    catalyst_status: str
    direction_alignment: str
    pre_news_high: Decimal | None
    pre_news_low: Decimal | None
    status_reason: str
    post_news_expectation: str
    no_trade_reason: str
    as_of_utc: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
