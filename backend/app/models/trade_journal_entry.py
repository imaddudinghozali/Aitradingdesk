from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class TradeJournalEntry(Base):
    __tablename__ = "trade_journal"
    __table_args__ = (
        Index("ix_trade_journal_symbol_created", "symbol", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    symbol: Mapped[str] = mapped_column(String(20), index=True)
    narrative_snapshot_id: Mapped[int | None] = mapped_column(
        ForeignKey("narrative_snapshots.id"), nullable=True
    )
    execution_assessment_id: Mapped[int | None] = mapped_column(
        ForeignKey("execution_assessments.id"), nullable=True
    )
    session: Mapped[str | None] = mapped_column(String(30), nullable=True)
    daily_quarter: Mapped[str | None] = mapped_column(String(5), nullable=True)
    setup_context: Mapped[str] = mapped_column(Text)
    ai_narrative: Mapped[str | None] = mapped_column(Text, nullable=True)
    entry_reason: Mapped[str] = mapped_column(Text)
    execution_confirmation: Mapped[str] = mapped_column(Text)
    invalidation: Mapped[str] = mapped_column(Text)
    risk: Mapped[str] = mapped_column(Text)
    result: Mapped[str] = mapped_column(String(20), index=True)
    realized_rr: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    mistake_review: Mapped[str | None] = mapped_column(Text, nullable=True)
    narrative_review: Mapped[str | None] = mapped_column(Text, nullable=True)
    screenshot_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
