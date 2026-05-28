from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class BacktestObservation(Base):
    __tablename__ = "backtest_observations"
    __table_args__ = (
        Index("ix_backtest_observations_run_outcome", "backtest_run_id", "outcome"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    backtest_run_id: Mapped[int] = mapped_column(ForeignKey("backtest_runs.id"), index=True)
    narrative_snapshot_id: Mapped[int] = mapped_column(ForeignKey("narrative_snapshots.id"))
    execution_assessment_id: Mapped[int | None] = mapped_column(
        ForeignKey("execution_assessments.id"), nullable=True
    )
    source_sweep_event_id: Mapped[int | None] = mapped_column(
        ForeignKey("sweep_events.id"), nullable=True
    )
    symbol: Mapped[str] = mapped_column(String(20), index=True)
    timeframe: Mapped[str] = mapped_column(String(10))
    observed_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    session: Mapped[str] = mapped_column(String(30))
    daily_quarter: Mapped[str] = mapped_column(String(5))
    htf_dol: Mapped[str] = mapped_column(String(255))
    direction_liquidity: Mapped[str] = mapped_column(String(50))
    active_model: Mapped[str] = mapped_column(String(100))
    ssmt_status: Mapped[str] = mapped_column(Text)
    judas_status: Mapped[str] = mapped_column(Text)
    opr_status: Mapped[str] = mapped_column(Text)
    mmxm_timing_context: Mapped[str] = mapped_column(Text)
    execution_status: Mapped[str] = mapped_column(String(30))
    entry_reference: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    invalidation_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    target_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    expected_rr: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    bars_observed: Mapped[int] = mapped_column(Integer, default=0)
    outcome: Mapped[str] = mapped_column(String(40), index=True)
    realized_rr: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    outcome_reason: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
