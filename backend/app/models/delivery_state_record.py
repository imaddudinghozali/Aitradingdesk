from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class DeliveryStateRecord(Base):
    __tablename__ = "delivery_states"
    __table_args__ = (
        UniqueConstraint("narrative_snapshot_id", "timeframe_layer", name="uq_delivery_state_layer"),
        Index("ix_delivery_states_symbol_layer", "symbol", "timeframe_layer"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    narrative_snapshot_id: Mapped[int] = mapped_column(ForeignKey("narrative_snapshots.id"))
    symbol: Mapped[str] = mapped_column(String(20), index=True)
    timeframe_layer: Mapped[str] = mapped_column(String(20), index=True)
    quarter: Mapped[str] = mapped_column(String(5))
    session: Mapped[str] = mapped_column(String(30))
    state: Mapped[str] = mapped_column(String(30), index=True)
    narrative: Mapped[str] = mapped_column(Text)
    confidence_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
