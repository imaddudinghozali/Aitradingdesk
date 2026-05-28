from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ReplayDecisionRow(Base):
    __tablename__ = "replay_decisions"
    __table_args__ = (
        Index("ix_replay_decisions_run_time", "replay_run_id", "as_of_utc"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    replay_run_id: Mapped[int] = mapped_column(ForeignKey("replay_runs.id"), index=True)
    as_of_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    daily_quarter: Mapped[str] = mapped_column(String(2))
    session: Mapped[str] = mapped_column(String(30))
    decision: Mapped[str] = mapped_column(String(30), index=True)
    direction: Mapped[str] = mapped_column(String(20))
    entry_reference: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    target_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    invalidation_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    expected_rr: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    bars_observed: Mapped[int] = mapped_column(Integer, default=0)
    outcome: Mapped[str] = mapped_column(String(30), index=True)
    realized_rr: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    outcome_reason: Mapped[str] = mapped_column(Text)
    reason: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
