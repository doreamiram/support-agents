"""Tests for SLATracker (app/agents/sla_tracker.py).

All breach detection uses FakeClock — no real-time waits.
"""

from datetime import timedelta

import pytest

from app.agents.sla_tracker import SLAStatus, SLATracker
from app.config.loader import load_config
from app.db.repositories.sla_state_repository import SLAStateRepository
from app.db.repositories.ticket_repository import TicketRepository
from app.utils.clock import FakeClock


# ── Shared fixtures ───────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def config():
    return load_config()


def _make_ticket(db_session, tenant_id: str = "acme-corp", severity: str = "P1") -> str:
    """Create a minimal ticket and return its id."""
    ticket = TicketRepository(db_session).create(
        tenant_id=tenant_id,
        channel="slack",
        severity=severity,
    )
    return ticket.id


# ── SLA initialization ────────────────────────────────────────────────────────

class TestSLAInitialization:
    def test_initialize_returns_sla_status(self, db_session, config):
        clock = FakeClock()
        tracker = SLATracker(config=config, clock=clock, db=db_session)
        tid = _make_ticket(db_session)
        status = tracker.initialize(tid, "acme-corp", "P1")
        assert isinstance(status, SLAStatus)

    def test_initialize_state_is_open(self, db_session, config):
        clock = FakeClock()
        tracker = SLATracker(config=config, clock=clock, db=db_session)
        tid = _make_ticket(db_session)
        status = tracker.initialize(tid, "acme-corp", "P1")
        assert status.state == "OPEN"

    def test_initialize_no_breach_flags(self, db_session, config):
        clock = FakeClock()
        tracker = SLATracker(config=config, clock=clock, db=db_session)
        tid = _make_ticket(db_session)
        status = tracker.initialize(tid, "acme-corp", "P1")
        assert not status.response_breached
        assert not status.resolution_breached

    def test_initialize_engineer_flags_false(self, db_session, config):
        clock = FakeClock()
        tracker = SLATracker(config=config, clock=clock, db=db_session)
        tid = _make_ticket(db_session)
        status = tracker.initialize(tid, "acme-corp", "P1")
        assert not status.engineer_notified
        assert not status.engineer_engaged

    def test_initialize_p1_response_deadline(self, db_session, config):
        """P1 response time = 15 minutes per sla_rules.yaml."""
        clock = FakeClock()
        t0 = clock.now()
        tracker = SLATracker(config=config, clock=clock, db=db_session)
        tid = _make_ticket(db_session, severity="P1")
        status = tracker.initialize(tid, "acme-corp", "P1")
        assert status.response_deadline == t0 + timedelta(minutes=15)

    def test_initialize_p2_response_deadline(self, db_session, config):
        """P2 response time = 60 minutes per sla_rules.yaml."""
        clock = FakeClock()
        t0 = clock.now()
        tracker = SLATracker(config=config, clock=clock, db=db_session)
        tid = _make_ticket(db_session, severity="P2")
        status = tracker.initialize(tid, "acme-corp", "P2")
        assert status.response_deadline == t0 + timedelta(minutes=60)

    def test_initialize_p1_resolution_deadline(self, db_session, config):
        """P1 resolution time = 240 minutes per sla_rules.yaml."""
        clock = FakeClock()
        t0 = clock.now()
        tracker = SLATracker(config=config, clock=clock, db=db_session)
        tid = _make_ticket(db_session, severity="P1")
        status = tracker.initialize(tid, "acme-corp", "P1")
        assert status.resolution_deadline == t0 + timedelta(minutes=240)

    def test_initialize_creates_db_sla_state(self, db_session, config):
        clock = FakeClock()
        tracker = SLATracker(config=config, clock=clock, db=db_session)
        tid = _make_ticket(db_session)
        tracker.initialize(tid, "acme-corp", "P1")
        db_state = SLAStateRepository(db_session).get_by_ticket_id(
            tenant_id="acme-corp", ticket_id=tid
        )
        assert db_state is not None
        assert db_state.ticket_id == tid

    def test_get_status_returns_snapshot(self, db_session, config):
        clock = FakeClock()
        tracker = SLATracker(config=config, clock=clock, db=db_session)
        tid = _make_ticket(db_session)
        tracker.initialize(tid, "acme-corp", "P1")
        status = tracker.get_status(tid)
        assert status is not None
        assert status.ticket_id == tid

    def test_get_status_unknown_ticket_returns_none(self, db_session, config):
        tracker = SLATracker(config=config, clock=FakeClock(), db=db_session)
        assert tracker.get_status("no-such-ticket") is None


# ── Breach detection ──────────────────────────────────────────────────────────

class TestSLABreachDetection:
    def test_no_breach_before_response_deadline(self, db_session, config):
        clock = FakeClock()
        tracker = SLATracker(config=config, clock=clock, db=db_session)
        tid = _make_ticket(db_session, severity="P1")
        tracker.initialize(tid, "acme-corp", "P1")
        clock.advance(minutes=10)   # P1 response deadline = 15 min
        status = tracker.check_breach(tid, "acme-corp")
        assert not status.response_breached

    def test_no_breach_before_resolution_deadline(self, db_session, config):
        clock = FakeClock()
        tracker = SLATracker(config=config, clock=clock, db=db_session)
        tid = _make_ticket(db_session, severity="P1")
        tracker.initialize(tid, "acme-corp", "P1")
        clock.advance(minutes=200)  # P1 resolution deadline = 240 min
        status = tracker.check_breach(tid, "acme-corp")
        assert not status.resolution_breached

    def test_response_breach_detected_after_deadline(self, db_session, config):
        clock = FakeClock()
        tracker = SLATracker(config=config, clock=clock, db=db_session)
        tid = _make_ticket(db_session, severity="P1")
        tracker.initialize(tid, "acme-corp", "P1")
        clock.advance(minutes=20)   # past P1 15-minute response deadline
        status = tracker.check_breach(tid, "acme-corp")
        assert status.response_breached

    def test_resolution_breach_detected_after_deadline(self, db_session, config):
        clock = FakeClock()
        tracker = SLATracker(config=config, clock=clock, db=db_session)
        tid = _make_ticket(db_session, severity="P1")
        tracker.initialize(tid, "acme-corp", "P1")
        clock.advance(minutes=250)  # past P1 240-minute resolution deadline
        status = tracker.check_breach(tid, "acme-corp")
        assert status.resolution_breached

    def test_breach_sets_state_to_breached(self, db_session, config):
        clock = FakeClock()
        tracker = SLATracker(config=config, clock=clock, db=db_session)
        tid = _make_ticket(db_session, severity="P1")
        tracker.initialize(tid, "acme-corp", "P1")
        clock.advance(minutes=20)
        status = tracker.check_breach(tid, "acme-corp")
        assert status.state == "BREACHED"

    def test_p2_no_breach_before_deadline(self, db_session, config):
        """P2 response deadline = 60 minutes; advancing 30 should not breach."""
        clock = FakeClock()
        tracker = SLATracker(config=config, clock=clock, db=db_session)
        tid = _make_ticket(db_session, severity="P2")
        tracker.initialize(tid, "acme-corp", "P2")
        clock.advance(minutes=30)
        status = tracker.check_breach(tid, "acme-corp")
        assert not status.response_breached

    def test_check_breach_unknown_ticket_raises(self, db_session, config):
        tracker = SLATracker(config=config, clock=FakeClock(), db=db_session)
        with pytest.raises(ValueError, match="not initialized"):
            tracker.check_breach("unknown-ticket", "acme-corp")


# ── Engineer notified vs engaged ──────────────────────────────────────────────

class TestEngineerNotifiedVsEngaged:
    def test_mark_notified_sets_engineer_notified(self, db_session, config):
        clock = FakeClock()
        tracker = SLATracker(config=config, clock=clock, db=db_session)
        tid = _make_ticket(db_session)
        tracker.initialize(tid, "acme-corp", "P1")
        status = tracker.mark_engineer_notified(tid, "acme-corp")
        assert status.engineer_notified

    def test_mark_notified_does_not_set_engaged(self, db_session, config):
        clock = FakeClock()
        tracker = SLATracker(config=config, clock=clock, db=db_session)
        tid = _make_ticket(db_session)
        tracker.initialize(tid, "acme-corp", "P1")
        status = tracker.mark_engineer_notified(tid, "acme-corp")
        assert not status.engineer_engaged

    def test_mark_notified_state_is_engineer_notified(self, db_session, config):
        clock = FakeClock()
        tracker = SLATracker(config=config, clock=clock, db=db_session)
        tid = _make_ticket(db_session)
        tracker.initialize(tid, "acme-corp", "P1")
        status = tracker.mark_engineer_notified(tid, "acme-corp")
        assert status.state == "ENGINEER_NOTIFIED"

    def test_mark_engaged_sets_both_flags(self, db_session, config):
        clock = FakeClock()
        tracker = SLATracker(config=config, clock=clock, db=db_session)
        tid = _make_ticket(db_session)
        tracker.initialize(tid, "acme-corp", "P1")
        status = tracker.mark_engineer_engaged(tid, "acme-corp")
        assert status.engineer_notified
        assert status.engineer_engaged

    def test_mark_engaged_state_is_acknowledged(self, db_session, config):
        clock = FakeClock()
        tracker = SLATracker(config=config, clock=clock, db=db_session)
        tid = _make_ticket(db_session)
        tracker.initialize(tid, "acme-corp", "P1")
        status = tracker.mark_engineer_engaged(tid, "acme-corp")
        assert status.state == "ACKNOWLEDGED"

    def test_notified_and_engaged_are_distinct_transitions(self, db_session, config):
        """Notifying sets notified-only; engagement is a separate second step."""
        clock = FakeClock()
        tracker = SLATracker(config=config, clock=clock, db=db_session)
        tid = _make_ticket(db_session)
        tracker.initialize(tid, "acme-corp", "P2")

        notified = tracker.mark_engineer_notified(tid, "acme-corp")
        assert notified.engineer_notified
        assert not notified.engineer_engaged

        engaged = tracker.mark_engineer_engaged(tid, "acme-corp")
        assert engaged.engineer_notified
        assert engaged.engineer_engaged

    def test_response_not_breached_after_engagement(self, db_session, config):
        """Once the engineer engages, response SLA is satisfied."""
        clock = FakeClock()
        tracker = SLATracker(config=config, clock=clock, db=db_session)
        tid = _make_ticket(db_session, severity="P1")
        tracker.initialize(tid, "acme-corp", "P1")
        tracker.mark_engineer_engaged(tid, "acme-corp")  # acknowledge before deadline
        clock.advance(minutes=30)  # past P1 response deadline
        status = tracker.check_breach(tid, "acme-corp")
        assert not status.response_breached

    def test_mark_resolved_sets_state(self, db_session, config):
        clock = FakeClock()
        tracker = SLATracker(config=config, clock=clock, db=db_session)
        tid = _make_ticket(db_session)
        tracker.initialize(tid, "acme-corp", "P1")
        status = tracker.mark_resolved(tid, "acme-corp")
        assert status.state == "RESOLVED"

    def test_resolved_ticket_not_rebreached(self, db_session, config):
        clock = FakeClock()
        tracker = SLATracker(config=config, clock=clock, db=db_session)
        tid = _make_ticket(db_session, severity="P1")
        tracker.initialize(tid, "acme-corp", "P1")
        tracker.mark_resolved(tid, "acme-corp")
        clock.advance(minutes=500)  # well past all deadlines
        status = tracker.check_breach(tid, "acme-corp")
        # Once resolved, check_breach returns without re-evaluating breach.
        assert status.state == "RESOLVED"
