from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, field_validator

from app.schemas.market import VALID_SYMBOLS


class NarrativeProvider(str, Enum):
    RULES = "rules"
    CLAUDE = "claude"


class NarrativeGenerateRequest(BaseModel):
    symbol: str = Field(default="XAUUSD", description="XAUUSD or XAGUSD")
    provider: NarrativeProvider = NarrativeProvider.RULES
    as_of_utc: datetime | None = Field(
        default=None,
        description="Optional decision cutoff; no market snapshot after this timestamp is read.",
    )

    @field_validator("symbol")
    @classmethod
    def validate_symbol(cls, value: str) -> str:
        value = value.upper()
        if value not in VALID_SYMBOLS:
            raise ValueError(f"Symbol must be one of {VALID_SYMBOLS}")
        return value


class TelegramSendRequest(BaseModel):
    chat_id: str | None = Field(default=None, description="Override TELEGRAM_CHAT_ID")


class NarrativeSnapshotResponse(BaseModel):
    id: int
    symbol: str
    provider: NarrativeProvider
    model: str | None
    ai_enhanced: bool
    session: str
    session_anchor: str
    daily_quarter: str
    quarter_status: str
    next_valid_window: str
    htf_dol: str
    dol_status: str
    direction_liquidity: str
    active_model: str
    macro_state: str
    quarterly_state: str
    session_state: str
    intraday_state: str
    conflict_resolution: str
    news_catalyst_status: str
    delivery_tempo: str
    delivery_state: str
    session_narrative: str
    judas_manipulation_status: str
    opr_status: str
    mmxm_timing_context: str
    ssmt_status: str
    expansion_quality: str
    setup_context: str
    trigger_confirmation: str
    risk_context: str
    execution_status: str
    no_trade_reason: str
    validation_required: str
    continuation_status: str
    reset_required: bool
    next_decision_if_invalidated: str
    invalidation: str
    target_liquidity: str
    retracement_reference: str = ""
    rendered_snapshot: str
    telegram_status: str
    telegram_message_id: str | None
    as_of_utc: datetime
    created_at: datetime

    class Config:
        from_attributes = True
