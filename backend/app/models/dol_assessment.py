from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class DolAssessment(Base):
    __tablename__ = "dol_assessments"
    __table_args__ = (
        UniqueConstraint("symbol", name="uq_dol_assessments_symbol"),
        Index("ix_dol_assessments_symbol_status", "symbol", "lifecycle_status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    symbol: Mapped[str] = mapped_column(String(20), index=True)
    lifecycle_status: Mapped[str] = mapped_column(String(30), index=True)
    delivery_direction: Mapped[str | None] = mapped_column(String(20), nullable=True)
    primary_level_id: Mapped[int | None] = mapped_column(
        ForeignKey("liquidity_levels.id"),
        nullable=True,
    )
    secondary_level_id: Mapped[int | None] = mapped_column(
        ForeignKey("liquidity_levels.id"),
        nullable=True,
    )
    htf_level_id: Mapped[int | None] = mapped_column(
        ForeignKey("liquidity_levels.id"),
        nullable=True,
    )
    intraday_level_id: Mapped[int | None] = mapped_column(
        ForeignKey("liquidity_levels.id"),
        nullable=True,
    )
    engineered_level_id: Mapped[int | None] = mapped_column(
        ForeignKey("liquidity_levels.id"),
        nullable=True,
    )
    source_sweep_event_id: Mapped[int | None] = mapped_column(
        ForeignKey("sweep_events.id"),
        nullable=True,
    )
    objective_quality: Mapped[str | None] = mapped_column(String(30), nullable=True)
    status_reason: Mapped[str] = mapped_column(String(1000))
    old_objective_resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    displacement_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    timing_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    prior_narrative_resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    as_of_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
