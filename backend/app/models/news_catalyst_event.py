from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class NewsCatalystEvent(Base):
    __tablename__ = "news_catalyst_events"
    __table_args__ = (
        UniqueConstraint("symbol", "event_name", "scheduled_at_utc", name="uq_news_catalyst_event"),
        Index("ix_news_catalyst_symbol_scheduled", "symbol", "scheduled_at_utc"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    symbol: Mapped[str] = mapped_column(String(20), index=True)
    dol_assessment_id: Mapped[int] = mapped_column(ForeignKey("dol_assessments.id"))
    event_name: Mapped[str] = mapped_column(String(80))
    impact: Mapped[str] = mapped_column(String(20))
    scheduled_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    news_phase: Mapped[str] = mapped_column(String(40))
    catalyst_status: Mapped[str] = mapped_column(String(40))
    direction_alignment: Mapped[str] = mapped_column(String(30))
    pre_news_high: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    pre_news_low: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    status_reason: Mapped[str] = mapped_column(Text)
    post_news_expectation: Mapped[str] = mapped_column(Text)
    no_trade_reason: Mapped[str] = mapped_column(Text)
    as_of_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
