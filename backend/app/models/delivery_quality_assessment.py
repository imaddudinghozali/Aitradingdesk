from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class DeliveryQualityAssessment(Base):
    __tablename__ = "delivery_quality_assessments"
    __table_args__ = (
        UniqueConstraint("symbol", name="uq_delivery_quality_assessments_symbol"),
        Index("ix_delivery_quality_symbol_status", "symbol", "expansion_status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    symbol: Mapped[str] = mapped_column(String(20), index=True)
    dol_assessment_id: Mapped[int] = mapped_column(ForeignKey("dol_assessments.id"))
    narrative_ledger_id: Mapped[int] = mapped_column(ForeignKey("narrative_ledgers.id"))
    mmxm_assessment_id: Mapped[int | None] = mapped_column(
        ForeignKey("mmxm_assessments.id"), nullable=True
    )
    source_sweep_event_id: Mapped[int | None] = mapped_column(
        ForeignKey("sweep_events.id"), nullable=True
    )
    timeframe: Mapped[str] = mapped_column(String(10))
    valid_retracement: Mapped[bool] = mapped_column(Boolean, default=False)
    poi_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    delivery_tempo: Mapped[str] = mapped_column(String(30))
    expansion_quality: Mapped[str] = mapped_column(String(30))
    expansion_status: Mapped[str] = mapped_column(String(20))
    clean_displacement: Mapped[bool] = mapped_column(Boolean, default=False)
    overlap_heavy: Mapped[bool] = mapped_column(Boolean, default=False)
    failed_continuation: Mapped[bool] = mapped_column(Boolean, default=False)
    terminal_expansion: Mapped[bool] = mapped_column(Boolean, default=False)
    engineered_expansion: Mapped[bool] = mapped_column(Boolean, default=False)
    target_reached: Mapped[bool] = mapped_column(Boolean, default=False)
    status_reason: Mapped[str] = mapped_column(Text)
    execution_impact: Mapped[str] = mapped_column(Text)
    as_of_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
