from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class IngestionRun(Base):
    __tablename__ = "ingestion_runs"
    __table_args__ = (
        Index("ix_ingestion_runs_symbol_timeframe_started", "symbol", "timeframe", "started_at_utc"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    provider: Mapped[str] = mapped_column(String(40), index=True)
    symbol: Mapped[str] = mapped_column(String(20), index=True)
    timeframe: Mapped[str] = mapped_column(String(10), index=True)
    status: Mapped[str] = mapped_column(String(20), index=True)
    candles_fetched: Mapped[int] = mapped_column(Integer, default=0)
    candles_inserted: Mapped[int] = mapped_column(Integer, default=0)
    candles_skipped: Mapped[int] = mapped_column(Integer, default=0)
    first_candle_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_candle_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
