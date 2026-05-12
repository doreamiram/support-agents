"""Tests for AuditLogger service wrapper (Phase 6).

Covers:
  - append() delegates to AuditRepository and writes an event
  - list_events() returns tenant-scoped events in insertion order
  - verify_chain() returns VerificationResult with valid=True for a clean chain
  - verify_chain() returns valid=False and chain_breaks when tampering detected
  - verify_chain() returns event_count matching the number of events written
  - Verification result never exposes raw payload content
"""

import json

import pytest

from app.db.repositories.audit_repository import AuditRepository
from app.services.audit_logger import AuditLogger, VerificationResult


# ── Fixtures ──────────────────────────────────────────────────────────────────
# `db_session` is provided by conftest.py (function-scoped in-memory SQLite).


@pytest.fixture
def logger(db_session) -> AuditLogger:
    return AuditLogger(db_session)


# ── append ────────────────────────────────────────────────────────────────────

class TestAuditLoggerAppend:
    def test_append_returns_audit_event(self, logger):
        from app.db.models import AuditEvent
        event = logger.append(
            tenant_id="acme-corp",
            event_type="test_event",
            actor="test_actor",
            payload={"key": "value"},
        )
        assert isinstance(event, AuditEvent)

    def test_append_stores_event_type(self, logger):
        event = logger.append(
            tenant_id="acme-corp",
            event_type="classification_completed",
            actor="orchestrator",
            payload={"result": "incident"},
        )
        assert event.event_type == "classification_completed"

    def test_append_stores_tenant_id(self, logger):
        event = logger.append(
            tenant_id="vertex-systems",
            event_type="routing_decision",
            actor="orchestrator",
            payload={"action": "tier2"},
        )
        assert event.tenant_id == "vertex-systems"

    def test_append_stores_actor(self, logger):
        event = logger.append(
            tenant_id="acme-corp",
            event_type="routing_decision",
            actor="orchestrator",
            payload={},
        )
        assert event.actor == "orchestrator"

    def test_append_delegates_to_repository(self, db_session, logger):
        logger.append(
            tenant_id="acme-corp",
            event_type="test_event",
            actor="test",
            payload={"msg": "hello"},
        )
        # Verify via the repository directly.
        events = AuditRepository(db_session).list_by_tenant(tenant_id="acme-corp")
        assert len(events) == 1
        assert events[0].event_type == "test_event"

    def test_multiple_appends_ordered(self, logger):
        for i in range(3):
            logger.append(
                tenant_id="acme-corp",
                event_type=f"event_{i}",
                actor="test",
                payload={"seq": i},
            )
        events = logger.list_events(tenant_id="acme-corp")
        event_types = [e.event_type for e in events]
        assert event_types == ["event_0", "event_1", "event_2"]


# ── list_events ───────────────────────────────────────────────────────────────

class TestAuditLoggerListEvents:
    def test_list_events_empty_for_unknown_tenant(self, logger):
        events = logger.list_events(tenant_id="unknown-tenant")
        assert events == []

    def test_list_events_returns_only_tenant_events(self, logger):
        logger.append(
            tenant_id="acme-corp",
            event_type="acme_event",
            actor="test",
            payload={},
        )
        logger.append(
            tenant_id="vertex-systems",
            event_type="vertex_event",
            actor="test",
            payload={},
        )
        acme_events = logger.list_events(tenant_id="acme-corp")
        assert len(acme_events) == 1
        assert acme_events[0].event_type == "acme_event"

    def test_list_events_in_insertion_order(self, logger):
        for event_type in ("alpha", "beta", "gamma"):
            logger.append(
                tenant_id="acme-corp",
                event_type=event_type,
                actor="test",
                payload={},
            )
        events = logger.list_events(tenant_id="acme-corp")
        assert [e.event_type for e in events] == ["alpha", "beta", "gamma"]


# ── verify_chain ──────────────────────────────────────────────────────────────

class TestAuditLoggerVerifyChain:
    def test_verify_empty_chain_is_valid(self, logger):
        result = logger.verify_chain(tenant_id="acme-corp")
        assert isinstance(result, VerificationResult)
        assert result.valid is True

    def test_verify_empty_chain_event_count_zero(self, logger):
        result = logger.verify_chain(tenant_id="acme-corp")
        assert result.event_count == 0

    def test_verify_empty_chain_no_breaks(self, logger):
        result = logger.verify_chain(tenant_id="acme-corp")
        assert result.chain_breaks == []

    def test_verify_single_event_chain_valid(self, logger):
        logger.append(
            tenant_id="acme-corp",
            event_type="test_event",
            actor="test",
            payload={"data": "value"},
        )
        result = logger.verify_chain(tenant_id="acme-corp")
        assert result.valid is True

    def test_verify_multiple_events_chain_valid(self, logger):
        for i in range(5):
            logger.append(
                tenant_id="acme-corp",
                event_type=f"evt_{i}",
                actor="test",
                payload={"seq": i},
            )
        result = logger.verify_chain(tenant_id="acme-corp")
        assert result.valid is True
        assert result.event_count == 5

    def test_verify_event_count_matches_appended(self, logger):
        for _ in range(3):
            logger.append(
                tenant_id="acme-corp",
                event_type="counted_event",
                actor="test",
                payload={},
            )
        result = logger.verify_chain(tenant_id="acme-corp")
        assert result.event_count == 3

    def test_verify_chain_result_has_message(self, logger):
        result = logger.verify_chain(tenant_id="acme-corp")
        assert isinstance(result.message, str)
        assert len(result.message) > 0

    def test_verify_chain_result_is_dataclass(self, logger):
        result = logger.verify_chain(tenant_id="acme-corp")
        assert hasattr(result, "valid")
        assert hasattr(result, "event_count")
        assert hasattr(result, "message")
        assert hasattr(result, "chain_breaks")

    def test_verify_detects_tampering(self, db_session, logger):
        """Tampering with a stored record must be detected by chain verification."""
        logger.append(
            tenant_id="acme-corp",
            event_type="original_event",
            actor="test",
            payload={"data": "original"},
        )
        logger.append(
            tenant_id="acme-corp",
            event_type="second_event",
            actor="test",
            payload={"data": "second"},
        )

        # Tamper: alter the payload_json of the first event directly via the DB.
        from app.db.models import AuditEvent
        events = db_session.query(AuditEvent).filter(
            AuditEvent.tenant_id == "acme-corp"
        ).order_by(AuditEvent.id.asc()).all()
        assert len(events) == 2
        # Overwrite the first event's payload without updating its hash.
        events[0].payload_json = json.dumps({"data": "TAMPERED"})
        db_session.commit()

        result = logger.verify_chain(tenant_id="acme-corp")
        assert result.valid is False
        assert len(result.chain_breaks) > 0

    def test_verify_chain_breaks_contain_description_on_tampering(self, db_session, logger):
        logger.append(
            tenant_id="acme-corp",
            event_type="event_a",
            actor="test",
            payload={"x": 1},
        )
        logger.append(
            tenant_id="acme-corp",
            event_type="event_b",
            actor="test",
            payload={"x": 2},
        )
        from app.db.models import AuditEvent
        events = db_session.query(AuditEvent).filter(
            AuditEvent.tenant_id == "acme-corp"
        ).order_by(AuditEvent.id.asc()).all()
        events[0].payload_json = json.dumps({"x": 999})
        db_session.commit()

        result = logger.verify_chain(tenant_id="acme-corp")
        assert not result.valid
        assert any("tamper" in b.lower() or "mismatch" in b.lower() for b in result.chain_breaks)

    def test_verify_result_does_not_expose_payload_content(self, logger):
        logger.append(
            tenant_id="acme-corp",
            event_type="sensitive_event",
            actor="test",
            payload={"secret": "super-secret-value"},
        )
        result = logger.verify_chain(tenant_id="acme-corp")
        result_str = str(result)
        assert "super-secret-value" not in result_str
        assert "payload_json" not in result_str

    def test_verify_different_tenants_independent(self, logger):
        logger.append(
            tenant_id="acme-corp",
            event_type="acme_event",
            actor="test",
            payload={},
        )
        logger.append(
            tenant_id="vertex-systems",
            event_type="vertex_event",
            actor="test",
            payload={},
        )
        acme_result = logger.verify_chain(tenant_id="acme-corp")
        vertex_result = logger.verify_chain(tenant_id="vertex-systems")
        assert acme_result.valid is True
        assert acme_result.event_count == 1
        assert vertex_result.valid is True
        assert vertex_result.event_count == 1
