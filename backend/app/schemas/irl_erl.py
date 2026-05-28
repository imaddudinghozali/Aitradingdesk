from datetime import datetime
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, Field, field_validator

from app.schemas.dol import DeliveryDirection, DolLifecycle
from app.schemas.market import VALID_SYMBOLS


class MappingStatus(str, Enum):
    ALIGNED = "aligned"
    PARTIAL = "partial"
    CONFLICT = "conflict"
    WAITING_DOL = "waiting_dol"
    INSUFFICIENT_DATA = "insufficient_data"


class IrlErlEvaluateRequest(BaseModel):
    symbol: str = Field(default="XAUUSD", description="XAUUSD or XAGUSD")

    @field_validator("symbol")
    @classmethod
    def validate_symbol(cls, value: str) -> str:
        value = value.upper()
        if value not in VALID_SYMBOLS:
            raise ValueError(f"Symbol must be one of {VALID_SYMBOLS}")
        return value


class MappedLiquidityLevel(BaseModel):
    level_id: int
    level_type: str
    role: str
    liquidity_side: str
    price: Decimal
    status: str
    basis: str


class ImbalanceZoneResponse(BaseModel):
    poi_id: int
    poi_type: str
    timeframe: str
    direction: str
    price_low: Decimal
    price_high: Decimal
    status: str


class MappingLayerResponse(BaseModel):
    narrative_timeframe: str
    direction_timeframes: list[str]
    irl: MappedLiquidityLevel | None
    erl: MappedLiquidityLevel | None
    direction_liquidity: str
    status: MappingStatus
    reason: str
    imbalance: ImbalanceZoneResponse | None = None


class IrlErlMappingResponse(BaseModel):
    id: int
    symbol: str
    dol_lifecycle_status: DolLifecycle
    delivery_direction: DeliveryDirection | None
    direction_flow: str
    mapping_status: MappingStatus
    layers: list[MappingLayerResponse]
    conflict_flags: list[str]
    limitations: list[str]
    status_reason: str
    execution_status: str
    imbalance: ImbalanceZoneResponse | None = None
    imbalance_role: str | None = None
    as_of_utc: datetime
    updated_at: datetime
