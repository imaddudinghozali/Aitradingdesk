from sqlalchemy.orm import Session

from app.models.delivery_state_record import DeliveryStateRecord
from app.models.narrative_snapshot import NarrativeSnapshot


class DeliveryStateService:
    @staticmethod
    def record_snapshot(db: Session, snapshot: NarrativeSnapshot) -> list[DeliveryStateRecord]:
        rows = [
            ("macro", snapshot.macro_state, f"{snapshot.htf_dol}; {snapshot.direction_liquidity}."),
            ("quarterly", snapshot.quarterly_state, f"{snapshot.quarter_status}; {snapshot.next_valid_window}."),
            ("session", snapshot.session_state, snapshot.session_narrative),
            ("intraday", snapshot.intraday_state, snapshot.expansion_quality),
        ]
        records = [
            DeliveryStateRecord(
                narrative_snapshot_id=snapshot.id,
                symbol=snapshot.symbol,
                timeframe_layer=layer,
                quarter=snapshot.daily_quarter,
                session=snapshot.session,
                state=state,
                narrative=narrative,
                confidence_score=None,
            )
            for layer, state, narrative in rows
        ]
        db.add_all(records)
        db.commit()
        for record in records:
            db.refresh(record)
        return records

    @staticmethod
    def latest_snapshot_states(db: Session, symbol: str) -> list[DeliveryStateRecord]:
        latest = (
            db.query(DeliveryStateRecord.narrative_snapshot_id)
            .filter(DeliveryStateRecord.symbol == symbol)
            .order_by(DeliveryStateRecord.created_at.desc(), DeliveryStateRecord.id.desc())
            .first()
        )
        if latest is None:
            return []
        return (
            db.query(DeliveryStateRecord)
            .filter(DeliveryStateRecord.narrative_snapshot_id == latest[0])
            .order_by(DeliveryStateRecord.id.asc())
            .all()
        )
