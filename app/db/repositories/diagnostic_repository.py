import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.db.exceptions import TenantAccessError
from app.db.models import DataClassification, Diagnostic


class DiagnosticRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self,
        *,
        tenant_id: str,
        ticket_id: str,
        field_name: str,
        field_value: str,
        classification: DataClassification = DataClassification.INTERNAL,
    ) -> Diagnostic:
        diag = Diagnostic(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            ticket_id=ticket_id,
            field_name=field_name,
            field_value=field_value,
            classification=classification.value,
            collected_at=datetime.utcnow(),
        )
        self.db.add(diag)
        self.db.commit()
        self.db.refresh(diag)
        return diag

    def get_by_id(self, *, tenant_id: str, diagnostic_id: str) -> Optional[Diagnostic]:
        diag = self.db.get(Diagnostic, diagnostic_id)
        if diag is None:
            return None
        if diag.tenant_id != tenant_id:
            raise TenantAccessError("Diagnostic", diagnostic_id, tenant_id)
        return diag

    def list_by_ticket(self, *, tenant_id: str, ticket_id: str) -> list[Diagnostic]:
        return (
            self.db.query(Diagnostic)
            .filter(
                Diagnostic.tenant_id == tenant_id,
                Diagnostic.ticket_id == ticket_id,
            )
            .order_by(Diagnostic.collected_at.asc())
            .all()
        )
