from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Index, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class BacktestRun(Base):
    __tablename__ = "backtest_runs"
    __table_args__ = (
        Index("ix_backtest_runs_symbol_created", "symbol", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    symbol: Mapped[str] = mapped_column(String(20), index=True)
    timeframe: Mapped[str] = mapped_column(String(10))
    start_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    end_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    horizon_bars: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), index=True)
    methodology: Mapped[str] = mapped_column(Text)
    narrative_samples: Mapped[int] = mapped_column(Integer, default=0)
    scored_samples: Mapped[int] = mapped_column(Integer, default=0)
    valid_setup_samples: Mapped[int] = mapped_column(Integer, default=0)
    setup_wins: Mapped[int] = mapped_column(Integer, default=0)
    setup_losses: Mapped[int] = mapped_column(Integer, default=0)
    setup_unresolved: Mapped[int] = mapped_column(Integer, default=0)
    no_trade_samples: Mapped[int] = mapped_column(Integer, default=0)
    no_trade_scored: Mapped[int] = mapped_column(Integer, default=0)
    no_trade_correct: Mapped[int] = mapped_column(Integer, default=0)
    winrate: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    average_rr: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    max_drawdown_rr: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    no_trade_accuracy: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    false_ssmt_rate: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    false_sweep_rate: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    best_session: Mapped[str | None] = mapped_column(String(80), nullable=True)
    worst_session: Mapped[str | None] = mapped_column(String(80), nullable=True)
    best_quarter: Mapped[str | None] = mapped_column(String(80), nullable=True)
    worst_quarter: Mapped[str | None] = mapped_column(String(80), nullable=True)
    completed_at_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

