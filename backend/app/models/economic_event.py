from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class EconomicEvent(Base):
    __tablename__ = "economic_events"
    __table_args__ = (
        UniqueConstraint(
            "country",
            "event_name",
            "scheduled_at_utc",
            name="uq_economic_event_country_name_time",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    provider: Mapped[str] = mapped_column(String(40), index=True)
    source_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    event_name: Mapped[str] = mapped_column(String(120), index=True)
    country: Mapped[str] = mapped_column(String(60), index=True)
    impact: Mapped[str] = mapped_column(String(10), index=True)
    scheduled_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    actual: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    forecast: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    previous: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    is_relevant: Mapped[bool] = mapped_column(default=False, index=True)
    last_synced_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
