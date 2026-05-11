"""Tests for EscalationEngine (app/agents/escalation_engine.py).

All escalations are simulated — no real notifications are sent.
"""

import pytest

from app.agents.escalation_engine import EscalationAction, EscalationEngine, EscalationResult
from app.config.loader import load_config
from app.db.repositories.audit_repository import AuditRepository
from app.utils.clock import FakeClock


# ── Shared fixtures ───────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def config():
    return load_config()


def _make_engine(db_session, config, clock=None):
    return EscalationEngine(
        config=config,
        clock=clock or FakeClock(),
        audit_repo=AuditRepository(db_session),
    )


# ── Chain selection ───────────────────────────────────────────────────────────

class TestEscalationChainSelection:
    def test_component_specific_chain_preferred_over_wildcard(self, db_session, config):
        """acme-corp P1 auth-service has a dedicated chain (Identity Team Lead first)."""
        engine = _make_engine(db_session, config)
        result = engine.escalate(
            ticket_id="esc-t-001",
            tenant_id="acme-corp",
            severity="P1",
            component="auth-service",
            reason="sla_breached",
        )
        assert result.chain_found
        assert result.component_specific
        assert result.actions[0].contact_name == "ACME Identity Team Lead"

    def test_wildcard_chain_used_when_no_specific_match(self, db_session, config):
        """acme-corp P1 network-service → no specific chain → wildcard P1 applies."""
        engine = _make_engine(db_session, config)
        result = engine.escalate(
            ticket_id="esc-t-002",
            tenant_id="acme-corp",
            severity="P1",
            component="network-service",
            reason="sla_breached",
        )
        assert result.chain_found
        assert not result.component_specific

    def test_no_chain_found_for_missing_config(self, db_session, config):
        """No chain is configured for acme-corp / P3 / storage-service (only wildcard)."""
        engine = _make_engine(db_session, config)
        # Use a tenant that exists but try a nonexistent tenant_id to test missing chain.
        result = engine.escalate(
            ticket_id="esc-t-003",
            tenant_id="unknown-tenant",
            severity="P1",
            component="network-service",
            reason="sla_breached",
        )
        assert not result.chain_found
        assert result.actions == []

    def test_vertex_tenant_uses_vertex_chain(self, db_session, config):
        engine = _make_engine(db_session, config)
        result = engine.escalate(
            ticket_id="esc-t-004",
            tenant_id="vertex-systems",
            severity="P1",
            component="network-service",
            reason="sla_breached",
        )
        assert result.chain_found
        assert result.actions[0].contact_name == "Vertex Primary On-Call"

    def test_different_tenants_have_different_contacts(self, db_session, config):
        engine = _make_engine(db_session, config)
        acme_result = engine.escalate(
            ticket_id="esc-t-005a",
            tenant_id="acme-corp",
            severity="P1",
            component="network-service",
            reason="sla_breached",
        )
        vertex_result = engine.escalate(
            ticket_id="esc-t-005b",
            tenant_id="vertex-systems",
            severity="P1",
            component="network-service",
            reason="sla_breached",
        )
        acme_names = {a.contact_name for a in acme_result.actions}
        vertex_names = {a.contact_name for a in vertex_result.actions}
        assert acme_names != vertex_names

    def test_p3_wildcard_chain_found(self, db_session, config):
        engine = _make_engine(db_session, config)
        result = engine.escalate(
            ticket_id="esc-t-006",
            tenant_id="acme-corp",
            severity="P3",
            component="api-gateway",
            reason="sla_breached",
        )
        assert result.chain_found


# ── Simulated actions ─────────────────────────────────────────────────────────

class TestSimulatedActions:
    def test_all_actions_are_simulated(self, db_session, config):
        engine = _make_engine(db_session, config)
        result = engine.escalate(
            ticket_id="esc-t-007",
            tenant_id="acme-corp",
            severity="P1",
            component="network-service",
            reason="sla_breached",
        )
        for action in result.actions:
            assert action.simulated is True

    def test_actions_fired_in_configured_order(self, db_session, config):
        engine = _make_engine(db_session, config)
        result = engine.escalate(
            ticket_id="esc-t-008",
            tenant_id="acme-corp",
            severity="P2",
            component="network-service",
            reason="sla_breached",
        )
        steps = [a.step for a in result.actions]
        assert steps == sorted(steps)

    def test_delay_minutes_match_config(self, db_session, config):
        """P2 acme-corp wildcard: first contact at 0 min, second at 30 min."""
        engine = _make_engine(db_session, config)
        result = engine.escalate(
            ticket_id="esc-t-009",
            tenant_id="acme-corp",
            severity="P2",
            component="network-service",
            reason="sla_breached",
        )
        delays = [a.delay_minutes for a in result.actions]
        assert delays[0] == 0
        assert delays[1] == 30

    def test_would_fire_at_is_triggered_at_plus_delay(self, db_session, config):
        clock = FakeClock()
        engine = _make_engine(db_session, config, clock=clock)
        t0 = clock.now()
        result = engine.escalate(
            ticket_id="esc-t-010",
            tenant_id="acme-corp",
            severity="P2",
            component="network-service",
            reason="sla_breached",
        )
        from datetime import timedelta
        for action in result.actions:
            expected = t0 + timedelta(minutes=action.delay_minutes)
            assert action.would_fire_at == expected

    def test_reason_propagated_to_actions(self, db_session, config):
        engine = _make_engine(db_session, config)
        result = engine.escalate(
            ticket_id="esc-t-011",
            tenant_id="acme-corp",
            severity="P1",
            component="network-service",
            reason="response_sla_breached",
        )
        for action in result.actions:
            assert action.reason == "response_sla_breached"

    def test_action_has_contact_method_and_address(self, db_session, config):
        engine = _make_engine(db_session, config)
        result = engine.escalate(
            ticket_id="esc-t-012",
            tenant_id="acme-corp",
            severity="P1",
            component="network-service",
            reason="sla_breached",
        )
        for action in result.actions:
            assert action.contact_method in {"slack", "email", "pagerduty", "phone"}
            assert action.contact_address


# ── Audit event recording ──────────────────────────────────────────────────────

class TestEscalationAudit:
    def test_escalation_audit_event_recorded(self, db_session, config):
        audit_repo = AuditRepository(db_session)
        engine = EscalationEngine(
            config=config, clock=FakeClock(), audit_repo=audit_repo
        )
        engine.escalate(
            ticket_id="esc-t-013",
            tenant_id="acme-corp",
            severity="P1",
            component="network-service",
            reason="sla_breached",
        )
        events = audit_repo.list_by_tenant(tenant_id="acme-corp")
        types = [e.event_type for e in events]
        assert "escalation_triggered" in types

    def test_audit_event_payload_contains_ticket_id(self, db_session, config):
        import json
        audit_repo = AuditRepository(db_session)
        engine = EscalationEngine(
            config=config, clock=FakeClock(), audit_repo=audit_repo
        )
        engine.escalate(
            ticket_id="esc-t-audit-001",
            tenant_id="acme-corp",
            severity="P2",
            component="network-service",
            reason="sla_breached",
        )
        events = audit_repo.list_by_tenant(tenant_id="acme-corp")
        esc_events = [e for e in events if e.event_type == "escalation_triggered"]
        assert esc_events
        payload = json.loads(esc_events[-1].payload_json)
        assert payload["ticket_id"] == "esc-t-audit-001"
        assert payload["simulated"] is True

    def test_no_chain_still_records_audit(self, db_session, config):
        audit_repo = AuditRepository(db_session)
        engine = EscalationEngine(
            config=config, clock=FakeClock(), audit_repo=audit_repo
        )
        result = engine.escalate(
            ticket_id="esc-t-014",
            tenant_id="unknown-tenant",
            severity="P1",
            component="network-service",
            reason="sla_breached",
        )
        assert not result.chain_found
        events = audit_repo.list_by_tenant(tenant_id="unknown-tenant")
        assert any(e.event_type == "escalation_triggered" for e in events)
