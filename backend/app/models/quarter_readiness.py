from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class QuarterReadinessAssessment(Base):
    __tablename__ = "quarter_readiness_assessments"
    __table_args__ = (
        UniqueConstraint("symbol", name="uq_quarter_readiness_symbol"),
        Index("ix_quarter_readiness_symbol_status", "symbol", "quarter_status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    symbol: Mapped[str] = mapped_column(String(20), index=True)
    market_snapshot_id: Mapped[int] = mapped_column(ForeignKey("market_snapshots.id"))
    dol_assessment_id: Mapped[int] = mapped_column(ForeignKey("dol_assessments.id"))
    irl_erl_mapping_id: Mapped[int] = mapped_column(ForeignKey("irl_erl_mappings.id"))
    source_sweep_event_id: Mapped[int | None] = mapped_column(ForeignKey("sweep_events.id"), nullable=True)
    daily_quarter: Mapped[str] = mapped_column(String(5))
    micro_quarter_90m: Mapped[str] = mapped_column(String(5))
    session: Mapped[str] = mapped_column(String(30))
    quarter_status: Mapped[str] = mapped_column(String(30), index=True)
    quarter_intent: Mapped[str] = mapped_column(Text)
    manipulation_status: Mapped[str] = mapped_column(Text)
    expansion_status: Mapped[str] = mapped_column(Text)
    quarter_execution_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    gate_decision: Mapped[str] = mapped_column(String(30))
    status_reason: Mapped[str] = mapped_column(Text)
    next_valid_window: Mapped[str] = mapped_column(Text)
    as_of_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
