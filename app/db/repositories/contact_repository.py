import uuid
from typing import Optional

from sqlalchemy.orm import Session

from app.db.exceptions import TenantAccessError
from app.db.models import Contact


class ContactRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self,
        *,
        tenant_id: str,
        channel: str,
        external_id: str,
        name: str,
        role: str,
        verified: bool = False,
        email: Optional[str] = None,
    ) -> Contact:
        contact = Contact(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            channel=channel,
            external_id=external_id,
            name=name,
            role=role,
            verified=verified,
            email=email,
        )
        self.db.add(contact)
        self.db.commit()
        self.db.refresh(contact)
        return contact

    def get_by_id(self, *, tenant_id: str, contact_id: str) -> Optional[Contact]:
        contact = self.db.get(Contact, contact_id)
        if contact is None:
            return None
        if contact.tenant_id != tenant_id:
            raise TenantAccessError("Contact", contact_id, tenant_id)
        return contact

    def get_by_external_id(
        self, *, tenant_id: str, channel: str, external_id: str
    ) -> Optional[Contact]:
        return (
            self.db.query(Contact)
            .filter(
                Contact.tenant_id == tenant_id,
                Contact.channel == channel,
                Contact.external_id == external_id,
            )
            .first()
        )

    def list_by_tenant(self, *, tenant_id: str) -> list[Contact]:
        return (
            self.db.query(Contact)
            .filter(Contact.tenant_id == tenant_id)
            .all()
        )
