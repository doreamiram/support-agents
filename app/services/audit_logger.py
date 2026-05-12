from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from sqlalchemy.orm import Session

from app.db.models import AuditEvent
from app.db.repositories.audit_repository import AuditRepository


@dataclass
class VerificationResult:
    """Result of an audit chain verification."""

    valid: bool
    event_count: int
    message: str
    chain_breaks: list[str] = field(default_factory=list)


class AuditLogger:
    """
    Thin service wrapper around AuditRepository.

    Satisfies NFR-05 (every action audited) and NFR-06 (tamper-evident trail).

    Exposes:
      - append()       — write a new audit event (delegates to AuditRepository)
      - list_events()  — list tenant-scoped events
      - verify_chain() — verify the tamper-evident hash chain; returns
                         VerificationResult without exposing raw payload content

    Tenant isolation and hash-chain logic live in AuditRepository; this class
    only wraps them with a cleaner return type for the API layer.
    """

    def __init__(self, db: Session) -> None:
        self._repo = AuditRepository(db)

    def append(
        self,
        *,
        tenant_id: Optional[str],
        event_type: str,
        actor: str,
        payload: dict,
    ) -> AuditEvent:
        """Write a new audit event through the underlying repository."""
        return self._repo.append(
            tenant_id=tenant_id,
            event_type=event_type,
            actor=actor,
            payload=payload,
        )

    def list_events(self, *, tenant_id: str) -> list[AuditEvent]:
        """Return all audit events for the given tenant, in insertion order."""
        return self._repo.list_by_tenant(tenant_id=tenant_id)

    def verify_chain(self, *, tenant_id: str) -> VerificationResult:
        """
        Verify the tamper-evident hash chain for a single tenant.

        Returns a VerificationResult with:
          - valid:        True when every event's hash matches the previous.
          - event_count:  Number of events examined.
          - message:      Human-readable summary from the repository.
          - chain_breaks: Empty list when valid; contains the break description
                          when a mismatch is detected.

        Never exposes raw audit payload content.
        """
        events = self._repo.list_by_tenant(tenant_id=tenant_id)
        valid, message = self._repo.verify_chain(tenant_id=tenant_id)
        breaks: list[str] = [] if valid else [message]
        return VerificationResult(
            valid=valid,
            event_count=len(events),
            message=message,
            chain_breaks=breaks,
        )
