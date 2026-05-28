from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class SweepEvent(Base):
    __tablename__ = "sweep_events"
    __table_args__ = (
        UniqueConstraint(
            "liquidity_level_id",
            "interaction_snapshot_id",
            name="uq_sweep_events_level_interaction",
        ),
        Index("ix_sweep_events_symbol_detected", "symbol", "detected_at_utc"),
        Index("ix_sweep_events_level_status", "liquidity_level_id", "sweep_status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    liquidity_level_id: Mapped[int] = mapped_column(ForeignKey("liquidity_levels.id"), index=True)
    interaction_snapshot_id: Mapped[int] = mapped_column(ForeignKey("market_snapshots.id"), index=True)
    confirmation_snapshot_id: Mapped[int | None] = mapped_column(
        ForeignKey("market_snapshots.id"),
        nullable=True,
    )
    symbol: Mapped[str] = mapped_column(String(20), index=True)
    level_type: Mapped[str] = mapped_column(String(30), index=True)
    liquidity_side: Mapped[str] = mapped_column(String(3), index=True)
    level_price: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    session: Mapped[str] = mapped_column(String(30))
    session_anchor: Mapped[str] = mapped_column(String(5))
    daily_quarter: Mapped[str] = mapped_column(String(2))
    micro_quarter_90m: Mapped[str] = mapped_column(String(5))
    sweep_status: Mapped[str] = mapped_column(String(30), index=True)
    confirmation_status: Mapped[str] = mapped_column(String(30))
    displacement_detected: Mapped[bool] = mapped_column(Boolean, default=False)
    relevant_timing: Mapped[bool] = mapped_column(Boolean, default=False)
    narrative_alignment: Mapped[str] = mapped_column(String(30))
    reason: Mapped[str] = mapped_column(String(500))
    target_liquidity: Mapped[str | None] = mapped_column(String(30), nullable=True)
    detected_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
