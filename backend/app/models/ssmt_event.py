from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class SsmtEvent(Base):
    __tablename__ = "ssmt_events"
    __table_args__ = (
        UniqueConstraint(
            "trade_asset",
            "confirmation_symbol",
            "timeframe",
            "first_quarter_start_utc",
            "second_quarter_start_utc",
            name="uq_ssmt_event_quarter_pair",
        ),
        Index("ix_ssmt_events_asset_status", "trade_asset", "ssmt_status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    trade_asset: Mapped[str] = mapped_column(String(20), default="XAUUSD", index=True)
    confirmation_symbol: Mapped[str] = mapped_column(String(20), default="XAGUSD")
    timeframe: Mapped[str] = mapped_column(String(10))
    ssmt_status: Mapped[str] = mapped_column(String(30), index=True)
    direction: Mapped[str | None] = mapped_column(String(20), nullable=True)
    cic_detected: Mapped[bool] = mapped_column(Boolean, default=False)
    quarter_sequence_valid: Mapped[bool] = mapped_column(Boolean, default=False)
    first_quarter: Mapped[str | None] = mapped_column(String(5), nullable=True)
    second_quarter: Mapped[str | None] = mapped_column(String(5), nullable=True)
    first_quarter_start_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    second_quarter_start_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    xau_first_swing: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    xau_second_swing: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    xag_first_swing: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    xag_second_swing: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    second_swing_at_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source_sweep_event_id: Mapped[int | None] = mapped_column(ForeignKey("sweep_events.id"), nullable=True)
    magneto_level_id: Mapped[int | None] = mapped_column(ForeignKey("liquidity_levels.id"), nullable=True)
    magneto_status: Mapped[str] = mapped_column(String(20), default="clear")
    poi_touched: Mapped[bool] = mapped_column(Boolean, default=False)
    poi_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    algorithm_state: Mapped[str] = mapped_column(String(40), default="waiting")
    algorithm_context_status: Mapped[str] = mapped_column(String(30), default="waiting")
    ssmt_dol_alignment: Mapped[str] = mapped_column(String(30))
    ssmt_noise_status: Mapped[str] = mapped_column(String(50))
    xau_relative_state: Mapped[str] = mapped_column(String(30))
    confirmation_pair_state: Mapped[str] = mapped_column(Text)
    liquidity_context: Mapped[str] = mapped_column(Text)
    reason_if_noise: Mapped[str | None] = mapped_column(Text, nullable=True)
    status_reason: Mapped[str] = mapped_column(Text)
    as_of_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
