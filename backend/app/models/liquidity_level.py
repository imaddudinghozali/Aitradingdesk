from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Index, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class LiquidityLevel(Base):
    __tablename__ = "liquidity_levels"
    __table_args__ = (
        UniqueConstraint("symbol", "level_type", name="uq_liquidity_levels_symbol_type"),
        Index("ix_liquidity_levels_symbol_status", "symbol", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    symbol: Mapped[str] = mapped_column(String(20), index=True)
    level_type: Mapped[str] = mapped_column(String(30), index=True)
    liquidity_side: Mapped[str] = mapped_column(String(3), index=True)
    price: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    status: Mapped[str] = mapped_column(String(20), default="active", index=True)
    source_timeframe: Mapped[str] = mapped_column(String(20))
    source_period_start_ny: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    source_period_end_ny: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    as_of_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    touched_at_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    taken_at_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    invalidated_at_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
