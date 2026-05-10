import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.db.exceptions import TenantAccessError
from app.db.models import Ticket


class TicketRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self,
        *,
        tenant_id: str,
        channel: str,
        severity: str,
        status: str = "OPEN",
        category: str = "",
        component: str = "",
        subject: str = "",
        description: str = "",
    ) -> Ticket:
        now = datetime.utcnow()
        ticket = Ticket(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            channel=channel,
            severity=severity,
            status=status,
            category=category,
            component=component,
            subject=subject,
            description=description,
            created_at=now,
            updated_at=now,
        )
        self.db.add(ticket)
        self.db.commit()
        self.db.refresh(ticket)
        return ticket

    def get_by_id(self, *, tenant_id: str, ticket_id: str) -> Optional[Ticket]:
        ticket = self.db.get(Ticket, ticket_id)
        if ticket is None:
            return None
        if ticket.tenant_id != tenant_id:
            raise TenantAccessError("Ticket", ticket_id, tenant_id)
        return ticket

    def list_by_tenant(self, *, tenant_id: str) -> list[Ticket]:
        return (
            self.db.query(Ticket)
            .filter(Ticket.tenant_id == tenant_id)
            .order_by(Ticket.created_at.desc())
            .all()
        )

    def update_status(self, *, tenant_id: str, ticket_id: str, status: str) -> Ticket:
        ticket = self.get_by_id(tenant_id=tenant_id, ticket_id=ticket_id)
        if ticket is None:
            raise ValueError(f"Ticket {ticket_id!r} not found")
        ticket.status = status
        ticket.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(ticket)
        return ticket
