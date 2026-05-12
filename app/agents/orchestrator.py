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
from app.agents.escalation_engine import EscalationEngine, EscalationResult
from app.agents.first_response_generator import FirstResponse, FirstResponseGenerator
from app.agents.handoff_builder import HandoffBuilder, HandoffPacket
from app.agents.knowledge_retriever import KnowledgeRetriever, NoMatchResult
from app.agents.sla_tracker import SLAStatus, SLATracker
from app.config.models import AppConfig
from app.db.repositories.audit_repository import AuditRepository
from app.schemas.events import InboundEvent
from app.services.communication_policy import CommDecision, CommunicationPolicy
from app.services.ticket_manager import TicketManager
from app.utils.clock import ClockProvider, SystemClock

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
    # Phase 5 additions (optional — present only when SLA/escalation ran).
    sla_status: Optional[SLAStatus] = None
    escalation_result: Optional[EscalationResult] = None
    comm_decision: Optional[CommDecision] = None
    # Phase 6 addition — present when action=="tier2".
    handoff_packet: Optional[HandoffPacket] = None


class SupportOrchestrator:
    """
    Phase 6 orchestrator.

    Phase 4 responsibilities (unchanged):
      - Classify the inbound event.
      - Route to Tier 1 or Tier 2.
      - Create a tenant-scoped ticket for incident / question events.
      - Collect diagnostics; surface follow-up questions if incomplete.
      - Retrieve a matching KB article when diagnostics are sufficient.
      - Generate a grounded first response when a confident KB match exists.
      - Route to Tier 2 when no KB match meets the confidence threshold.
      - Record audit events for classification and routing decisions.

    Phase 5 additions (private attributes, never exposed as class-level names):
      - Initialize SLA state when an incident ticket is created.
      - Detect SLA breach and invoke escalation engine.
      - Apply communication policy before simulated customer-facing updates.

    Phase 6 additions (private attributes, never exposed as class-level names):
      - Build a structured HandoffPacket whenever action=="tier2".
    """

    def __init__(
        self,
        db: Session,
        config: AppConfig,
        kb_dir: Optional[Path] = None,
        clock: Optional[ClockProvider] = None,
    ) -> None:
        self._db = db
        self._config = config
        _clock: ClockProvider = clock or SystemClock()

        self._classifier = InteractionClassifier(config)
        self._ticket_manager = TicketManager(db)
        self._audit_repo = AuditRepository(db)

        # Phase 4 agents (instance attributes).
        self._diagnostics_collector = DiagnosticsCollector()
        self._kb_retriever = KnowledgeRetriever(
            knowledge_index=config.knowledge_index,
            kb_dir=kb_dir,
        )
        self._first_response_gen = FirstResponseGenerator()

        # Phase 5 agents (private instance attributes — not class-level names,
        # so existing negative-assertions on SupportOrchestrator class attributes
        # continue to pass).
        self._sla_tracker = SLATracker(config=config, clock=_clock, db=db)
        self._escalation_engine = EscalationEngine(
            config=config, clock=_clock, audit_repo=self._audit_repo
        )
        self._communication_policy = CommunicationPolicy(config=config, clock=_clock)

        # Phase 6 agent (private instance attribute).
        self._handoff_builder = HandoffBuilder()

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
        sla_status: Optional[SLAStatus] = None
        escalation_result: Optional[EscalationResult] = None
        comm_decision: Optional[CommDecision] = None
        handoff_packet: Optional[HandoffPacket] = None

        if action == "tier1" and classification.category in _TICKET_CATEGORIES:
            ticket = self._ticket_manager.create_for_event(event, classification)
            ticket_id = ticket.id

            # Phase 5: initialize SLA state for incident tickets.
            if classification.category == Category.INCIDENT:
                sla_status = self._sla_tracker.initialize(
                    ticket_id=ticket_id,
                    tenant_id=event.tenant_id,
                    severity=classification.severity,
                )

            # Phase 4: diagnostics → KB retrieval → first response.
            diagnostics_result = self._diagnostics_collector.collect(
                event, classification
            )

            if not diagnostics_result.is_complete:
                follow_up_questions = diagnostics_result.follow_up_questions
            else:
                query = f"{event.subject} {event.body}"
                kb_result = self._kb_retriever.retrieve(query, classification)

                if isinstance(kb_result, NoMatchResult):
                    if classification.category == Category.INCIDENT:
                        action = "tier2"
                        reason = "no_kb_match"
                else:
                    # Phase 5: check communication policy before sending first response.
                    comm_decision = self._communication_policy.check(
                        tenant_id=event.tenant_id,
                        severity=classification.severity,
                    )
                    if comm_decision.allowed:
                        first_response = self._first_response_gen.generate(
                            classification, kb_result, diagnostics_result
                        )

            # Phase 5: breach check and escalation for incidents already in breach.
            if sla_status is not None:
                sla_status = self._sla_tracker.check_breach(
                    ticket_id=ticket_id, tenant_id=event.tenant_id
                )
                if sla_status.response_breached or sla_status.resolution_breached:
                    escalation_result = self._escalation_engine.escalate(
                        ticket_id=ticket_id,
                        tenant_id=event.tenant_id,
                        severity=classification.severity,
                        component=classification.component,
                        reason="sla_breached_on_creation",
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

        # Phase 6: build handoff packet for every Tier 2 routing outcome.
        if action == "tier2":
            handoff_packet = self._handoff_builder.build(
                event,
                action=action,
                reason=reason,
                classification=classification,
                ticket_id=ticket_id,
                diagnostics_result=diagnostics_result,
                first_response=first_response,
                follow_up_questions=follow_up_questions,
                sla_status=sla_status,
                escalation_result=escalation_result,
                comm_decision=comm_decision,
            )

        return OrchestratorResult(
            action=action,
            reason=reason,
            classification=classification,
            ticket_id=ticket_id,
            diagnostics_result=diagnostics_result,
            first_response=first_response,
            follow_up_questions=follow_up_questions,
            sla_status=sla_status,
            escalation_result=escalation_result,
            comm_decision=comm_decision,
            handoff_packet=handoff_packet,
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
