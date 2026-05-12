"""Tests for HandoffBuilder and HandoffPacket (Phase 6).

Covers:
  - All required fields present on the packet
  - CONFIDENTIAL / RESTRICTED diagnostic values excluded
  - PUBLIC / INTERNAL diagnostic values included
  - suggested_next_action generated for every handoff reason
  - attempted_steps reflect what actually ran
  - Packets for low_confidence, customer_requested_human, no_kb_match, injection_flagged
"""

from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.agents.classifier import Category, ClassificationResult
from app.agents.diagnostics_collector import DiagnosticField, DiagnosticsResult
from app.agents.escalation_engine import EscalationResult
from app.agents.first_response_generator import FirstResponse
from app.agents.handoff_builder import HandoffBuilder, HandoffPacket
from app.agents.sla_tracker import SLAStatus
from app.db.models import DataClassification
from app.schemas.events import Channel, InboundEvent
from app.services.communication_policy import CommDecision


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_event(
    subject: str = "The auth service is failing",
    body: str = "Cannot authenticate. Error 503.",
    tenant_id: str = "acme-corp",
    contact_id: str = "alice.chen",
    channel: Channel = Channel.SLACK,
    external_id: str = "U0ACM001",
    injection_flagged: bool = False,
) -> InboundEvent:
    return InboundEvent(
        event_id="evt-hb-001",
        tenant_id=tenant_id,
        contact_id=contact_id,
        channel=channel,
        external_id=external_id,
        timestamp=datetime.now(timezone.utc),
        subject=subject,
        body=body,
        raw_payload={},
        injection_flagged=injection_flagged,
    )


def _make_classification(
    category: Category = Category.INCIDENT,
    severity: str = "P2",
    component: str = "auth-service",
    confidence: float = 0.80,
    reasoning: str = "Matched incident patterns",
) -> ClassificationResult:
    return ClassificationResult(
        category=category,
        severity=severity,
        component=component,
        confidence_score=confidence,
        reasoning=reasoning,
    )


def _make_sla_status(
    ticket_id: str = "ticket-001",
    state: str = "OPEN",
    response_breached: bool = False,
    resolution_breached: bool = False,
) -> SLAStatus:
    now = datetime.now(timezone.utc)
    from datetime import timedelta
    return SLAStatus(
        ticket_id=ticket_id,
        tenant_id="acme-corp",
        severity="P2",
        state=state,
        response_deadline=now + timedelta(hours=4),
        resolution_deadline=now + timedelta(hours=24),
        response_breached=response_breached,
        resolution_breached=resolution_breached,
        engineer_notified=False,
        engineer_engaged=False,
        created_at=now,
        checked_at=now,
    )


def _make_diagnostics_result(
    include_confidential: bool = False,
) -> DiagnosticsResult:
    fields = [
        DiagnosticField(
            name="channel",
            value="slack",
            classification=DataClassification.PUBLIC,
        ),
        DiagnosticField(
            name="severity",
            value="P2",
            classification=DataClassification.INTERNAL,
        ),
        DiagnosticField(
            name="component",
            value="auth-service",
            classification=DataClassification.INTERNAL,
        ),
    ]
    if include_confidential:
        fields.append(DiagnosticField(
            name="ip_address",
            value="10.0.0.42",
            classification=DataClassification.CONFIDENTIAL,
        ))
    return DiagnosticsResult(
        fields=fields,
        missing_required=[],
        follow_up_questions=[],
        is_complete=True,
    )


@pytest.fixture
def builder() -> HandoffBuilder:
    return HandoffBuilder()


# ── Required fields ───────────────────────────────────────────────────────────

class TestHandoffPacketFields:
    """All required fields must be present on every HandoffPacket."""

    def test_packet_has_tenant_id(self, builder):
        packet = builder.build(
            _make_event(),
            action="tier2",
            reason="low_confidence",
            classification=_make_classification(category=Category.LOW_CONFIDENCE),
            ticket_id=None,
            diagnostics_result=None,
            first_response=None,
            follow_up_questions=[],
            sla_status=None,
            escalation_result=None,
            comm_decision=None,
        )
        assert packet.tenant_id == "acme-corp"

    def test_packet_has_ticket_id_field(self, builder):
        packet = builder.build(
            _make_event(),
            action="tier2",
            reason="low_confidence",
            classification=_make_classification(category=Category.LOW_CONFIDENCE),
            ticket_id="ticket-123",
            diagnostics_result=None,
            first_response=None,
            follow_up_questions=[],
            sla_status=None,
            escalation_result=None,
            comm_decision=None,
        )
        assert packet.ticket_id == "ticket-123"

    def test_packet_ticket_id_none_when_not_created(self, builder):
        packet = builder.build(
            _make_event(),
            action="tier2",
            reason="low_confidence",
            classification=_make_classification(category=Category.LOW_CONFIDENCE),
            ticket_id=None,
            diagnostics_result=None,
            first_response=None,
            follow_up_questions=[],
            sla_status=None,
            escalation_result=None,
            comm_decision=None,
        )
        assert packet.ticket_id is None

    def test_packet_has_handoff_reason(self, builder):
        packet = builder.build(
            _make_event(),
            action="tier2",
            reason="low_confidence",
            classification=_make_classification(category=Category.LOW_CONFIDENCE),
            ticket_id=None,
            diagnostics_result=None,
            first_response=None,
            follow_up_questions=[],
            sla_status=None,
            escalation_result=None,
            comm_decision=None,
        )
        assert packet.handoff_reason == "low_confidence"

    def test_packet_has_channel(self, builder):
        packet = builder.build(
            _make_event(channel=Channel.JIRA),
            action="tier2",
            reason="low_confidence",
            classification=_make_classification(category=Category.LOW_CONFIDENCE),
            ticket_id=None,
            diagnostics_result=None,
            first_response=None,
            follow_up_questions=[],
            sla_status=None,
            escalation_result=None,
            comm_decision=None,
        )
        assert packet.channel == "jira"

    def test_packet_has_contact_id(self, builder):
        packet = builder.build(
            _make_event(contact_id="bob.smith"),
            action="tier2",
            reason="low_confidence",
            classification=_make_classification(category=Category.LOW_CONFIDENCE),
            ticket_id=None,
            diagnostics_result=None,
            first_response=None,
            follow_up_questions=[],
            sla_status=None,
            escalation_result=None,
            comm_decision=None,
        )
        assert packet.contact_id == "bob.smith"

    def test_packet_has_customer_goal(self, builder):
        packet = builder.build(
            _make_event(subject="Cannot login to dashboard"),
            action="tier2",
            reason="low_confidence",
            classification=_make_classification(category=Category.LOW_CONFIDENCE),
            ticket_id=None,
            diagnostics_result=None,
            first_response=None,
            follow_up_questions=[],
            sla_status=None,
            escalation_result=None,
            comm_decision=None,
        )
        assert packet.customer_goal == "Cannot login to dashboard"

    def test_packet_has_classification_fields(self, builder):
        clf = _make_classification(
            category=Category.INCIDENT,
            severity="P1",
            component="api-gateway",
            confidence=0.91,
            reasoning="Matched critical outage patterns",
        )
        packet = builder.build(
            _make_event(),
            action="tier2",
            reason="no_kb_match",
            classification=clf,
            ticket_id="t-001",
            diagnostics_result=_make_diagnostics_result(),
            first_response=None,
            follow_up_questions=[],
            sla_status=None,
            escalation_result=None,
            comm_decision=None,
        )
        assert packet.category == "incident"
        assert packet.severity == "P1"
        assert packet.component == "api-gateway"
        assert packet.confidence_score == 0.91
        assert "critical outage" in packet.classification_reasoning

    def test_packet_has_routing_fields(self, builder):
        packet = builder.build(
            _make_event(),
            action="tier2",
            reason="injection_flagged",
            classification=_make_classification(),
            ticket_id=None,
            diagnostics_result=None,
            first_response=None,
            follow_up_questions=[],
            sla_status=None,
            escalation_result=None,
            comm_decision=None,
        )
        assert packet.routing_action == "tier2"
        assert packet.routing_reason == "injection_flagged"

    def test_packet_has_attempted_steps(self, builder):
        packet = builder.build(
            _make_event(),
            action="tier2",
            reason="low_confidence",
            classification=_make_classification(category=Category.LOW_CONFIDENCE),
            ticket_id=None,
            diagnostics_result=None,
            first_response=None,
            follow_up_questions=[],
            sla_status=None,
            escalation_result=None,
            comm_decision=None,
        )
        assert isinstance(packet.attempted_steps, list)
        assert "classification" in packet.attempted_steps

    def test_packet_has_diagnostics_summary(self, builder):
        packet = builder.build(
            _make_event(),
            action="tier2",
            reason="low_confidence",
            classification=_make_classification(category=Category.LOW_CONFIDENCE),
            ticket_id=None,
            diagnostics_result=None,
            first_response=None,
            follow_up_questions=[],
            sla_status=None,
            escalation_result=None,
            comm_decision=None,
        )
        assert isinstance(packet.diagnostics_summary, dict)

    def test_packet_has_suggested_next_action(self, builder):
        packet = builder.build(
            _make_event(),
            action="tier2",
            reason="low_confidence",
            classification=_make_classification(category=Category.LOW_CONFIDENCE),
            ticket_id=None,
            diagnostics_result=None,
            first_response=None,
            follow_up_questions=[],
            sla_status=None,
            escalation_result=None,
            comm_decision=None,
        )
        assert isinstance(packet.suggested_next_action, str)
        assert len(packet.suggested_next_action) > 0

    def test_packet_has_created_at(self, builder):
        packet = builder.build(
            _make_event(),
            action="tier2",
            reason="low_confidence",
            classification=_make_classification(category=Category.LOW_CONFIDENCE),
            ticket_id=None,
            diagnostics_result=None,
            first_response=None,
            follow_up_questions=[],
            sla_status=None,
            escalation_result=None,
            comm_decision=None,
        )
        assert isinstance(packet.created_at, str)
        # Must be parseable as ISO-8601.
        datetime.fromisoformat(packet.created_at)

    def test_packet_is_handoff_packet_instance(self, builder):
        packet = builder.build(
            _make_event(),
            action="tier2",
            reason="low_confidence",
            classification=_make_classification(category=Category.LOW_CONFIDENCE),
            ticket_id=None,
            diagnostics_result=None,
            first_response=None,
            follow_up_questions=[],
            sla_status=None,
            escalation_result=None,
            comm_decision=None,
        )
        assert isinstance(packet, HandoffPacket)


# ── Data classification safety ─────────────────────────────────────────────────

class TestHandoffDataClassification:
    """CONFIDENTIAL / RESTRICTED values must never appear in diagnostics_summary."""

    def test_confidential_ip_not_in_diagnostics_summary(self, builder):
        diag = _make_diagnostics_result(include_confidential=True)
        # Verify the fixture actually has a CONFIDENTIAL field.
        confidential_names = {
            f.name for f in diag.fields
            if f.classification == DataClassification.CONFIDENTIAL
        }
        assert "ip_address" in confidential_names

        packet = builder.build(
            _make_event(),
            action="tier2",
            reason="no_kb_match",
            classification=_make_classification(),
            ticket_id="t-001",
            diagnostics_result=diag,
            first_response=None,
            follow_up_questions=[],
            sla_status=None,
            escalation_result=None,
            comm_decision=None,
        )
        assert "ip_address" not in packet.diagnostics_summary

    def test_restricted_field_not_in_diagnostics_summary(self, builder):
        restricted_field = DiagnosticField(
            name="secret_key",
            value="sk-abc123",
            classification=DataClassification.RESTRICTED,
        )
        diag = DiagnosticsResult(
            fields=[restricted_field],
            missing_required=[],
            follow_up_questions=[],
            is_complete=True,
        )
        packet = builder.build(
            _make_event(),
            action="tier2",
            reason="no_kb_match",
            classification=_make_classification(),
            ticket_id="t-001",
            diagnostics_result=diag,
            first_response=None,
            follow_up_questions=[],
            sla_status=None,
            escalation_result=None,
            comm_decision=None,
        )
        assert "secret_key" not in packet.diagnostics_summary

    def test_public_channel_field_in_diagnostics_summary(self, builder):
        diag = _make_diagnostics_result(include_confidential=False)
        packet = builder.build(
            _make_event(),
            action="tier2",
            reason="low_confidence",
            classification=_make_classification(category=Category.LOW_CONFIDENCE),
            ticket_id=None,
            diagnostics_result=diag,
            first_response=None,
            follow_up_questions=[],
            sla_status=None,
            escalation_result=None,
            comm_decision=None,
        )
        assert "channel" in packet.diagnostics_summary

    def test_internal_severity_field_in_diagnostics_summary(self, builder):
        diag = _make_diagnostics_result(include_confidential=False)
        packet = builder.build(
            _make_event(),
            action="tier2",
            reason="low_confidence",
            classification=_make_classification(category=Category.LOW_CONFIDENCE),
            ticket_id=None,
            diagnostics_result=diag,
            first_response=None,
            follow_up_questions=[],
            sla_status=None,
            escalation_result=None,
            comm_decision=None,
        )
        assert "severity" in packet.diagnostics_summary

    def test_confidential_value_not_in_any_top_level_field(self, builder):
        diag = _make_diagnostics_result(include_confidential=True)
        packet = builder.build(
            _make_event(),
            action="tier2",
            reason="no_kb_match",
            classification=_make_classification(),
            ticket_id="t-001",
            diagnostics_result=diag,
            first_response=None,
            follow_up_questions=[],
            sla_status=None,
            escalation_result=None,
            comm_decision=None,
        )
        # The value "10.0.0.42" must not appear anywhere in top-level string fields.
        top_level_text = " ".join([
            packet.customer_goal,
            packet.classification_reasoning,
            packet.suggested_next_action,
            packet.routing_reason,
            str(packet.diagnostics_summary),
        ])
        assert "10.0.0.42" not in top_level_text


# ── Suggested next action ──────────────────────────────────────────────────────

class TestSuggestedNextAction:
    def test_low_confidence_action_mentions_classify(self, builder):
        packet = builder.build(
            _make_event(subject="Something odd happened"),
            action="tier2",
            reason="low_confidence",
            classification=_make_classification(category=Category.LOW_CONFIDENCE),
            ticket_id=None,
            diagnostics_result=None,
            first_response=None,
            follow_up_questions=[],
            sla_status=None,
            escalation_result=None,
            comm_decision=None,
        )
        assert "low_confidence" == packet.handoff_reason
        assert packet.suggested_next_action  # non-empty
        assert "alice.chen" in packet.suggested_next_action

    def test_injection_flagged_action_mentions_injection(self, builder):
        packet = builder.build(
            _make_event(injection_flagged=True),
            action="tier2",
            reason="injection_flagged",
            classification=_make_classification(),
            ticket_id=None,
            diagnostics_result=None,
            first_response=None,
            follow_up_questions=[],
            sla_status=None,
            escalation_result=None,
            comm_decision=None,
        )
        action = packet.suggested_next_action.lower()
        assert "injection" in action or "prompt" in action

    def test_customer_requested_human_action_mentions_contact(self, builder):
        packet = builder.build(
            _make_event(contact_id="bob.smith"),
            action="tier2",
            reason="customer_requested_human",
            classification=_make_classification(),
            ticket_id=None,
            diagnostics_result=None,
            first_response=None,
            follow_up_questions=[],
            sla_status=None,
            escalation_result=None,
            comm_decision=None,
        )
        assert "bob.smith" in packet.suggested_next_action

    def test_no_kb_match_action_mentions_kb(self, builder):
        packet = builder.build(
            _make_event(),
            action="tier2",
            reason="no_kb_match",
            classification=_make_classification(component="network-service"),
            ticket_id="t-001",
            diagnostics_result=_make_diagnostics_result(),
            first_response=None,
            follow_up_questions=[],
            sla_status=None,
            escalation_result=None,
            comm_decision=None,
        )
        action_lower = packet.suggested_next_action.lower()
        assert "kb" in action_lower or "runbook" in action_lower or "knowledge" in action_lower

    def test_suggested_action_is_string(self, builder):
        for reason in ("low_confidence", "injection_flagged", "customer_requested_human", "no_kb_match"):
            packet = builder.build(
                _make_event(),
                action="tier2",
                reason=reason,
                classification=_make_classification(category=Category.LOW_CONFIDENCE),
                ticket_id=None,
                diagnostics_result=None,
                first_response=None,
                follow_up_questions=[],
                sla_status=None,
                escalation_result=None,
                comm_decision=None,
            )
            assert isinstance(packet.suggested_next_action, str)
            assert packet.suggested_next_action


# ── Handoff reason scenarios ──────────────────────────────────────────────────

class TestHandoffReasonScenarios:
    def test_low_confidence_packet(self, builder):
        packet = builder.build(
            _make_event(subject="xyz abc 123"),
            action="tier2",
            reason="low_confidence",
            classification=_make_classification(
                category=Category.LOW_CONFIDENCE,
                confidence=0.20,
            ),
            ticket_id=None,
            diagnostics_result=None,
            first_response=None,
            follow_up_questions=[],
            sla_status=None,
            escalation_result=None,
            comm_decision=None,
        )
        assert packet.handoff_reason == "low_confidence"
        assert packet.ticket_id is None
        assert "classification" in packet.attempted_steps

    def test_customer_requested_human_packet(self, builder):
        packet = builder.build(
            _make_event(subject="I need to speak to a human agent"),
            action="tier2",
            reason="customer_requested_human",
            classification=_make_classification(category=Category.INCIDENT),
            ticket_id=None,
            diagnostics_result=None,
            first_response=None,
            follow_up_questions=[],
            sla_status=None,
            escalation_result=None,
            comm_decision=None,
        )
        assert packet.handoff_reason == "customer_requested_human"
        assert packet.customer_goal == "I need to speak to a human agent"

    def test_no_kb_match_packet(self, builder):
        packet = builder.build(
            _make_event(subject="Storage upload failed"),
            action="tier2",
            reason="no_kb_match",
            classification=_make_classification(
                category=Category.INCIDENT,
                component="storage-service",
            ),
            ticket_id="ticket-no-kb",
            diagnostics_result=_make_diagnostics_result(),
            first_response=None,
            follow_up_questions=[],
            sla_status=None,
            escalation_result=None,
            comm_decision=None,
        )
        assert packet.handoff_reason == "no_kb_match"
        assert packet.ticket_id == "ticket-no-kb"
        assert packet.kb_no_match_reason is not None
        assert "diagnostics_collection" in packet.attempted_steps
        assert "kb_retrieval" in packet.attempted_steps

    def test_injection_flagged_packet(self, builder):
        packet = builder.build(
            _make_event(injection_flagged=True),
            action="tier2",
            reason="injection_flagged",
            classification=_make_classification(),
            ticket_id=None,
            diagnostics_result=None,
            first_response=None,
            follow_up_questions=[],
            sla_status=None,
            escalation_result=None,
            comm_decision=None,
        )
        assert packet.handoff_reason == "injection_flagged"
        assert packet.ticket_id is None

    def test_sla_fields_present_when_sla_status_given(self, builder):
        sla = _make_sla_status(state="BREACHED", response_breached=True)
        packet = builder.build(
            _make_event(),
            action="tier2",
            reason="no_kb_match",
            classification=_make_classification(),
            ticket_id="t-sla",
            diagnostics_result=_make_diagnostics_result(),
            first_response=None,
            follow_up_questions=[],
            sla_status=sla,
            escalation_result=None,
            comm_decision=None,
        )
        assert packet.sla_state == "BREACHED"
        assert packet.sla_response_breached is True
        assert packet.sla_response_deadline is not None
        assert packet.sla_resolution_deadline is not None
        assert "sla_initialized" in packet.attempted_steps

    def test_sla_fields_none_when_no_sla_status(self, builder):
        packet = builder.build(
            _make_event(),
            action="tier2",
            reason="low_confidence",
            classification=_make_classification(category=Category.LOW_CONFIDENCE),
            ticket_id=None,
            diagnostics_result=None,
            first_response=None,
            follow_up_questions=[],
            sla_status=None,
            escalation_result=None,
            comm_decision=None,
        )
        assert packet.sla_state is None
        assert packet.sla_response_deadline is None
        assert packet.sla_response_breached is None


# ── Attempted steps ───────────────────────────────────────────────────────────

class TestAttemptedSteps:
    def test_early_tier2_has_only_classification(self, builder):
        # low_confidence: no diagnostics, no KB, no SLA
        packet = builder.build(
            _make_event(),
            action="tier2",
            reason="low_confidence",
            classification=_make_classification(category=Category.LOW_CONFIDENCE),
            ticket_id=None,
            diagnostics_result=None,
            first_response=None,
            follow_up_questions=[],
            sla_status=None,
            escalation_result=None,
            comm_decision=None,
        )
        assert packet.attempted_steps == ["classification"]

    def test_no_kb_match_has_diagnostics_and_kb_steps(self, builder):
        packet = builder.build(
            _make_event(),
            action="tier2",
            reason="no_kb_match",
            classification=_make_classification(),
            ticket_id="t-001",
            diagnostics_result=_make_diagnostics_result(),
            first_response=None,
            follow_up_questions=[],
            sla_status=_make_sla_status(),
            escalation_result=None,
            comm_decision=None,
        )
        assert "classification" in packet.attempted_steps
        assert "diagnostics_collection" in packet.attempted_steps
        assert "kb_retrieval" in packet.attempted_steps
        assert "sla_initialized" in packet.attempted_steps
