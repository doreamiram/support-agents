from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from sqlalchemy.orm import Session

from app.agents.classifier import (
    Category,
    ClassificationResult,
    InteractionClassifier,
    check_human_requested,
)
from app.config.models import AppConfig
from app.db.repositories.audit_repository import AuditRepository
from app.schemas.events import InboundEvent
from app.services.ticket_manager import TicketManager

# Categories that stay in Tier 1 (automated).
_TIER1_CATEGORIES: frozenset[Category] = frozenset(
    {Category.INCIDENT, Category.QUESTION, Category.FOLLOW_UP, Category.NOISE}
)

# Categories for which a new ticket is created.
_TICKET_CATEGORIES: frozenset[Category] = frozenset(
    {Category.INCIDENT, Category.QUESTION}
)


@dataclass
class OrchestratorResult:
    action: str                       # "tier1" | "tier2"
    reason: str
    classification: ClassificationResult
    ticket_id: Optional[str] = None


class SupportOrchestrator:
    """
    Phase 3 orchestrator.

    Responsibilities (this phase):
      - Classify the inbound event.
      - Route to Tier 1 (automated) or Tier 2 (human loop-in).
      - Create a tenant-scoped ticket for incident / question events routed to Tier 1.
      - Record audit events for classification and routing decisions.

    NOT implemented (deferred to later phases):
      - Diagnostics collection (Phase 4)
      - Knowledge retrieval (Phase 4)
      - First response generation (Phase 4)
      - SLA tracking (Phase 5)
      - Escalation engine (Phase 5)
      - Communication policy (Phase 5)
      - Human handoff packet builder (Phase 6)
    """

    def __init__(self, db: Session, config: AppConfig) -> None:
        self._db = db
        self._config = config
        self._classifier = InteractionClassifier(config)
        self._ticket_manager = TicketManager(db)
        self._audit_repo = AuditRepository(db)

    def process(self, event: InboundEvent) -> OrchestratorResult:
        classification = self._classifier.classify(event)

        self._audit_repo.append(
            tenant_id=event.tenant_id,
            event_type="classification_completed",
            actor="orchestrator",
            payload={
                "event_id": event.event_id,
                "category": classification.category.value,
                "severity": classification.severity,
                "component": classification.component,
                "confidence_score": classification.confidence_score,
                "reasoning": classification.reasoning,
            },
        )

        action, reason = self._route(event, classification)

        ticket_id: Optional[str] = None
        if action == "tier1" and classification.category in _TICKET_CATEGORIES:
            ticket = self._ticket_manager.create_for_event(event, classification)
            ticket_id = ticket.id

        self._audit_repo.append(
            tenant_id=event.tenant_id,
            event_type="routing_decision",
            actor="orchestrator",
            payload={
                "event_id": event.event_id,
                "action": action,
                "reason": reason,
                "ticket_id": ticket_id,
            },
        )

        return OrchestratorResult(
            action=action,
            reason=reason,
            classification=classification,
            ticket_id=ticket_id,
        )

    def _route(
        self,
        event: InboundEvent,
        classification: ClassificationResult,
    ) -> tuple[str, str]:
        if event.injection_flagged:
            return "tier2", "injection_flagged"
        if check_human_requested(event):
            return "tier2", "customer_requested_human"
        if classification.category == Category.LOW_CONFIDENCE:
            return "tier2", "low_confidence"
        if classification.category not in _TIER1_CATEGORIES:
            return "tier2", "unknown_category"
        return "tier1", classification.category.value
