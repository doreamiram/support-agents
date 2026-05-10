"""
Tenant isolation tests.

Every test in this file proves that one tenant cannot read or affect
another tenant's data through any repository method.
"""

import pytest

from app.db.exceptions import TenantAccessError
from app.db.repositories.audit_repository import AuditRepository
from app.db.repositories.contact_repository import ContactRepository
from app.db.repositories.diagnostic_repository import DiagnosticRepository
from app.db.repositories.sla_state_repository import SLAStateRepository
from app.db.repositories.ticket_repository import TicketRepository

TENANT_A = "acme-corp"
TENANT_B = "vertex-systems"


# ── Ticket isolation ──────────────────────────────────────────────────────────

class TestTicketIsolation:
    def test_tenant_a_can_read_own_ticket(self, db_session):
        repo = TicketRepository(db_session)
        ticket = repo.create(tenant_id=TENANT_A, channel="slack", severity="P2")
        result = repo.get_by_id(tenant_id=TENANT_A, ticket_id=ticket.id)
        assert result is not None
        assert result.id == ticket.id

    def test_tenant_b_cannot_read_tenant_a_ticket(self, db_session):
        repo = TicketRepository(db_session)
        ticket = repo.create(tenant_id=TENANT_A, channel="slack", severity="P2")
        with pytest.raises(TenantAccessError):
            repo.get_by_id(tenant_id=TENANT_B, ticket_id=ticket.id)

    def test_tenant_b_list_excludes_tenant_a_tickets(self, db_session):
        repo = TicketRepository(db_session)
        repo.create(tenant_id=TENANT_A, channel="slack", severity="P2")
        repo.create(tenant_id=TENANT_A, channel="jira", severity="P1")
        assert repo.list_by_tenant(tenant_id=TENANT_B) == []

    def test_each_tenant_sees_only_own_tickets(self, db_session):
        repo = TicketRepository(db_session)
        repo.create(tenant_id=TENANT_A, channel="slack", severity="P2")
        repo.create(tenant_id=TENANT_B, channel="jira", severity="P3")

        a_tickets = repo.list_by_tenant(tenant_id=TENANT_A)
        b_tickets = repo.list_by_tenant(tenant_id=TENANT_B)

        assert len(a_tickets) == 1 and a_tickets[0].tenant_id == TENANT_A
        assert len(b_tickets) == 1 and b_tickets[0].tenant_id == TENANT_B

    def test_nonexistent_ticket_returns_none(self, db_session):
        repo = TicketRepository(db_session)
        result = repo.get_by_id(tenant_id=TENANT_A, ticket_id="does-not-exist")
        assert result is None

    def test_tenant_b_cannot_update_tenant_a_ticket_status(self, db_session):
        repo = TicketRepository(db_session)
        ticket = repo.create(tenant_id=TENANT_A, channel="slack", severity="P1")
        with pytest.raises(TenantAccessError):
            repo.update_status(tenant_id=TENANT_B, ticket_id=ticket.id, status="RESOLVED")


# ── Diagnostic isolation ──────────────────────────────────────────────────────

class TestDiagnosticIsolation:
    def test_tenant_b_cannot_read_tenant_a_diagnostic(self, db_session):
        ticket_repo = TicketRepository(db_session)
        diag_repo = DiagnosticRepository(db_session)

        ticket = ticket_repo.create(tenant_id=TENANT_A, channel="slack", severity="P2")
        diag = diag_repo.create(
            tenant_id=TENANT_A,
            ticket_id=ticket.id,
            field_name="error_code",
            field_value="500",
        )

        with pytest.raises(TenantAccessError):
            diag_repo.get_by_id(tenant_id=TENANT_B, diagnostic_id=diag.id)

    def test_list_by_ticket_filters_by_tenant(self, db_session):
        ticket_repo = TicketRepository(db_session)
        diag_repo = DiagnosticRepository(db_session)

        ticket_a = ticket_repo.create(tenant_id=TENANT_A, channel="slack", severity="P2")
        diag_repo.create(
            tenant_id=TENANT_A,
            ticket_id=ticket_a.id,
            field_name="region",
            field_value="us-east-1",
        )

        # Tenant B queries using Tenant A's ticket_id — must return nothing
        result = diag_repo.list_by_ticket(tenant_id=TENANT_B, ticket_id=ticket_a.id)
        assert result == []

    def test_tenant_a_can_list_own_diagnostics(self, db_session):
        ticket_repo = TicketRepository(db_session)
        diag_repo = DiagnosticRepository(db_session)

        ticket = ticket_repo.create(tenant_id=TENANT_A, channel="slack", severity="P2")
        diag_repo.create(
            tenant_id=TENANT_A, ticket_id=ticket.id,
            field_name="k1", field_value="v1",
        )
        diag_repo.create(
            tenant_id=TENANT_A, ticket_id=ticket.id,
            field_name="k2", field_value="v2",
        )

        results = diag_repo.list_by_ticket(tenant_id=TENANT_A, ticket_id=ticket.id)
        assert len(results) == 2


# ── Audit event isolation ─────────────────────────────────────────────────────

class TestAuditEventIsolation:
    def test_tenant_b_cannot_read_tenant_a_audit_event(self, db_session):
        repo = AuditRepository(db_session)
        event = repo.append(
            tenant_id=TENANT_A,
            event_type="TICKET_CREATED",
            actor="alice.chen",
            payload={"ticket_id": "t-001"},
        )

        with pytest.raises(TenantAccessError):
            repo.get_by_id(tenant_id=TENANT_B, event_id=event.id)

    def test_tenant_b_list_excludes_tenant_a_events(self, db_session):
        repo = AuditRepository(db_session)
        repo.append(
            tenant_id=TENANT_A,
            event_type="TICKET_CREATED",
            actor="alice.chen",
            payload={},
        )
        assert repo.list_by_tenant(tenant_id=TENANT_B) == []

    def test_each_tenant_sees_only_own_audit_events(self, db_session):
        repo = AuditRepository(db_session)
        repo.append(tenant_id=TENANT_A, event_type="E1", actor="a", payload={})
        repo.append(tenant_id=TENANT_B, event_type="E1", actor="b", payload={})

        a_events = repo.list_by_tenant(tenant_id=TENANT_A)
        b_events = repo.list_by_tenant(tenant_id=TENANT_B)

        assert len(a_events) == 1 and a_events[0].tenant_id == TENANT_A
        assert len(b_events) == 1 and b_events[0].tenant_id == TENANT_B


# ── TenantAccessError contract ────────────────────────────────────────────────

class TestTenantAccessError:
    def test_error_message_contains_resource_type(self, db_session):
        repo = TicketRepository(db_session)
        ticket = repo.create(tenant_id=TENANT_A, channel="slack", severity="P2")

        with pytest.raises(TenantAccessError) as exc_info:
            repo.get_by_id(tenant_id=TENANT_B, ticket_id=ticket.id)

        assert "Ticket" in str(exc_info.value)

    def test_error_message_contains_requesting_tenant(self, db_session):
        repo = TicketRepository(db_session)
        ticket = repo.create(tenant_id=TENANT_A, channel="slack", severity="P2")

        with pytest.raises(TenantAccessError) as exc_info:
            repo.get_by_id(tenant_id=TENANT_B, ticket_id=ticket.id)

        assert TENANT_B in str(exc_info.value)

    def test_error_attributes_populated(self, db_session):
        repo = TicketRepository(db_session)
        ticket = repo.create(tenant_id=TENANT_A, channel="slack", severity="P2")

        exc: TenantAccessError | None = None
        try:
            repo.get_by_id(tenant_id=TENANT_B, ticket_id=ticket.id)
        except TenantAccessError as e:
            exc = e

        assert exc is not None
        assert exc.resource == "Ticket"
        assert exc.resource_id == ticket.id
        assert exc.requested_tenant == TENANT_B

    def test_diagnostic_isolation_error_attributes(self, db_session):
        ticket_repo = TicketRepository(db_session)
        diag_repo = DiagnosticRepository(db_session)
        ticket = ticket_repo.create(tenant_id=TENANT_A, channel="jira", severity="P1")
        diag = diag_repo.create(
            tenant_id=TENANT_A, ticket_id=ticket.id,
            field_name="region", field_value="eu-west-1",
        )

        with pytest.raises(TenantAccessError) as exc_info:
            diag_repo.get_by_id(tenant_id=TENANT_B, diagnostic_id=diag.id)

        assert exc_info.value.resource == "Diagnostic"
        assert exc_info.value.requested_tenant == TENANT_B


# ── Audit hash chain ──────────────────────────────────────────────────────────

class TestAuditHashChain:
    def test_empty_chain_verifies(self, db_session):
        repo = AuditRepository(db_session)
        ok, msg = repo.verify_chain(tenant_id=TENANT_A)
        assert ok is True

    def test_single_event_chain_verifies(self, db_session):
        repo = AuditRepository(db_session)
        repo.append(
            tenant_id=TENANT_A,
            event_type="TICKET_CREATED",
            actor="alice.chen",
            payload={"ticket_id": "t-001"},
        )
        ok, msg = repo.verify_chain(tenant_id=TENANT_A)
        assert ok is True, msg

    def test_multi_event_chain_verifies(self, db_session):
        repo = AuditRepository(db_session)
        for i in range(5):
            repo.append(
                tenant_id=TENANT_A,
                event_type=f"EVENT_{i}",
                actor="system",
                payload={"seq": i},
            )
        ok, msg = repo.verify_chain(tenant_id=TENANT_A)
        assert ok is True, msg

    def test_chain_is_independent_per_tenant(self, db_session):
        repo = AuditRepository(db_session)
        repo.append(tenant_id=TENANT_A, event_type="E1", actor="a", payload={})
        repo.append(tenant_id=TENANT_B, event_type="E1", actor="b", payload={})
        repo.append(tenant_id=TENANT_A, event_type="E2", actor="a", payload={})

        ok_a, _ = repo.verify_chain(tenant_id=TENANT_A)
        ok_b, _ = repo.verify_chain(tenant_id=TENANT_B)
        assert ok_a is True
        assert ok_b is True

    def test_first_event_has_empty_previous_hash(self, db_session):
        repo = AuditRepository(db_session)
        event = repo.append(
            tenant_id=TENANT_A, event_type="E1", actor="system", payload={}
        )
        assert event.previous_hash == ""

    def test_subsequent_event_links_to_prior_hash(self, db_session):
        repo = AuditRepository(db_session)
        e1 = repo.append(
            tenant_id=TENANT_A, event_type="E1", actor="system", payload={}
        )
        e2 = repo.append(
            tenant_id=TENANT_A, event_type="E2", actor="system", payload={}
        )
        assert e2.previous_hash == e1.current_hash

    def test_tampered_current_hash_detected(self, db_session):
        repo = AuditRepository(db_session)
        repo.append(tenant_id=TENANT_A, event_type="E1", actor="a", payload={})
        e2 = repo.append(tenant_id=TENANT_A, event_type="E2", actor="a", payload={})

        # Directly corrupt the stored hash
        e2.current_hash = "deadbeef" * 8
        db_session.commit()

        ok, msg = repo.verify_chain(tenant_id=TENANT_A)
        assert ok is False
        assert "tampered" in msg.lower()

    def test_tampered_payload_detected(self, db_session):
        repo = AuditRepository(db_session)
        e1 = repo.append(
            tenant_id=TENANT_A,
            event_type="TICKET_CREATED",
            actor="alice.chen",
            payload={"ticket_id": "original-id"},
        )

        # Silently mutate the payload without updating the hash
        e1.payload_json = '{"ticket_id": "tampered-id"}'
        db_session.commit()

        ok, msg = repo.verify_chain(tenant_id=TENANT_A)
        assert ok is False
        assert "tampered" in msg.lower()

    def test_verify_returns_event_count_on_success(self, db_session):
        repo = AuditRepository(db_session)
        for _ in range(3):
            repo.append(tenant_id=TENANT_A, event_type="E", actor="a", payload={})

        ok, msg = repo.verify_chain(tenant_id=TENANT_A)
        assert ok is True
        assert "3" in msg
