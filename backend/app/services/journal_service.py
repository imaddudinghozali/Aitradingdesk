from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.execution_assessment import ExecutionAssessment
from app.models.narrative_snapshot import NarrativeSnapshot
from app.models.trade_journal_entry import TradeJournalEntry
from app.schemas.journal import (
    JournalCreateRequest,
    JournalPerformanceResponse,
    JournalUpdateRequest,
    ReviewBucket,
)


class JournalService:
    COMPLETED_RESULTS = {"win", "loss", "breakeven"}

    @staticmethod
    def create(db: Session, request: JournalCreateRequest) -> TradeJournalEntry:
        narrative = (
            db.get(NarrativeSnapshot, request.narrative_snapshot_id)
            if request.narrative_snapshot_id else None
        )
        execution = (
            db.get(ExecutionAssessment, request.execution_assessment_id)
            if request.execution_assessment_id else None
        )
        if request.narrative_snapshot_id and narrative is None:
            raise ValueError("Narrative snapshot not found.")
        if request.execution_assessment_id and execution is None:
            raise ValueError("Execution assessment not found.")
        if narrative and narrative.symbol != request.symbol:
            raise ValueError("Narrative snapshot symbol does not match journal symbol.")
        if execution and execution.symbol != request.symbol:
            raise ValueError("Execution assessment symbol does not match journal symbol.")
        entry = TradeJournalEntry(
            symbol=request.symbol,
            narrative_snapshot_id=request.narrative_snapshot_id,
            execution_assessment_id=request.execution_assessment_id,
            session=narrative.session if narrative else None,
            daily_quarter=narrative.daily_quarter if narrative else None,
            setup_context=request.setup_context,
            ai_narrative=narrative.rendered_snapshot if narrative else None,
            entry_reason=request.entry_reason,
            execution_confirmation=request.execution_confirmation,
            invalidation=request.invalidation,
            risk=request.risk,
            result=request.result,
            realized_rr=request.realized_rr,
            mistake_review=request.mistake_review,
            narrative_review=request.narrative_review,
            screenshot_path=request.screenshot_path,
            notes=request.notes,
        )
        db.add(entry)
        db.commit()
        db.refresh(entry)
        return entry

    @staticmethod
    def update(db: Session, entry: TradeJournalEntry, request: JournalUpdateRequest) -> TradeJournalEntry:
        for field, value in request.model_dump(exclude_unset=True).items():
            setattr(entry, field, value)
        db.commit()
        db.refresh(entry)
        return entry

    @staticmethod
    def list_entries(db: Session, symbol: str | None = None, limit: int = 100) -> list[TradeJournalEntry]:
        query = db.query(TradeJournalEntry)
        if symbol:
            query = query.filter(TradeJournalEntry.symbol == symbol)
        return query.order_by(TradeJournalEntry.created_at.desc(), TradeJournalEntry.id.desc()).limit(limit).all()

    @staticmethod
    def performance(db: Session, symbol: str | None = None) -> JournalPerformanceResponse:
        entries = list(reversed(JournalService.list_entries(db, symbol, 10000)))
        completed = [entry for entry in entries if entry.result in JournalService.COMPLETED_RESULTS]
        wins = sum(entry.result == "win" for entry in completed)
        losses = sum(entry.result == "loss" for entry in completed)
        rr_values = [entry.realized_rr for entry in completed if entry.realized_rr is not None]
        cumulative = sum(rr_values, Decimal(0)) if rr_values else None
        drawdown = JournalService._max_drawdown(rr_values)
        return JournalPerformanceResponse(
            symbol=symbol,
            total_entries=len(entries),
            completed_trades=len(completed),
            no_trade_reviews=sum(entry.result == "no_trade" for entry in entries),
            wins=wins,
            losses=losses,
            winrate=(Decimal(wins) / Decimal(len(completed))) if completed else None,
            average_rr=(cumulative / Decimal(len(rr_values))) if rr_values else None,
            cumulative_rr=cumulative,
            max_drawdown_rr=drawdown,
            by_session=JournalService._buckets(completed, "session"),
            by_quarter=JournalService._buckets(completed, "daily_quarter"),
        )

    @staticmethod
    def _buckets(entries: list[TradeJournalEntry], field: str) -> list[ReviewBucket]:
        names = sorted({getattr(entry, field) or "Unclassified" for entry in entries})
        result: list[ReviewBucket] = []
        for name in names:
            matching = [entry for entry in entries if (getattr(entry, field) or "Unclassified") == name]
            rr_values = [entry.realized_rr for entry in matching if entry.realized_rr is not None]
            result.append(
                ReviewBucket(
                    name=name,
                    trades=len(matching),
                    wins=sum(entry.result == "win" for entry in matching),
                    average_rr=(
                        sum(rr_values, Decimal(0)) / Decimal(len(rr_values))
                        if rr_values else None
                    ),
                )
            )
        return result

    @staticmethod
    def _max_drawdown(values: list[Decimal]) -> Decimal | None:
        if not values:
            return None
        equity = Decimal(0)
        peak = Decimal(0)
        max_drawdown = Decimal(0)
        for value in values:
            equity += value
            peak = max(peak, equity)
            max_drawdown = max(max_drawdown, peak - equity)
        return max_drawdown
