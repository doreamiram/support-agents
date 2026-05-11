from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from app.config.models import AppConfig, QuietHoursRule, QuietWindow
from app.utils.clock import ClockProvider

# Static UTC-offset table for the IANA timezone names used in quiet_hours.yaml.
# DST is not modelled — this is a prototype without the tzdata package.
# Offsets are given in minutes.  Add entries as needed.
_UTC_OFFSET_MINUTES: dict[str, int] = {
    "UTC": 0,
    "GMT": 0,
    "America/New_York": -5 * 60,      # EST (ignores EDT)
    "America/Chicago": -6 * 60,
    "America/Denver": -7 * 60,
    "America/Los_Angeles": -8 * 60,
    "Europe/London": 0,                # GMT (ignores BST)
    "Europe/Paris": 1 * 60,
    "Europe/Berlin": 1 * 60,
    "Asia/Tokyo": 9 * 60,
    "Asia/Singapore": 8 * 60,
    "Australia/Sydney": 11 * 60,
}


@dataclass
class CommDecision:
    """Result of a communication policy check."""

    allowed: bool
    reason: str
    suppressed_by: Optional[str] = None   # "quiet_hours" | "cooldown" | None


class CommunicationPolicy:
    """
    Gate outbound messages to meaningful state changes only.

    Rules applied in order:
      1. P1 (Sev-1) + critical_override → always allow (bypass quiet hours and cooldown).
      2. Current clock time falls inside a quiet window → suppress.
      3. Cooldown not yet elapsed since last message → suppress.
      4. Otherwise → allow.

    No real messages are sent; callers act on the CommDecision.
    """

    _CRITICAL_SEVERITIES = {"P1", "Sev-1", "sev-1", "sev1", "critical"}

    def __init__(self, config: AppConfig, clock: ClockProvider) -> None:
        self._clock = clock
        self._rules: dict[str, QuietHoursRule] = {
            r.tenant_id: r for r in config.quiet_hours.quiet_hours
        }

    def check(
        self,
        *,
        tenant_id: str,
        severity: str,
        last_message_at: Optional[datetime] = None,
    ) -> CommDecision:
        """
        Decide whether an outbound message is allowed.

        Parameters
        ----------
        tenant_id:        Tenant whose quiet hours apply.
        severity:         Ticket severity (P1 / P2 / P3 / P4).
        last_message_at:  When the last outbound message was sent (for cooldown).
                          Pass None if no prior message has been sent.
        """
        rule = self._rules.get(tenant_id)
        if rule is None:
            return CommDecision(allowed=True, reason="no_quiet_hours_configured")

        now = self._clock.now()
        is_critical = severity in self._CRITICAL_SEVERITIES

        # Rule 1: critical override — P1 bypasses everything when configured.
        if is_critical and rule.critical_override:
            return CommDecision(allowed=True, reason="critical_override_applied")

        # Rule 2: quiet hours window.
        if self._in_quiet_hours(rule, now):
            return CommDecision(
                allowed=False,
                reason="suppressed_quiet_hours",
                suppressed_by="quiet_hours",
            )

        # Rule 3: cooldown between non-critical messages.
        if last_message_at is not None:
            elapsed_minutes = (now - last_message_at).total_seconds() / 60.0
            if elapsed_minutes < rule.cooldown_minutes:
                remaining = int(rule.cooldown_minutes - elapsed_minutes)
                return CommDecision(
                    allowed=False,
                    reason=f"suppressed_cooldown_{remaining}min_remaining",
                    suppressed_by="cooldown",
                )

        return CommDecision(allowed=True, reason="allowed")

    # ── Private helpers ───────────────────────────────────────────────────────

    def _in_quiet_hours(self, rule: QuietHoursRule, now: datetime) -> bool:
        """Return True if `now` falls inside any configured quiet window."""
        for window in rule.windows:
            if self._window_active(window, now):
                return True
        return False

    def _window_active(self, window: QuietWindow, utc_now: datetime) -> bool:
        """Check whether utc_now falls inside this window after timezone conversion."""
        offset_minutes = _UTC_OFFSET_MINUTES.get(window.timezone, 0)
        local = utc_now + timedelta(minutes=offset_minutes)
        day_name = local.strftime("%A").lower()

        if day_name not in window.days:
            return False

        start_h, start_m = map(int, window.start.split(":"))
        end_h, end_m = map(int, window.end.split(":"))
        current_minutes = local.hour * 60 + local.minute
        start_minutes = start_h * 60 + start_m
        end_minutes = end_h * 60 + end_m

        if start_minutes <= end_minutes:
            # Same-day window (e.g., 09:00–22:00).
            return start_minutes <= current_minutes < end_minutes
        else:
            # Overnight window (e.g., 22:00–08:00): active from start until midnight
            # and from midnight until end the following morning.
            return current_minutes >= start_minutes or current_minutes < end_minutes
