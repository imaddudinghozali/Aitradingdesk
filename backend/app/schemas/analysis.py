from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator

from app.schemas.narrative import NarrativeProvider
from app.schemas.sweep import NarrativeAlignment


class AnalysisRunRequest(BaseModel):
    symbol: str = Field(default="XAUUSD")
    sweep_timeframe: str = Field(default="M15")
    execution_timeframe: str = Field(default="M15")
    minimum_rr: Decimal = Field(default=Decimal("1.0"), gt=0)
    provider: NarrativeProvider = NarrativeProvider.RULES
    sweep_narrative_alignment: NarrativeAlignment = NarrativeAlignment.UNKNOWN
    ssmt_poi_touched: bool = Field(
        default=False,
        description="Reviewed H4 SSMT POI confirmation; false keeps SSMT blocked.",
    )
    ssmt_poi_reference: str | None = Field(default=None, max_length=255)

    @field_validator("symbol")
    @classmethod
    def validate_symbol(cls, value: str) -> str:
        if value.upper() != "XAUUSD":
            raise ValueError("Analysis execution is restricted to XAUUSD; XAGUSD is confirmation input.")
        return "XAUUSD"

    @field_validator("sweep_timeframe", "execution_timeframe")
    @classmethod
    def validate_timeframe(cls, value: str) -> str:
        value = value.upper()
        if value not in {"M5", "M15", "H1"}:
            raise ValueError("Analysis timeframe must be M5, M15, or H1.")
        return value


class AnalysisStepResponse(BaseModel):
    stage: str
    status: str
    detail: str
    record_id: int | None = None


class AnalysisRunResponse(BaseModel):
    id: int
    symbol: str
    as_of_utc: datetime
    sweep_timeframe: str
    execution_timeframe: str
    minimum_rr: Decimal
    provider: NarrativeProvider
    run_status: str
    decision_status: str
    no_trade_reason: str
    steps: list[AnalysisStepResponse]
    missing_inputs: list[str]
    dol_assessment_id: int | None
    irl_erl_mapping_id: int | None
    quarter_readiness_id: int | None
    ssmt_event_id: int | None
    narrative_ledger_id: int | None
    mmxm_assessment_id: int | None
    delivery_quality_assessment_id: int | None
    execution_assessment_id: int | None
    narrative_snapshot_id: int | None
    created_at: datetime
    completed_at_utc: datetime | None
