from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class PoiZone(Base):
    __tablename__ = "poi_zones"
    __table_args__ = (
        UniqueConstraint(
            "symbol",
            "timeframe",
            "poi_type",
            "direction",
            "source_snapshot_id",
            name="uq_poi_zone_source",
        ),
        Index("ix_poi_zones_symbol_status", "symbol", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    symbol: Mapped[str] = mapped_column(String(20), index=True)
    timeframe: Mapped[str] = mapped_column(String(10), index=True)
    poi_type: Mapped[str] = mapped_column(String(20), index=True)
    direction: Mapped[str] = mapped_column(String(20))
    price_low: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    price_high: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    source_snapshot_id: Mapped[int] = mapped_column(ForeignKey("market_snapshots.id"))
    status: Mapped[str] = mapped_column(String(30), index=True)
    touched_at_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reaction_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    invalidated_at_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status_reason: Mapped[str] = mapped_column(Text)
    as_of_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
