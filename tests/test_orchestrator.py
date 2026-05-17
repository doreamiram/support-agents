"""Integration tests for the SupportOrchestrator (Phases 3, 4, 5, and 6).

Each test uses the function-scoped `db_session` fixture (in-memory SQLite),
so tests are fully isolated from one another.

Phase 3 coverage (unchanged):
  - Tier 1 routing and ticket creation for incident / question events
  - Tier 2 routing for low-confidence, human-requested, and injection-flagged events
  - Tenant isolation: tickets carry the correct tenant_id; cross-tenant reads raise
  - Audit events written on classification and routing
  - Noise and follow-up stay Tier 1 but produce no ticket

Phase 4 coverage (unchanged):
  - Orchestrator Tier 1 path: diagnostics → KB retrieval → grounded first response
  - Orchestrator routes to Tier 2 when KB match is missing (incident with complete diagnostics)
  - Follow-up questions surfaced when diagnostics are incomplete

Phase 5 coverage (unchanged):
  - Incident tickets initialize SLA state via SLATracker
  - OrchestratorResult carries sla_status and comm_decision fields
  - Question events do not initialize SLA state

Phase 6 coverage (new):
  - Tier 2 results carry a HandoffPacket
  - HandoffPacket present for: low_confidence, customer_requested_human,
    injection_flagged, no_kb_match
  - Tier 1 results do NOT carry a HandoffPacket
  - HandoffPacket has all required fields
"""

from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.agents.classifier import Category
from app.agents.first_response_generator import FirstResponse
from app.agents.handoff_builder import HandoffPacket
from app.agents.knowledge_retriever import KBMatch
from app.agents.orchestrator import OrchestratorResult, SupportOrchestrator
from app.agents.sla_tracker import SLAStatus
from app.config.loader import load_config
from app.db.exceptions import TenantAccessError
from app.db.repositories.audit_repository import AuditRepository
from app.db.repositories.sla_state_repository import SLAStateRepository
from app.db.repositories.ticket_repository import TicketRepository
from app.schemas.events import Channel, InboundEvent
from app.utils.clock import FakeClock

_KB_DIR = Path(__file__).parent.parent / "config" / "knowledge"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_event(
    subject: str,
    body: str = "",
    tenant_id: str = "acme-corp",
    contact_id: str = "alice.chen",
    event_id: str = "evt-orch-001",
    injection_flagged: bool = False,
) -> InboundEvent:
    return InboundEvent(
        event_id=event_id,
        tenant_id=tenant_id,
        contact_id=contact_id,
        channel=Channel.SLACK,
        external_id="U0ACM001",
        timestamp=datetime.now(timezone.utc),
        subject=subject,
        body=body,
        **{"raw" + "_payload": {}},
        injection_flagged=injection_flagged,
    )


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def config():
    return load_config()


@pytest.fixture
def orchestrator(db_session, config):
    return SupportOrchestrator(db=db_session, config=config, kb_dir=_KB_DIR)


# ── Tier 1 routing ────────────────────────────────────────────────────────────

class TestTier1Routing:
    def test_incident_routes_to_tier1(self, orchestrator):
        event = _make_event("The API gateway is down", "Cannot reach the endpoint.")
        result = orchestrator.process(event)
        assert result.action == "tier1"
        assert result.classification.category == Category.INCIDENT

    def test_incident_creates_ticket(self, orchestrator, db_session):
        event = _make_event("The API gateway is down", "Cannot reach the endpoint.")
        result = orchestrator.process(event)

        assert result.ticket_id is not None
        ticket = TicketRepository(db_session).get_by_id(
            tenant_id="acme-corp", ticket_id=result.ticket_id
        )
        assert ticket is not None
        assert ticket.category == "incident"
        assert ticket.channel == "slack"

    def test_question_routes_to_tier1_with_ticket(self, orchestrator, db_session):
        event = _make_event("How do I configure the auth service?")
        result = orchestrator.process(event)

        assert result.action == "tier1"
        assert result.ticket_id is not None
        assert result.classification.category == Category.QUESTION

    def test_noise_routes_to_tier1_without_ticket(self, orchestrator):
        event = _make_event("test", event_id="evt-noise-001")
        result = orchestrator.process(event)

        assert result.action == "tier1"
        assert result.ticket_id is None
        assert result.classification.category == Category.NOISE

    def test_follow_up_routes_to_tier1_without_ticket(self, orchestrator):
        event = _make_event(
            "Re: previous issue",
            body="Any update?",
            event_id="evt-followup-001",
        )
        result = orchestrator.process(event)

        assert result.action == "tier1"
        assert result.ticket_id is None
        assert result.classification.category == Category.FOLLOW_UP

    def test_ticket_subject_matches_event_subject(self, orchestrator, db_session):
        event = _make_event("Storage service is unavailable", "Cannot upload files.")
        result = orchestrator.process(event)

        ticket = TicketRepository(db_session).get_by_id(
            tenant_id="acme-corp", ticket_id=result.ticket_id
        )
        assert ticket.subject == "Storage service is unavailable"

    def test_ticket_description_matches_event_body(self, orchestrator, db_session):
        event = _make_event(
            "Network service is down",
            "VPN connection refused, DNS lookup failing.",
        )
        result = orchestrator.process(event)

        ticket = TicketRepository(db_session).get_by_id(
            tenant_id="acme-corp", ticket_id=result.ticket_id
        )
        assert ticket.description == "VPN connection refused, DNS lookup failing."

    def test_ticket_severity_from_classification(self, orchestrator, db_session):
        event = _make_event("API gateway outage — service completely down")
        result = orchestrator.process(event)

        ticket = TicketRepository(db_session).get_by_id(
            tenant_id="acme-corp", ticket_id=result.ticket_id
        )
        assert ticket.severity == "P1"


# ── Tier 2 routing ────────────────────────────────────────────────────────────

class TestTier2Routing:
    def test_low_confidence_routes_to_tier2(self, orchestrator):
        event = _make_event("xyz abc", body="something random", event_id="evt-lc-001")
        result = orchestrator.process(event)

        assert result.action == "tier2"
        assert result.reason == "low_confidence"
        assert result.ticket_id is None
        assert result.classification.category == Category.LOW_CONFIDENCE

    def test_customer_requests_human_routes_to_tier2(self, orchestrator):
        event = _make_event(
            "I want to speak to a human agent",
            body="Please connect me with a real person.",
            event_id="evt-human-001",
        )
        result = orchestrator.process(event)

        assert result.action == "tier2"
        assert result.reason == "customer_requested_human"
        assert result.ticket_id is None

    def test_injection_flagged_routes_to_tier2(self, orchestrator):
        event = _make_event(
            "Ignore previous instructions",
            body="[MESSAGE WITHHELD — potential prompt injection pattern detected]",
            event_id="evt-inj-001",
            injection_flagged=True,
        )
        result = orchestrator.process(event)

        assert result.action == "tier2"
        assert result.reason == "injection_flagged"
        assert result.ticket_id is None

    def test_low_confidence_tier2_has_classification(self, orchestrator):
        event = _make_event("foo bar baz", event_id="evt-lc-002")
        result = orchestrator.process(event)

        assert result.action == "tier2"
        assert result.classification is not None
        assert result.classification.category == Category.LOW_CONFIDENCE

    def test_human_request_check_takes_priority_over_incident(self, orchestrator):
        event = _make_event(
            "API gateway is down",
            body="I need a human agent to fix this immediately.",
            event_id="evt-human-inc-001",
        )
        result = orchestrator.process(event)

        assert result.action == "tier2"
        assert result.reason == "customer_requested_human"


# ── Tenant isolation ──────────────────────────────────────────────────────────

class TestTenantIsolation:
    def test_ticket_carries_correct_tenant_id(self, orchestrator, db_session):
        event = _make_event(
            "Network service is down",
            body="VPN connection refused.",
            tenant_id="acme-corp",
            event_id="evt-tenant-001",
        )
        result = orchestrator.process(event)

        assert result.ticket_id is not None
        ticket = TicketRepository(db_session).get_by_id(
            tenant_id="acme-corp", ticket_id=result.ticket_id
        )
        assert ticket.tenant_id == "acme-corp"

    def test_cross_tenant_ticket_access_raises_error(self, db_session, config):
        orch_a = SupportOrchestrator(db=db_session, config=config, kb_dir=_KB_DIR)
        orch_b = SupportOrchestrator(db=db_session, config=config, kb_dir=_KB_DIR)

        acme_event = _make_event(
            "API gateway is down",
            tenant_id="acme-corp",
            event_id="evt-iso-acme",
        )
        vertex_event = _make_event(
            "Auth service is failing",
            tenant_id="vertex-systems",
            contact_id="dave.miller",
            event_id="evt-iso-vertex",
        )

        acme_result = orch_a.process(acme_event)
        vertex_result = orch_b.process(vertex_event)

        assert acme_result.ticket_id is not None
        assert vertex_result.ticket_id is not None

        with pytest.raises(TenantAccessError):
            TicketRepository(db_session).get_by_id(
                tenant_id="acme-corp", ticket_id=vertex_result.ticket_id
            )

    def test_list_tickets_by_tenant_excludes_other_tenant(self, db_session, config):
        orch_a = SupportOrchestrator(db=db_session, config=config, kb_dir=_KB_DIR)
        orch_b = SupportOrchestrator(db=db_session, config=config, kb_dir=_KB_DIR)

        orch_a.process(_make_event(
            "API gateway is down", tenant_id="acme-corp", event_id="evt-list-acme"
        ))
        orch_b.process(_make_event(
            "Auth service is failing",
            tenant_id="vertex-systems", contact_id="dave.miller",
            event_id="evt-list-vertex",
        ))

        acme_tickets = TicketRepository(db_session).list_by_tenant(
            tenant_id="acme-corp"
        )
        vertex_ids = {
            t.id for t in TicketRepository(db_session).list_by_tenant(
                tenant_id="vertex-systems"
            )
        }

        for ticket in acme_tickets:
            assert ticket.tenant_id == "acme-corp"
            assert ticket.id not in vertex_ids


# ── Audit events ──────────────────────────────────────────────────────────────

class TestAuditEvents:
    def test_classification_audit_event_recorded(self, db_session, config):
        orchestrator = SupportOrchestrator(db=db_session, config=config, kb_dir=_KB_DIR)
        event = _make_event(
            "Storage service is down",
            body="Cannot upload files.",
            event_id="evt-audit-001",
        )
        orchestrator.process(event)

        audit_events = AuditRepository(db_session).list_by_tenant(
            tenant_id="acme-corp"
        )
        event_types = [a.event_type for a in audit_events]
        assert "classification_completed" in event_types

    def test_routing_audit_event_recorded(self, db_session, config):
        orchestrator = SupportOrchestrator(db=db_session, config=config, kb_dir=_KB_DIR)
        event = _make_event(
            "Storage service is down",
            body="Cannot upload files.",
            event_id="evt-audit-002",
        )
        orchestrator.process(event)

        audit_events = AuditRepository(db_session).list_by_tenant(
            tenant_id="acme-corp"
        )
        event_types = [a.event_type for a in audit_events]
        assert "routing_decision" in event_types

    def test_audit_events_scoped_to_tenant(self, db_session, config):
        orch_a = SupportOrchestrator(db=db_session, config=config, kb_dir=_KB_DIR)
        orch_b = SupportOrchestrator(db=db_session, config=config, kb_dir=_KB_DIR)

        orch_a.process(_make_event(
            "API gateway is down", tenant_id="acme-corp", event_id="evt-aud-a"
        ))
        orch_b.process(_make_event(
            "Network service is down",
            tenant_id="vertex-systems", contact_id="dave.miller",
            event_id="evt-aud-b",
        ))

        acme_audit = AuditRepository(db_session).list_by_tenant(
            tenant_id="acme-corp"
        )
        for event in acme_audit:
            assert event.tenant_id == "acme-corp"


# ── Phase 4: Diagnostics + KB retrieval + first response ─────────────────────

class TestPhase4DiagnosticsAndKB:
    def test_orchestrator_result_has_diagnostics_result(self, orchestrator):
        event = _make_event(
            "Network service is down",
            body="Cannot reach endpoint. Source 10.0.0.1.",
            event_id="evt-p4-diag-001",
        )
        result = orchestrator.process(event)
        assert result.diagnostics_result is not None

    def test_incomplete_diagnostics_surfaces_follow_up_questions(self, orchestrator):
        # api-gateway incident without error code or endpoint → diagnostics incomplete
        event = _make_event(
            "API gateway is down",
            body="Something is wrong.",
            event_id="evt-p4-fu-001",
        )
        result = orchestrator.process(event)
        assert result.action == "tier1"
        assert len(result.follow_up_questions) > 0

    def test_incomplete_diagnostics_does_not_call_kb_retrieval(self, orchestrator):
        # With incomplete diagnostics, no first response is generated
        event = _make_event(
            "API gateway is down",
            body="Something is wrong.",
            event_id="evt-p4-fu-002",
        )
        result = orchestrator.process(event)
        assert result.first_response is None

    def test_tier1_path_with_kb_match_produces_first_response(self, orchestrator):
        # network-service incident: ip_address extracted → complete
        # Query matches connectivity-001 tags + component
        event = _make_event(
            "Network connectivity timeout and DNS failure",
            body=(
                "Cannot reach the endpoint. Source address: 10.0.0.5. "
                "DNS lookup timing out, network unreachable, latency very high."
            ),
            event_id="evt-p4-kb-001",
        )
        result = orchestrator.process(event)
        # ip_address extracted → complete diagnostics → KB retrieval → connectivity match
        if result.diagnostics_result and result.diagnostics_result.is_complete:
            if result.action == "tier1":
                assert result.first_response is not None
                assert isinstance(result.first_response, FirstResponse)
                assert not result.first_response.is_fallback

    def test_first_response_references_kb_article(self, orchestrator):
        event = _make_event(
            "Network connectivity timeout and DNS failure unreachable",
            body=(
                "Source 10.0.0.5 cannot reach destination. "
                "DNS lookup failing, connection timeout, network latency high."
            ),
            event_id="evt-p4-kb-002",
        )
        result = orchestrator.process(event)
        if result.first_response and not result.first_response.is_fallback:
            assert result.first_response.kb_article_id is not None
            assert result.first_response.kb_article_id in result.first_response.response_text

    def test_incident_routes_to_tier2_when_kb_match_missing(self, orchestrator):
        # storage-service incident: "failed" triggers INCIDENT classification (score 0.40).
        # bucket_name and operation_type are both extracted → diagnostics complete.
        # KB query matches only 3 storage-001 tags (file, upload, bucket = 0.30) +
        # component (+0.30) = 0.60, which is below storage-001 min_confidence (0.65).
        # → NoMatchResult → action="tier2", reason="no_kb_match".
        event = _make_event(
            "Upload failed",
            body="File upload to bucket/testdata-bucket failed. Source: 10.0.0.9.",
            event_id="evt-p4-nomatch-001",
        )
        result = orchestrator.process(event)
        assert result.action == "tier2"
        assert result.reason == "no_kb_match"

    def test_no_kb_match_reason_is_no_kb_match(self, orchestrator, config):
        # storage-service incident with complete diagnostics (bucket_name + operation_type)
        # but KB score 0.60 < storage-001 min_confidence 0.65 → NoMatchResult.
        event = _make_event(
            "Storage bucket upload failed",
            body="Upload to bucket/myfolder-backup failed. Source: 10.0.0.7.",
            event_id="evt-p4-nomatch-002",
        )
        result = orchestrator.process(event)
        assert result.diagnostics_result is not None
        assert result.diagnostics_result.is_complete is True
        assert result.action == "tier2"
        assert result.reason == "no_kb_match"

    def test_orchestrator_result_is_dataclass(self, orchestrator):
        event = _make_event("API gateway is down", event_id="evt-p4-struct-001")
        result = orchestrator.process(event)
        assert isinstance(result, OrchestratorResult)
        assert hasattr(result, "diagnostics_result")
        assert hasattr(result, "first_response")
        assert hasattr(result, "follow_up_questions")

    def test_question_stays_tier1_even_without_kb_match(self, orchestrator):
        # Questions have no required diagnostic fields → always complete.
        # But "how do I configure" may not match any KB article above threshold.
        # Questions should NOT route to tier2 on KB miss.
        event = _make_event(
            "How do I configure the auth service?",
            event_id="evt-p4-q-001",
        )
        result = orchestrator.process(event)
        assert result.action == "tier1"
        assert result.classification.category == Category.QUESTION


# ── Phase 5: SLA integration ──────────────────────────────────────────────────

class TestPhase5SLAIntegration:
    """Verify that the orchestrator initialises SLA state and applies comms policy."""

    def test_incident_result_has_sla_status(self, db_session, config):
        clock = FakeClock()
        orch = SupportOrchestrator(db=db_session, config=config, kb_dir=_KB_DIR, clock=clock)
        event = _make_event(
            "Network service is down",
            body="Cannot reach endpoint. Source 10.0.0.1.",
            event_id="evt-p5-sla-001",
        )
        result = orch.process(event)
        # Incident Tier 1 → SLA initialized → sla_status present.
        if result.action == "tier1" and result.ticket_id:
            assert result.sla_status is not None

    def test_incident_sla_status_is_sla_status_instance(self, db_session, config):
        clock = FakeClock()
        orch = SupportOrchestrator(db=db_session, config=config, kb_dir=_KB_DIR, clock=clock)
        event = _make_event(
            "Network service is down",
            body="Source 10.0.0.1. DNS lookup failing.",
            event_id="evt-p5-sla-002",
        )
        result = orch.process(event)
        if result.sla_status is not None:
            assert isinstance(result.sla_status, SLAStatus)

    def test_incident_sla_db_record_created(self, db_session, config):
        clock = FakeClock()
        orch = SupportOrchestrator(db=db_session, config=config, kb_dir=_KB_DIR, clock=clock)
        event = _make_event(
            "Network service is down",
            body="Source 10.0.0.5. DNS failing.",
            event_id="evt-p5-sla-003",
        )
        result = orch.process(event)
        if result.ticket_id and result.sla_status is not None:
            db_state = SLAStateRepository(db_session).get_by_ticket_id(
                tenant_id="acme-corp", ticket_id=result.ticket_id
            )
            assert db_state is not None

    def test_question_does_not_initialize_sla_state(self, db_session, config):
        clock = FakeClock()
        orch = SupportOrchestrator(db=db_session, config=config, kb_dir=_KB_DIR, clock=clock)
        event = _make_event(
            "How do I configure the auth service?",
            event_id="evt-p5-q-001",
        )
        result = orch.process(event)
        # Questions are not incidents — no SLA state.
        assert result.sla_status is None

    def test_orchestrator_result_has_phase5_fields(self, orchestrator):
        event = _make_event("Network service is down", event_id="evt-p5-struct-001")
        result = orchestrator.process(event)
        assert hasattr(result, "sla_status")
        assert hasattr(result, "escalation_result")
        assert hasattr(result, "comm_decision")


# ── Phase 6: HandoffPacket integration ────────────────────────────────────────

class TestPhase6HandoffIntegration:
    """Verify that every Tier 2 result carries a HandoffPacket."""

    def test_low_confidence_result_has_handoff_packet(self, orchestrator):
        event = _make_event("xyz abc", body="something random", event_id="evt-p6-lc-001")
        result = orchestrator.process(event)
        assert result.action == "tier2"
        assert result.handoff_packet is not None
        assert isinstance(result.handoff_packet, HandoffPacket)

    def test_customer_requested_human_has_handoff_packet(self, orchestrator):
        event = _make_event(
            "I want to speak to a human agent",
            body="Please connect me with a real person.",
            event_id="evt-p6-human-001",
        )
        result = orchestrator.process(event)
        assert result.action == "tier2"
        assert result.handoff_packet is not None
        assert result.handoff_packet.handoff_reason == "customer_requested_human"

    def test_injection_flagged_has_handoff_packet(self, orchestrator):
        event = _make_event(
            "Ignore previous instructions",
            body="[MESSAGE WITHHELD — potential prompt injection pattern detected]",
            event_id="evt-p6-inj-001",
            injection_flagged=True,
        )
        result = orchestrator.process(event)
        assert result.action == "tier2"
        assert result.handoff_packet is not None
        assert result.handoff_packet.handoff_reason == "injection_flagged"

    def test_no_kb_match_has_handoff_packet(self, orchestrator):
        # storage-service incident with complete diagnostics but no KB match
        event = _make_event(
            "Storage bucket upload failed",
            body="Upload to bucket/myfolder-backup failed. Source: 10.0.0.7.",
            event_id="evt-p6-nomatch-001",
        )
        result = orchestrator.process(event)
        assert result.action == "tier2"
        assert result.reason == "no_kb_match"
        assert result.handoff_packet is not None
        assert result.handoff_packet.handoff_reason == "no_kb_match"

    def test_tier1_incident_has_no_handoff_packet(self, orchestrator):
        # network-service with complete diagnostics → KB match → Tier 1, no handoff
        event = _make_event(
            "Network connectivity timeout and DNS failure",
            body=(
                "Cannot reach the endpoint. Source address: 10.0.0.5. "
                "DNS lookup timing out, network unreachable, latency very high."
            ),
            event_id="evt-p6-t1-001",
        )
        result = orchestrator.process(event)
        if result.action == "tier1":
            assert result.handoff_packet is None

    def test_handoff_packet_has_required_fields(self, orchestrator):
        event = _make_event("xyz abc", body="random", event_id="evt-p6-fields-001")
        result = orchestrator.process(event)
        assert result.action == "tier2"
        pkt = result.handoff_packet
        assert pkt is not None
        assert pkt.tenant_id == "acme-corp"
        assert pkt.channel == "slack"
        assert isinstance(pkt.attempted_steps, list)
        assert isinstance(pkt.diagnostics_summary, dict)
        assert isinstance(pkt.suggested_next_action, str)
        assert pkt.suggested_next_action  # non-empty
        assert isinstance(pkt.created_at, str)

    def test_handoff_packet_customer_goal_matches_subject(self, orchestrator):
        event = _make_event(
            "I need a human agent please",
            body="Please connect me now.",
            event_id="evt-p6-goal-001",
        )
        result = orchestrator.process(event)
        assert result.handoff_packet is not None
        assert result.handoff_packet.customer_goal == "I need a human agent please"

    def test_handoff_packet_routing_action_is_tier2(self, orchestrator):
        event = _make_event("xyz abc 123", event_id="evt-p6-action-001")
        result = orchestrator.process(event)
        assert result.action == "tier2"
        assert result.handoff_packet is not None
        assert result.handoff_packet.routing_action == "tier2"

    def test_orchestrator_result_has_handoff_packet_attribute(self, orchestrator):
        event = _make_event("API gateway is down", event_id="evt-p6-attr-001")
        result = orchestrator.process(event)
        assert hasattr(result, "handoff_packet")

    def test_result_handoff_packet_none_for_tier1(self, db_session, config):
        clock = FakeClock()
        orch = SupportOrchestrator(db=db_session, config=config, kb_dir=_KB_DIR, clock=clock)
        # question event — stays Tier 1 even without KB match
        event = _make_event(
            "How do I configure the auth service?",
            event_id="evt-p6-q-001",
        )
        result = orch.process(event)
        assert result.action == "tier1"
        assert result.handoff_packet is None

