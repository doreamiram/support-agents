from __future__ import annotations

from sqlalchemy.orm import Session

from app.agents.classifier import ClassificationResult
from app.db.models import Ticket
from app.db.repositories.ticket_repository import TicketRepository
from app.schemas.events import InboundEvent


class TicketManager:
    """
    Thin service that creates tickets through the repository layer only.
    Tenant isolation is enforced by TicketRepository; this class never
    bypasses it.
    """

    def __init__(self, db: Session) -> None:
        self._repo = TicketRepository(db)

    def create_for_event(
        self,
        event: InboundEvent,
        classification: ClassificationResult,
    ) -> Ticket:
        return self._repo.create(
            tenant_id=event.tenant_id,
            channel=event.channel.value,
            severity=classification.severity,
            category=classification.category.value,
            component=classification.component,
            subject=event.subject,
            description=event.body,
        )
