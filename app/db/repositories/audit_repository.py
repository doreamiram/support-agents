import hashlib
import json
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.db.exceptions import TenantAccessError
from app.db.models import AuditEvent


def _compute_hash(
    previous_hash: str,
    event_type: str,
    actor: str,
    payload_json: str,
    created_at_iso: str,
) -> str:
    content = "|".join([previous_hash, event_type, actor, payload_json, created_at_iso])
    return hashlib.sha256(content.encode()).hexdigest()


class AuditRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def append(
        self,
        *,
        tenant_id: Optional[str],
        event_type: str,
        actor: str,
        payload: dict,
    ) -> AuditEvent:
        prev = (
            self.db.query(AuditEvent)
            .filter(AuditEvent.tenant_id == tenant_id)
            .order_by(AuditEvent.id.desc())
            .first()
        )
        prev_hash = prev.current_hash if prev else ""
        now = datetime.utcnow()
        payload_json = json.dumps(payload, sort_keys=True)
        current_hash = _compute_hash(
            prev_hash, event_type, actor, payload_json, now.isoformat()
        )
        event = AuditEvent(
            tenant_id=tenant_id,
            event_type=event_type,
            actor=actor,
            payload_json=payload_json,
            previous_hash=prev_hash,
            current_hash=current_hash,
            created_at=now,
        )
        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)
        return event

    def get_by_id(self, *, tenant_id: str, event_id: int) -> Optional[AuditEvent]:
        event = self.db.get(AuditEvent, event_id)
        if event is None:
            return None
        if event.tenant_id != tenant_id:
            raise TenantAccessError("AuditEvent", event_id, tenant_id)
        return event

    def list_by_tenant(self, *, tenant_id: str) -> list[AuditEvent]:
        return (
            self.db.query(AuditEvent)
            .filter(AuditEvent.tenant_id == tenant_id)
            .order_by(AuditEvent.id.asc())
            .all()
        )

    def verify_chain(self, *, tenant_id: str) -> tuple[bool, str]:
        events = self.list_by_tenant(tenant_id=tenant_id)
        if not events:
            return True, "Chain is empty — nothing to verify"

        prev_hash = ""
        for i, event in enumerate(events):
            if event.previous_hash != prev_hash:
                return False, (
                    f"Chain break at position {i} (event id={event.id}): "
                    f"previous_hash does not match prior current_hash"
                )
            expected = _compute_hash(
                event.previous_hash,
                event.event_type,
                event.actor,
                event.payload_json,
                event.created_at.isoformat(),
            )
            if event.current_hash != expected:
                return False, (
                    f"Chain break at position {i} (event id={event.id}): "
                    f"current_hash mismatch — record may have been tampered"
                )
            prev_hash = event.current_hash

        return True, f"Chain valid — {len(events)} event(s) verified"
