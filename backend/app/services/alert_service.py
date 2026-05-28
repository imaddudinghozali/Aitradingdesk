from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models.alert_record import AlertRecord
from app.models.narrative_snapshot import NarrativeSnapshot


class AlertService:
    @staticmethod
    def record_narrative(db: Session, snapshot: NarrativeSnapshot) -> AlertRecord:
        if snapshot.execution_status == "Valid Setup":
            event_type, severity = "execution_valid_setup", "setup"
        elif snapshot.continuation_status in {"failed", "reversed", "redistributed"}:
            event_type, severity = "narrative_failure", "critical"
        else:
            event_type, severity = "narrative_snapshot", "info"
        alert = AlertRecord(
            narrative_snapshot_id=snapshot.id,
            execution_assessment_id=snapshot.execution_assessment_id,
            event_type=event_type,
            symbol=snapshot.symbol,
            message=snapshot.rendered_snapshot,
            severity=severity,
            sent_to_telegram=False,
        )
        db.add(alert)
        db.commit()
        db.refresh(alert)
        return alert

    @staticmethod
    def list_records(db: Session, symbol: str | None = None, limit: int = 100) -> list[AlertRecord]:
        query = db.query(AlertRecord)
        if symbol:
            query = query.filter(AlertRecord.symbol == symbol)
        return query.order_by(AlertRecord.created_at.desc(), AlertRecord.id.desc()).limit(limit).all()

    @staticmethod
    def mark_telegram_sent(
        db: Session,
        narrative_id: int,
        message_id: str,
    ) -> None:
        alert = (
            db.query(AlertRecord)
            .filter(AlertRecord.narrative_snapshot_id == narrative_id)
            .order_by(AlertRecord.id.desc())
            .first()
        )
        if alert is None:
            return
        alert.sent_to_telegram = True
        alert.telegram_message_id = message_id
        alert.sent_at_utc = datetime.now(UTC)
