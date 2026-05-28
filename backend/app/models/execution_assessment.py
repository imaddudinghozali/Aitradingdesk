from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ExecutionAssessment(Base):
    __tablename__ = "execution_assessments"
    __table_args__ = (
        Index("ix_execution_symbol_status", "symbol", "execution_status"),
        Index("ix_execution_symbol_as_of", "symbol", "as_of_utc"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    symbol: Mapped[str] = mapped_column(String(20), index=True)
    timeframe: Mapped[str] = mapped_column(String(10))
    dol_assessment_id: Mapped[int] = mapped_column(ForeignKey("dol_assessments.id"))
    narrative_ledger_id: Mapped[int] = mapped_column(ForeignKey("narrative_ledgers.id"))
    quarter_readiness_id: Mapped[int | None] = mapped_column(
        ForeignKey("quarter_readiness_assessments.id"), nullable=True
    )
    delivery_quality_assessment_id: Mapped[int | None] = mapped_column(
        ForeignKey("delivery_quality_assessments.id"), nullable=True
    )
    poi_zone_id: Mapped[int | None] = mapped_column(ForeignKey("poi_zones.id"), nullable=True)
    delivery_direction: Mapped[str] = mapped_column(String(20))
    setup_context: Mapped[str] = mapped_column(Text)
    poi_confirmation: Mapped[str] = mapped_column(Text)
    mss_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    cisd_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    trigger_confirmation: Mapped[str] = mapped_column(Text)
    entry_reference: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    invalidation_price: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    target_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    risk_points: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    reward_points: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    rr_ratio: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    minimum_rr: Mapped[Decimal] = mapped_column(Numeric(10, 4))
    risk_status: Mapped[str] = mapped_column(String(30))
    execution_status: Mapped[str] = mapped_column(String(30), index=True)
    no_trade_reason: Mapped[str] = mapped_column(Text)
    validation_required: Mapped[str] = mapped_column(Text)
    as_of_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
