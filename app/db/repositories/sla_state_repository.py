import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.db.exceptions import TenantAccessError
from app.db.models import SLAState


class SLAStateRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, *, tenant_id: str, ticket_id: str) -> SLAState:
        state = SLAState(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            ticket_id=ticket_id,
        )
        self.db.add(state)
        self.db.commit()
        self.db.refresh(state)
        return state

    def get_by_ticket_id(
        self, *, tenant_id: str, ticket_id: str
    ) -> Optional[SLAState]:
        state = (
            self.db.query(SLAState)
            .filter(SLAState.ticket_id == ticket_id)
            .first()
        )
        if state is None:
            return None
        if state.tenant_id != tenant_id:
            raise TenantAccessError("SLAState", ticket_id, tenant_id)
        return state

    def update(
        self,
        *,
        tenant_id: str,
        ticket_id: str,
        status: Optional[str] = None,
        acknowledged_at: Optional[datetime] = None,
        in_progress_at: Optional[datetime] = None,
        resolved_at: Optional[datetime] = None,
        breached: Optional[bool] = None,
        breached_at: Optional[datetime] = None,
    ) -> SLAState:
        state = self.get_by_ticket_id(tenant_id=tenant_id, ticket_id=ticket_id)
        if state is None:
            raise ValueError(f"SLAState for ticket {ticket_id!r} not found")
        if status is not None:
            state.status = status
        if acknowledged_at is not None:
            state.acknowledged_at = acknowledged_at
        if in_progress_at is not None:
            state.in_progress_at = in_progress_at
        if resolved_at is not None:
            state.resolved_at = resolved_at
        if breached is not None:
            state.breached = breached
        if breached_at is not None:
            state.breached_at = breached_at
        self.db.commit()
        self.db.refresh(state)
        return state
