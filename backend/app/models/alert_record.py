from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AlertRecord(Base):
    __tablename__ = "alerts"
    __table_args__ = (
        Index("ix_alerts_symbol_created", "symbol", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    narrative_snapshot_id: Mapped[int | None] = mapped_column(
        ForeignKey("narrative_snapshots.id"), nullable=True
    )
    execution_assessment_id: Mapped[int | None] = mapped_column(
        ForeignKey("execution_assessments.id"), nullable=True
    )
    event_type: Mapped[str] = mapped_column(String(40), index=True)
    symbol: Mapped[str] = mapped_column(String(20), index=True)
    message: Mapped[str] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(String(20), index=True)
    sent_to_telegram: Mapped[bool] = mapped_column(Boolean, default=False)
    telegram_message_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    sent_at_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
