from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class IrlErlMapping(Base):
    __tablename__ = "irl_erl_mappings"
    __table_args__ = (
        UniqueConstraint("symbol", name="uq_irl_erl_mappings_symbol"),
        Index("ix_irl_erl_mappings_symbol_status", "symbol", "mapping_status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    symbol: Mapped[str] = mapped_column(String(20), index=True)
    dol_assessment_id: Mapped[int] = mapped_column(ForeignKey("dol_assessments.id"))
    direction_flow: Mapped[str] = mapped_column(String(40))
    mapping_status: Mapped[str] = mapped_column(String(30), index=True)
    weekly_irl_level_id: Mapped[int | None] = mapped_column(ForeignKey("liquidity_levels.id"), nullable=True)
    weekly_erl_level_id: Mapped[int | None] = mapped_column(ForeignKey("liquidity_levels.id"), nullable=True)
    daily_irl_level_id: Mapped[int | None] = mapped_column(ForeignKey("liquidity_levels.id"), nullable=True)
    daily_erl_level_id: Mapped[int | None] = mapped_column(ForeignKey("liquidity_levels.id"), nullable=True)
    status_reason: Mapped[str] = mapped_column(String(1000))
    conflict_summary: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    as_of_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
