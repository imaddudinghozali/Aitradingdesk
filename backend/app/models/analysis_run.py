from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AnalysisRun(Base):
    __tablename__ = "analysis_runs"
    __table_args__ = (
        Index("ix_analysis_run_symbol_created", "symbol", "created_at"),
        Index("ix_analysis_run_symbol_status", "symbol", "decision_status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    symbol: Mapped[str] = mapped_column(String(20), index=True)
    as_of_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    sweep_timeframe: Mapped[str] = mapped_column(String(10))
    execution_timeframe: Mapped[str] = mapped_column(String(10))
    minimum_rr: Mapped[Decimal] = mapped_column(Numeric(10, 4))
    provider: Mapped[str] = mapped_column(String(20))
    sweep_narrative_alignment: Mapped[str] = mapped_column(String(20))
    ssmt_poi_touched: Mapped[bool] = mapped_column(Boolean, default=False)
    ssmt_poi_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    run_status: Mapped[str] = mapped_column(String(30), index=True)
    decision_status: Mapped[str] = mapped_column(String(30), index=True)
    no_trade_reason: Mapped[str] = mapped_column(Text)
    step_trace: Mapped[str] = mapped_column(Text)
    missing_inputs: Mapped[str] = mapped_column(Text)
    dol_assessment_id: Mapped[int | None] = mapped_column(
        ForeignKey("dol_assessments.id"), nullable=True
    )
    irl_erl_mapping_id: Mapped[int | None] = mapped_column(
        ForeignKey("irl_erl_mappings.id"), nullable=True
    )
    quarter_readiness_id: Mapped[int | None] = mapped_column(
        ForeignKey("quarter_readiness_assessments.id"), nullable=True
    )
    ssmt_event_id: Mapped[int | None] = mapped_column(ForeignKey("ssmt_events.id"), nullable=True)
    narrative_ledger_id: Mapped[int | None] = mapped_column(
        ForeignKey("narrative_ledgers.id"), nullable=True
    )
    mmxm_assessment_id: Mapped[int | None] = mapped_column(
        ForeignKey("mmxm_assessments.id"), nullable=True
    )
    delivery_quality_assessment_id: Mapped[int | None] = mapped_column(
        ForeignKey("delivery_quality_assessments.id"), nullable=True
    )
    execution_assessment_id: Mapped[int | None] = mapped_column(
        ForeignKey("execution_assessments.id"), nullable=True
    )
    narrative_snapshot_id: Mapped[int | None] = mapped_column(
        ForeignKey("narrative_snapshots.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
