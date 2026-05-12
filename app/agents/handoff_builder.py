from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from app.agents.diagnostics_collector import DiagnosticsResult
from app.agents.escalation_engine import EscalationResult
from app.agents.first_response_generator import FirstResponse
from app.agents.sla_tracker import SLAStatus
from app.db.models import DataClassification
from app.schemas.events import InboundEvent
from app.services.communication_policy import CommDecision

# Only PUBLIC and INTERNAL diagnostic values appear in the handoff packet.
# CONFIDENTIAL (e.g. ip_address) and RESTRICTED values are never included.
_SAFE_CLASSIFICATIONS = frozenset(
    {DataClassification.PUBLIC, DataClassification.INTERNAL}
)


@dataclass
class HandoffPacket:
    """
    Structured context packet for Tier 2 / human review.

    Satisfies FR-24 (context packet: goal, attempts, diagnostics, SLA state,
    suggested next action) and FR-25 (handoff at any workflow point).

    CONFIDENTIAL and RESTRICTED diagnostic values are never included in any field.
    This packet is stored on OrchestratorResult and is never sent externally.
    """

    # Identity
    tenant_id: str
    ticket_id: Optional[str]
    handoff_reason: str                         # why handoff was triggered

    # Contact / channel (from InboundEvent — no credentials)
    channel: str
    contact_id: str
    external_id: str

    # Customer intent
    customer_goal: str                          # original event subject

    # Classification
    category: str
    severity: str
    component: str
    confidence_score: float
    classification_reasoning: str

    # Routing
    routing_action: str                         # "tier1" | "tier2"
    routing_reason: str

    # Automation trace — steps attempted before handoff
    attempted_steps: list[str]

    # Diagnostics: PUBLIC + INTERNAL fields only
    diagnostics_summary: dict[str, str]         # field_name → value
    missing_diagnostics_fields: list[str]
    follow_up_questions: list[str]

    # Knowledge base
    kb_article_id: Optional[str]
    kb_article_title: Optional[str]
    kb_no_match_reason: Optional[str]

    # First response
    first_response_status: str                  # "sent" | "suppressed" | "not_generated"

    # SLA summary (no raw DB records exposed)
    sla_state: Optional[str]
    sla_response_deadline: Optional[str]        # ISO string or None
    sla_resolution_deadline: Optional[str]
    sla_response_breached: Optional[bool]
    sla_resolution_breached: Optional[bool]

    # Escalation summary
    escalation_chain_found: Optional[bool]
    escalation_actions_count: Optional[int]

    # Recommended action for the human engineer
    suggested_next_action: str

    # Packet creation time (UTC ISO-8601)
    created_at: str


class HandoffBuilder:
    """
    Builds deterministic HandoffPacket objects for Tier 2 / human review.

    All output is deterministic: same inputs always produce the same packet
    (except created_at, which records wall-clock time).

    CONFIDENTIAL and RESTRICTED diagnostic values are excluded from the packet.
    The packet is never sent externally — callers store it on OrchestratorResult.
    """

    def build(
        self,
        event: InboundEvent,
        *,
        action: str,
        reason: str,
        classification,
        ticket_id: Optional[str],
        diagnostics_result: Optional[DiagnosticsResult],
        first_response: Optional[FirstResponse],
        follow_up_questions: list[str],
        sla_status: Optional[SLAStatus],
        escalation_result: Optional[EscalationResult],
        comm_decision: Optional[CommDecision],
    ) -> HandoffPacket:
        now = datetime.now(timezone.utc).isoformat()

        # Diagnostics: PUBLIC + INTERNAL only — CONFIDENTIAL/RESTRICTED excluded.
        diag_summary: dict[str, str] = {}
        missing_fields: list[str] = []
        follow_up_qs: list[str] = list(follow_up_questions) if follow_up_questions else []

        if diagnostics_result is not None:
            for df in diagnostics_result.fields:
                if df.classification in _SAFE_CLASSIFICATIONS:
                    diag_summary[df.name] = str(df.value)
            missing_fields = list(diagnostics_result.missing_required)
            if not follow_up_qs:
                follow_up_qs = list(diagnostics_result.follow_up_questions)

        # Knowledge base information.
        kb_article_id: Optional[str] = None
        kb_article_title: Optional[str] = None
        kb_no_match_reason: Optional[str] = None

        if first_response is not None:
            if not first_response.is_fallback:
                kb_article_id = first_response.kb_article_id
                kb_article_title = first_response.kb_article_title
            else:
                kb_no_match_reason = "no_kb_match_found"
        elif reason == "no_kb_match":
            kb_no_match_reason = "no_kb_match"
        elif diagnostics_result is not None and not diagnostics_result.is_complete:
            kb_no_match_reason = "kb_not_attempted_diagnostics_incomplete"
        else:
            kb_no_match_reason = "kb_not_attempted"

        # First response status.
        if first_response is not None:
            first_response_status = "sent"
        elif comm_decision is not None and not comm_decision.allowed:
            first_response_status = "suppressed"
        else:
            first_response_status = "not_generated"

        # SLA summary — no raw SLAState DB records exposed.
        sla_state: Optional[str] = None
        sla_response_deadline: Optional[str] = None
        sla_resolution_deadline: Optional[str] = None
        sla_response_breached: Optional[bool] = None
        sla_resolution_breached: Optional[bool] = None

        if sla_status is not None:
            sla_state = sla_status.state
            sla_response_deadline = sla_status.response_deadline.isoformat()
            sla_resolution_deadline = sla_status.resolution_deadline.isoformat()
            sla_response_breached = sla_status.response_breached
            sla_resolution_breached = sla_status.resolution_breached

        # Escalation summary.
        escalation_chain_found: Optional[bool] = None
        escalation_actions_count: Optional[int] = None

        if escalation_result is not None:
            escalation_chain_found = escalation_result.chain_found
            escalation_actions_count = len(escalation_result.actions)

        return HandoffPacket(
            tenant_id=event.tenant_id,
            ticket_id=ticket_id,
            handoff_reason=reason,
            channel=event.channel.value,
            contact_id=event.contact_id,
            external_id=event.external_id,
            customer_goal=event.subject,
            category=classification.category.value,
            severity=classification.severity,
            component=classification.component,
            confidence_score=classification.confidence_score,
            classification_reasoning=classification.reasoning,
            routing_action=action,
            routing_reason=reason,
            attempted_steps=self._build_attempted_steps(
                reason=reason,
                diagnostics_result=diagnostics_result,
                first_response=first_response,
                sla_status=sla_status,
                escalation_result=escalation_result,
            ),
            diagnostics_summary=diag_summary,
            missing_diagnostics_fields=missing_fields,
            follow_up_questions=follow_up_qs,
            kb_article_id=kb_article_id,
            kb_article_title=kb_article_title,
            kb_no_match_reason=kb_no_match_reason,
            first_response_status=first_response_status,
            sla_state=sla_state,
            sla_response_deadline=sla_response_deadline,
            sla_resolution_deadline=sla_resolution_deadline,
            sla_response_breached=sla_response_breached,
            sla_resolution_breached=sla_resolution_breached,
            escalation_chain_found=escalation_chain_found,
            escalation_actions_count=escalation_actions_count,
            suggested_next_action=self._suggest_next_action(
                reason=reason,
                classification=classification,
                sla_status=sla_status,
                event=event,
            ),
            created_at=now,
        )

    # ── Private helpers ───────────────────────────────────────────────────────

    def _build_attempted_steps(
        self,
        *,
        reason: str,
        diagnostics_result: Optional[DiagnosticsResult],
        first_response: Optional[FirstResponse],
        sla_status: Optional[SLAStatus],
        escalation_result: Optional[EscalationResult],
    ) -> list[str]:
        steps = ["classification"]
        if diagnostics_result is not None:
            steps.append("diagnostics_collection")
        if first_response is not None or reason == "no_kb_match":
            steps.append("kb_retrieval")
        if first_response is not None:
            steps.append("first_response_generated")
        if sla_status is not None:
            steps.append("sla_initialized")
        if escalation_result is not None:
            steps.append("escalation_triggered")
        return steps

    def _suggest_next_action(
        self,
        *,
        reason: str,
        classification,
        sla_status: Optional[SLAStatus],
        event: InboundEvent,
    ) -> str:
        if reason == "low_confidence":
            return (
                f"Manually review and classify the message from "
                f"{event.contact_id} (channel: {event.channel.value}): "
                f'"{event.subject}". Assign to the appropriate support team.'
            )
        if reason == "injection_flagged":
            return (
                f"Review the message from {event.contact_id} for potential "
                "prompt injection. Verify customer intent before processing. "
                "Do not auto-route this event."
            )
        if reason == "customer_requested_human":
            return (
                f"Customer {event.contact_id} explicitly requested a human agent "
                f"via {event.channel.value}. Contact regarding: "
                f'"{event.subject}".'
            )
        if reason == "no_kb_match":
            return (
                f"No KB article found for this {classification.component} issue "
                f"(severity {classification.severity}). Investigate manually and "
                "create a runbook entry if the resolution is novel."
            )
        if sla_status is not None and (
            sla_status.response_breached or sla_status.resolution_breached
        ):
            return (
                f"SLA BREACH detected for this {classification.severity} incident. "
                "Immediate response required. Check escalation chain contacts."
            )
        return (
            f"Review this {classification.category.value} event "
            f"(severity {classification.severity}, "
            f"component {classification.component}) "
            "and route to the appropriate team."
        )
