import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from app.db.models import ReplayGuard


class ReplayGuardRepository:
    """System-wide (not tenant-scoped) — event_id is globally unique."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def exists(self, *, event_id: str) -> bool:
        return (
            self.db.query(ReplayGuard)
            .filter(ReplayGuard.event_id == event_id)
            .first()
        ) is not None

    def record(self, *, event_id: str) -> ReplayGuard:
        guard = ReplayGuard(
            id=str(uuid.uuid4()),
            event_id=event_id,
            received_at=datetime.utcnow(),
        )
        self.db.add(guard)
        self.db.commit()
        self.db.refresh(guard)
        return guard
