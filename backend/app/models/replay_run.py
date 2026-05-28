from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ReplayRun(Base):
    __tablename__ = "replay_runs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    symbol: Mapped[str] = mapped_column(String(20), index=True)
    timeframe: Mapped[str] = mapped_column(String(10), index=True)
    policy_name: Mapped[str] = mapped_column(String(60))
    start_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    step_bars: Mapped[int] = mapped_column(Integer, default=1)
    horizon_bars: Mapped[int] = mapped_column(Integer, default=24)
    status: Mapped[str] = mapped_column(String(20), default="running", index=True)
    methodology: Mapped[str] = mapped_column(Text)
    evaluation_points: Mapped[int] = mapped_column(Integer, default=0)
    valid_setups: Mapped[int] = mapped_column(Integer, default=0)
    no_trades: Mapped[int] = mapped_column(Integer, default=0)
    setup_wins: Mapped[int] = mapped_column(Integer, default=0)
    setup_losses: Mapped[int] = mapped_column(Integer, default=0)
    setup_unresolved: Mapped[int] = mapped_column(Integer, default=0)
    winrate: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    average_rr: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    max_drawdown_rr: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    completed_at_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
