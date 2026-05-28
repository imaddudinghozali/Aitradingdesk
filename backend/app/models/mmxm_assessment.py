from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class MmxmAssessment(Base):
    __tablename__ = "mmxm_assessments"
    __table_args__ = (
        UniqueConstraint("symbol", name="uq_mmxm_assessments_symbol"),
        Index("ix_mmxm_assessments_symbol_model", "symbol", "active_model"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    symbol: Mapped[str] = mapped_column(String(20), index=True)
    dol_assessment_id: Mapped[int] = mapped_column(ForeignKey("dol_assessments.id"))
    narrative_ledger_id: Mapped[int] = mapped_column(ForeignKey("narrative_ledgers.id"))
    source_sweep_event_id: Mapped[int | None] = mapped_column(ForeignKey("sweep_events.id"), nullable=True)
    active_model: Mapped[str] = mapped_column(String(30))
    model_status: Mapped[str] = mapped_column(String(30))
    candle_delivery: Mapped[str] = mapped_column(String(20))
    htf_delivery_leg: Mapped[str] = mapped_column(Text)
    timing_probability: Mapped[str] = mapped_column(String(30))
    timing_conflict: Mapped[str] = mapped_column(Text)
    mmxm_phase: Mapped[str] = mapped_column(String(60))
    quadrant: Mapped[str] = mapped_column(String(20))
    quadrant_position: Mapped[Decimal | None] = mapped_column(Numeric(7, 4), nullable=True)
    range_low: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    range_high: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    current_price: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    terminus: Mapped[str] = mapped_column(String(255))
    hrlr_status: Mapped[str] = mapped_column(Text)
    lrlr_status: Mapped[str] = mapped_column(Text)
    opr_status: Mapped[str] = mapped_column(Text)
    judas_status: Mapped[str] = mapped_column(String(30))
    judas_reason: Mapped[str] = mapped_column(Text)
    nine_am_context: Mapped[str] = mapped_column(Text)
    status_reason: Mapped[str] = mapped_column(Text)
    as_of_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
