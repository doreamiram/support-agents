"""Tests for CommunicationPolicy (app/services/communication_policy.py).

Uses FakeClock to control time deterministically.

Timezone notes (static offsets used in the prototype):
  America/New_York = UTC-5 (EST, DST not modelled)
  Europe/London    = UTC+0

ACME Corp quiet hours (from config/quiet_hours.yaml):
  Weeknights Mon-Fri 22:00-08:00 EST → 03:00-13:00 UTC the next/same day
  Weekends   Sat-Sun 21:00-09:00 EST → 02:00-14:00 UTC

  critical_override: true, cooldown_minutes: 30

Key UTC test times (January 2026, EST = UTC-5):
  BUSINESS  = 2026-01-05 15:00 UTC  →  Mon 10:00 EST  (outside quiet hours)
  QUIET     = 2026-01-06 03:30 UTC  →  Mon 22:30 EST  (inside overnight window)
"""

from datetime import datetime, timedelta, timezone

import pytest

from app.config.loader import load_config
from app.services.communication_policy import CommDecision, CommunicationPolicy
from app.utils.clock import FakeClock

# January 5, 2026 = Monday
_BUSINESS_UTC = datetime(2026, 1, 5, 15, 0, 0, tzinfo=timezone.utc)   # Mon 10:00 EST
_QUIET_UTC    = datetime(2026, 1, 6, 3, 30, 0, tzinfo=timezone.utc)    # Mon 22:30 EST


@pytest.fixture(scope="module")
def config():
    return load_config()


# ── Quiet hours suppression ───────────────────────────────────────────────────

class TestQuietHoursSuppress:
    def test_non_critical_suppressed_during_quiet_hours(self, config):
        clock = FakeClock(start=_QUIET_UTC)
        policy = CommunicationPolicy(config=config, clock=clock)
        decision = policy.check(tenant_id="acme-corp", severity="P2")
        assert not decision.allowed
        assert decision.suppressed_by == "quiet_hours"

    def test_non_critical_allowed_during_business_hours(self, config):
        clock = FakeClock(start=_BUSINESS_UTC)
        policy = CommunicationPolicy(config=config, clock=clock)
        decision = policy.check(tenant_id="acme-corp", severity="P2")
        assert decision.allowed

    def test_p3_suppressed_during_quiet_hours(self, config):
        clock = FakeClock(start=_QUIET_UTC)
        policy = CommunicationPolicy(config=config, clock=clock)
        decision = policy.check(tenant_id="acme-corp", severity="P3")
        assert not decision.allowed
        assert decision.suppressed_by == "quiet_hours"

    def test_reason_string_present_on_suppress(self, config):
        clock = FakeClock(start=_QUIET_UTC)
        policy = CommunicationPolicy(config=config, clock=clock)
        decision = policy.check(tenant_id="acme-corp", severity="P2")
        assert decision.reason  # non-empty

    def test_vertex_quiet_hours_different_window(self, config):
        """Vertex uses Europe/London (UTC+0): window is 23:00-07:00 local."""
        # Mon 23:30 UTC = 23:30 London (inside Vertex overnight window)
        vertex_quiet = datetime(2026, 1, 5, 23, 30, 0, tzinfo=timezone.utc)
        clock = FakeClock(start=vertex_quiet)
        policy = CommunicationPolicy(config=config, clock=clock)
        decision = policy.check(tenant_id="vertex-systems", severity="P2")
        assert not decision.allowed
        assert decision.suppressed_by == "quiet_hours"


# ── Critical override ─────────────────────────────────────────────────────────

class TestCriticalOverride:
    def test_p1_bypasses_quiet_hours_when_override_configured(self, config):
        """ACME has critical_override: true — P1 must always be allowed."""
        clock = FakeClock(start=_QUIET_UTC)
        policy = CommunicationPolicy(config=config, clock=clock)
        decision = policy.check(tenant_id="acme-corp", severity="P1")
        assert decision.allowed

    def test_critical_override_reason_string(self, config):
        clock = FakeClock(start=_QUIET_UTC)
        policy = CommunicationPolicy(config=config, clock=clock)
        decision = policy.check(tenant_id="acme-corp", severity="P1")
        assert "critical_override" in decision.reason

    def test_suppressed_by_is_none_on_critical_override(self, config):
        clock = FakeClock(start=_QUIET_UTC)
        policy = CommunicationPolicy(config=config, clock=clock)
        decision = policy.check(tenant_id="acme-corp", severity="P1")
        assert decision.suppressed_by is None

    def test_p2_not_overridden_during_quiet_hours(self, config):
        """P2 is not critical — override does not apply."""
        clock = FakeClock(start=_QUIET_UTC)
        policy = CommunicationPolicy(config=config, clock=clock)
        decision = policy.check(tenant_id="acme-corp", severity="P2")
        assert not decision.allowed


# ── Cooldown enforcement ──────────────────────────────────────────────────────

class TestCooldown:
    def test_cooldown_suppresses_message_within_window(self, config):
        """ACME cooldown = 30 minutes; sending after only 10 minutes is suppressed."""
        clock = FakeClock(start=_BUSINESS_UTC)
        policy = CommunicationPolicy(config=config, clock=clock)
        last = _BUSINESS_UTC - timedelta(minutes=10)
        decision = policy.check(
            tenant_id="acme-corp", severity="P2", last_message_at=last
        )
        assert not decision.allowed
        assert decision.suppressed_by == "cooldown"

    def test_cooldown_allows_after_full_window(self, config):
        """45 minutes elapsed > 30-minute cooldown → allowed."""
        clock = FakeClock(start=_BUSINESS_UTC)
        policy = CommunicationPolicy(config=config, clock=clock)
        last = _BUSINESS_UTC - timedelta(minutes=45)
        decision = policy.check(
            tenant_id="acme-corp", severity="P2", last_message_at=last
        )
        assert decision.allowed

    def test_cooldown_exact_boundary_suppresses(self, config):
        """Exactly at cooldown boundary (30 min elapsed) is still suppressed
        because the check is `elapsed < cooldown` (strict less-than)."""
        clock = FakeClock(start=_BUSINESS_UTC)
        policy = CommunicationPolicy(config=config, clock=clock)
        last = _BUSINESS_UTC - timedelta(minutes=30)
        decision = policy.check(
            tenant_id="acme-corp", severity="P2", last_message_at=last
        )
        # elapsed == 30, cooldown == 30: 30 < 30 is False → allowed.
        assert decision.allowed

    def test_no_cooldown_without_last_message(self, config):
        """Without a prior message, cooldown does not apply."""
        clock = FakeClock(start=_BUSINESS_UTC)
        policy = CommunicationPolicy(config=config, clock=clock)
        decision = policy.check(
            tenant_id="acme-corp", severity="P2", last_message_at=None
        )
        assert decision.allowed

    def test_vertex_longer_cooldown(self, config):
        """Vertex cooldown = 45 minutes; sending after 30 minutes is suppressed."""
        # Vertex window: Mon 23:00-07:00 London.  Use a safe daytime UTC time.
        vertex_day = datetime(2026, 1, 5, 12, 0, 0, tzinfo=timezone.utc)  # Mon 12:00 UTC (daytime)
        clock = FakeClock(start=vertex_day)
        policy = CommunicationPolicy(config=config, clock=clock)
        last = vertex_day - timedelta(minutes=30)
        decision = policy.check(
            tenant_id="vertex-systems", severity="P2", last_message_at=last
        )
        assert not decision.allowed
        assert decision.suppressed_by == "cooldown"


# ── No config fallback ────────────────────────────────────────────────────────

class TestNoConfigFallback:
    def test_unknown_tenant_is_allowed(self, config):
        """If no quiet hours rule exists for the tenant, always allow."""
        clock = FakeClock(start=_QUIET_UTC)
        policy = CommunicationPolicy(config=config, clock=clock)
        decision = policy.check(tenant_id="nonexistent-tenant", severity="P2")
        assert decision.allowed
        assert decision.reason == "no_quiet_hours_configured"

    def test_comm_decision_is_dataclass(self, config):
        clock = FakeClock(start=_BUSINESS_UTC)
        policy = CommunicationPolicy(config=config, clock=clock)
        decision = policy.check(tenant_id="acme-corp", severity="P2")
        assert isinstance(decision, CommDecision)
        assert hasattr(decision, "allowed")
        assert hasattr(decision, "reason")
        assert hasattr(decision, "suppressed_by")
