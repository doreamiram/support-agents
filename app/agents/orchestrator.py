from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from app.agents.classifier import (
    Category,
    ClassificationResult,
    InteractionClassifier,
    check_human_requested,
)
from app.agents.diagnostics_collector import DiagnosticsCollector, DiagnosticsResult
from app.agents.first_response_generator import FirstResponse, FirstResponseGenerator
from app.agents.knowledge_retriever import KnowledgeRetriever, NoMatchResult
from app.config.models import AppConfig
from app.db.repositories.audit_repository import AuditRepository
from app.schemas.events import InboundEvent
from app.services.ticket_manager import TicketManager

# Categories that stay in Tier 1 (automated).
_TIER1_CATEGORIES: frozenset[Category] = frozenset(
    {Category.INCIDENT, Category.QUESTION, Category.FOLLOW_UP, Category.NOISE}
)

# Categories for which a new ticket is created and Phase 4 processing runs.
_TICKET_CATEGORIES: frozenset[Category] = frozenset(
    {Category.INCIDENT, Category.QUESTION}
)


@dataclass
class OrchestratorResult:
    action: str                                    # "tier1" | "tier2"
    reason: str
    classification: ClassificationResult
    ticket_id: Optional[str] = None
    diagnostics_result: Optional[DiagnosticsResult] = None
    first_response: Optional[FirstResponse] = None
    follow_up_questions: list[str] = field(default_factory=list)


class SupportOrchestrator:
    """
    Phase 4 orchestrator.

    Responsibilities (this phase):
      - Classify the inbound event.
      - Route to Tier 1 (automated) or Tier 2 (human loop-in).
      - Create a tenant-scoped ticket for incident / question events routed to Tier 1.
      - Collect diagnostics from the event; surface follow-up questions if incomplete.
      - Retrieve a matching KB article when diagnostics are sufficient.
      - Generate a grounded first response when a confident KB match exists.
      - Route to Tier 2 when no KB match meets the confidence threshold.
      - Record audit events for classification and routing decisions.

    NOT implemented (deferred to later phases):
      - SLA tracking (Phase 5)
      - Escalation engine (Phase 5)
      - Communication policy (Phase 5)
      - Human handoff packet builder (Phase 6)
    """

    def __init__(
        self,
        db: Session,
        config: AppConfig,
        kb_dir: Optional[Path] = None,
    ) -> None:
        self._db = db
        self._config = config
        self._classifier = InteractionClassifier(config)
        self._ticket_manager = TicketManager(db)
        self._audit_repo = AuditRepository(db)
        # Phase 4 agents (instance attributes, not class-level).
        self._diagnostics_collector = DiagnosticsCollector()
        self._kb_retriever = KnowledgeRetriever(
            knowledge_index=config.knowledge_index,
            kb_dir=kb_dir,
        )
        self._first_response_gen = FirstResponseGenerator()

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
        diagnostics_result: Optional[DiagnosticsResult] = None
        first_response: Optional[FirstResponse] = None
        follow_up_questions: list[str] = []

        if action == "tier1" and classification.category in _TICKET_CATEGORIES:
            ticket = self._ticket_manager.create_for_event(event, classification)
            ticket_id = ticket.id

            # Phase 4: diagnostics → KB retrieval → first response.
            diagnostics_result = self._diagnostics_collector.collect(
                event, classification
            )

            if not diagnostics_result.is_complete:
                # Surface follow-up questions; skip KB retrieval until they are answered.
                follow_up_questions = diagnostics_result.follow_up_questions
            else:
                query = f"{event.subject} {event.body}"
                kb_result = self._kb_retriever.retrieve(query, classification)

                if isinstance(kb_result, NoMatchResult):
                    # KB miss on incidents routes to Tier 2 for engineer review.
                    # Questions without a KB match stay Tier 1 (no invented guidance).
                    if classification.category == Category.INCIDENT:
                        action = "tier2"
                        reason = "no_kb_match"
                else:
                    first_response = self._first_response_gen.generate(
                        classification, kb_result, diagnostics_result
                    )

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
            diagnostics_result=diagnostics_result,
            first_response=first_response,
            follow_up_questions=follow_up_questions,
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
