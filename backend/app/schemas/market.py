"""Pydantic schemas for market data."""

from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, Field, field_validator, model_validator


VALID_TIMEFRAMES = {"M5", "M15", "H1", "H4", "D"}
TIMEFRAME_ALIASES = {
    "DAILY": "D",
    "D1": "D",
}
VALID_SYMBOLS = {"XAUUSD", "XAGUSD"}


class MarketDataInput(BaseModel):
    """Input model for market OHLC data."""
    
    symbol: str = Field(
        ..., 
        description="Symbol: XAUUSD or XAGUSD",
        examples=["XAUUSD"]
    )
    timeframe: str = Field(
        ..., 
        description="Timeframe: M5, M15, M30, H1, H4, D, W, M",
        examples=["H1"]
    )
    open: Decimal = Field(..., description="Open price", ge=0)
    high: Decimal = Field(..., description="High price", ge=0)
    low: Decimal = Field(..., description="Low price", ge=0)
    close: Decimal = Field(..., description="Close price", ge=0)
    volume: Decimal | None = Field(None, description="Volume", ge=0)
    timestamp_utc: datetime = Field(..., description="Candle timestamp in UTC")
    
    @field_validator("symbol")
    @classmethod
    def validate_symbol(cls, v: str) -> str:
        v = v.upper()
        if v not in VALID_SYMBOLS:
            raise ValueError(f"Symbol must be one of {VALID_SYMBOLS}")
        return v
    
    @field_validator("timeframe")
    @classmethod
    def validate_timeframe(cls, v: str) -> str:
        v = TIMEFRAME_ALIASES.get(v.upper(), v.upper())
        if v not in VALID_TIMEFRAMES:
            raise ValueError(f"Timeframe must be one of {VALID_TIMEFRAMES}")
        return v

    @model_validator(mode="after")
    def validate_ohlc_range(self) -> "MarketDataInput":
        if self.high < self.low:
            raise ValueError("High must be >= Low")

        for field_name in ("open", "close"):
            value = getattr(self, field_name)
            if value < self.low or value > self.high:
                raise ValueError(f"{field_name.title()} must be between Low and High")

        return self
    
    class Config:
        json_schema_extra = {
            "example": {
                "symbol": "XAUUSD",
                "timeframe": "H1",
                "open": 2350.50,
                "high": 2355.75,
                "low": 2349.00,
                "close": 2354.25,
                "volume": 1000000.00,
                "timestamp_utc": "2024-05-24T12:00:00Z"
            }
        }


class MarketSnapshotResponse(BaseModel):
    """Response model for market snapshot."""
    
    id: int
    symbol: str
    timeframe: str
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal | None
    timestamp_utc: datetime
    timestamp_ny: datetime
    session: str
    session_anchor: str
    yearly_quarter: str
    monthly_quarter: str
    weekly_quarter: str
    daily_quarter: str
    micro_quarter_90m: str
    day_of_week: str
    is_killzone: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


class MarketSnapshotBatch(BaseModel):
    """Batch input for multiple market snapshots."""
    
    snapshots: list[MarketDataInput] = Field(..., min_length=1, max_length=1000)


class MarketQueryParams(BaseModel):
    """Query parameters for market data."""
    
    symbol: str = Field(default="XAUUSD", description="Symbol to query")
    timeframe: str = Field(default="H1", description="Timeframe to query")
    limit: int = Field(default=100, ge=1, le=1000, description="Number of snapshots")
    
    @field_validator("symbol")
    @classmethod
    def validate_symbol(cls, v: str) -> str:
        v = v.upper()
        if v not in VALID_SYMBOLS:
            raise ValueError(f"Symbol must be one of {VALID_SYMBOLS}")
        return v
    
    @field_validator("timeframe")
    @classmethod
    def validate_timeframe(cls, v: str) -> str:
        v = TIMEFRAME_ALIASES.get(v.upper(), v.upper())
        if v not in VALID_TIMEFRAMES:
            raise ValueError(f"Timeframe must be one of {VALID_TIMEFRAMES}")
        return v
