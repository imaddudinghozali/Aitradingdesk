from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, Index, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class MarketSnapshot(Base):
    __tablename__ = "market_snapshots"
    __table_args__ = (
        Index("ix_market_snapshots_symbol_timeframe_utc", "symbol", "timeframe", "timestamp_utc"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    symbol: Mapped[str] = mapped_column(String(20), index=True)
    timeframe: Mapped[str] = mapped_column(String(10), index=True)
    open: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    high: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    low: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    close: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    volume: Mapped[Decimal | None] = mapped_column(Numeric(24, 6), nullable=True)
    timestamp_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    timestamp_ny: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    session: Mapped[str] = mapped_column(String(30), index=True)
    session_anchor: Mapped[str] = mapped_column(String(5), index=True)
    yearly_quarter: Mapped[str] = mapped_column(String(2), index=True)
    monthly_quarter: Mapped[str] = mapped_column(String(2), index=True)
    weekly_quarter: Mapped[str] = mapped_column(String(2), index=True)
    daily_quarter: Mapped[str] = mapped_column(String(2), index=True)
    micro_quarter_90m: Mapped[str] = mapped_column(String(5), index=True)
    day_of_week: Mapped[str] = mapped_column(String(10), index=True)
    is_killzone: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
