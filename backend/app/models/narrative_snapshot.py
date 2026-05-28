from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class NarrativeSnapshot(Base):
    __tablename__ = "narrative_snapshots"
    __table_args__ = (
        Index("ix_narrative_snapshots_symbol_created", "symbol", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    symbol: Mapped[str] = mapped_column(String(20), index=True)
    provider: Mapped[str] = mapped_column(String(20))
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    ai_enhanced: Mapped[bool] = mapped_column(Boolean, default=False)
    dol_assessment_id: Mapped[int] = mapped_column(ForeignKey("dol_assessments.id"))
    irl_erl_mapping_id: Mapped[int] = mapped_column(ForeignKey("irl_erl_mappings.id"))
    quarter_readiness_id: Mapped[int] = mapped_column(ForeignKey("quarter_readiness_assessments.id"))
    ssmt_event_id: Mapped[int | None] = mapped_column(ForeignKey("ssmt_events.id"), nullable=True)
    narrative_ledger_id: Mapped[int | None] = mapped_column(ForeignKey("narrative_ledgers.id"), nullable=True)
    mmxm_assessment_id: Mapped[int | None] = mapped_column(ForeignKey("mmxm_assessments.id"), nullable=True)
    delivery_quality_assessment_id: Mapped[int | None] = mapped_column(
        ForeignKey("delivery_quality_assessments.id"), nullable=True
    )
    news_catalyst_event_id: Mapped[int | None] = mapped_column(
        ForeignKey("news_catalyst_events.id"), nullable=True
    )
    execution_assessment_id: Mapped[int | None] = mapped_column(
        ForeignKey("execution_assessments.id"), nullable=True
    )
    source_sweep_event_id: Mapped[int | None] = mapped_column(ForeignKey("sweep_events.id"), nullable=True)
    session: Mapped[str] = mapped_column(String(30))
    session_anchor: Mapped[str] = mapped_column(String(5))
    daily_quarter: Mapped[str] = mapped_column(String(5))
    quarter_status: Mapped[str] = mapped_column(String(30))
    next_valid_window: Mapped[str] = mapped_column(Text)
    htf_dol: Mapped[str] = mapped_column(String(255))
    dol_status: Mapped[str] = mapped_column(String(30))
    direction_liquidity: Mapped[str] = mapped_column(String(50))
    active_model: Mapped[str] = mapped_column(String(100))
    macro_state: Mapped[str] = mapped_column(String(30))
    quarterly_state: Mapped[str] = mapped_column(String(30))
    session_state: Mapped[str] = mapped_column(String(30))
    intraday_state: Mapped[str] = mapped_column(String(30))
    conflict_resolution: Mapped[str] = mapped_column(Text)
    news_catalyst_status: Mapped[str] = mapped_column(Text)
    delivery_tempo: Mapped[str] = mapped_column(String(30))
    delivery_state: Mapped[str] = mapped_column(Text)
    session_narrative: Mapped[str] = mapped_column(Text)
    judas_manipulation_status: Mapped[str] = mapped_column(Text)
    opr_status: Mapped[str] = mapped_column(Text)
    mmxm_timing_context: Mapped[str] = mapped_column(Text)
    ssmt_status: Mapped[str] = mapped_column(Text)
    expansion_quality: Mapped[str] = mapped_column(Text)
    setup_context: Mapped[str] = mapped_column(Text)
    trigger_confirmation: Mapped[str] = mapped_column(Text)
    risk_context: Mapped[str] = mapped_column(Text)
    execution_status: Mapped[str] = mapped_column(Text)
    no_trade_reason: Mapped[str] = mapped_column(Text)
    validation_required: Mapped[str] = mapped_column(Text)
    continuation_status: Mapped[str] = mapped_column(String(30))
    reset_required: Mapped[bool] = mapped_column(Boolean, default=False)
    next_decision_if_invalidated: Mapped[str] = mapped_column(Text)
    invalidation: Mapped[str] = mapped_column(Text)
    target_liquidity: Mapped[str] = mapped_column(String(255))
    retracement_reference: Mapped[str] = mapped_column(Text, default="")
    rendered_snapshot: Mapped[str] = mapped_column(Text)
    telegram_status: Mapped[str] = mapped_column(String(20), default="not_sent")
    telegram_message_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    as_of_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
