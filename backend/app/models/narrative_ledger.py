from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class NarrativeLedger(Base):
    __tablename__ = "narrative_ledgers"
    __table_args__ = (
        Index("ix_narrative_ledgers_symbol_status", "symbol", "continuation_status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    symbol: Mapped[str] = mapped_column(String(20), index=True)
    dol_assessment_id: Mapped[int] = mapped_column(ForeignKey("dol_assessments.id"))
    quarter_readiness_id: Mapped[int | None] = mapped_column(
        ForeignKey("quarter_readiness_assessments.id"), nullable=True
    )
    ssmt_event_id: Mapped[int | None] = mapped_column(ForeignKey("ssmt_events.id"), nullable=True)
    active_dol: Mapped[str] = mapped_column(String(255))
    delivery_direction: Mapped[str] = mapped_column(String(20))
    target_level_id: Mapped[int] = mapped_column(ForeignKey("liquidity_levels.id"))
    target_liquidity: Mapped[str] = mapped_column(String(255))
    invalidation_level_id: Mapped[int] = mapped_column(ForeignKey("liquidity_levels.id"))
    invalidation_level: Mapped[str] = mapped_column(String(255))
    invalidation_price: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    invalidation_condition: Mapped[str] = mapped_column(Text)
    next_decision_if_invalidated: Mapped[str] = mapped_column(Text)
    reset_required: Mapped[bool] = mapped_column(Boolean, default=False)
    continuation_status: Mapped[str] = mapped_column(String(30), index=True)
    breach_status: Mapped[str] = mapped_column(String(30), default="clear")
    status_reason: Mapped[str] = mapped_column(Text)
    invalidated_at_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    activated_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    as_of_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
