"""
Minimal in-memory telemetry for demo and evaluation purposes.

Records high-level operational events only — no sensitive data or raw payloads.
Satisfies NFR-07 (operational telemetry), NFR-14 (measurable behaviour),
and NFR-15 (regression-detectable metrics) at prototype scope.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional


@dataclass
class TelemetryEvent:
    """A single high-level telemetry event. No raw payload content."""

    event_type: str
    timestamp: str
    metadata: dict[str, Any]


class Telemetry:
    """
    Simple in-memory telemetry collector.

    Allowed event types (all high-level, no sensitive data):
      scenario_started        — a demo scenario began execution
      scenario_completed      — a demo scenario finished (pass or fail)
      tier1_response_generated — first response successfully produced in Tier 1
      handoff_created         — a Tier 2 HandoffPacket was produced
      audit_verified          — audit chain verified via AuditLogger
      sla_breach_detected     — SLA deadline exceeded for a ticket
      escalation_triggered    — escalation engine fired (simulated)
      scenario_error          — unexpected exception in a scenario

    No external telemetry provider. No network calls. No sensitive payloads.
    """

    _ALLOWED_EVENT_TYPES: frozenset[str] = frozenset(
        {
            "scenario_started",
            "scenario_completed",
            "tier1_response_generated",
            "handoff_created",
            "audit_verified",
            "sla_breach_detected",
            "escalation_triggered",
            "scenario_error",
        }
    )

    def __init__(self) -> None:
        self._events: list[TelemetryEvent] = []

    def record(
        self, event_type: str, metadata: Optional[dict[str, Any]] = None
    ) -> None:
        """Record a high-level telemetry event.

        Raises ValueError for unknown event types to prevent accidental
        recording of sensitive or raw-payload data.
        """
        if event_type not in self._ALLOWED_EVENT_TYPES:
            raise ValueError(
                f"Unknown telemetry event type: {event_type!r}. "
                f"Allowed: {sorted(self._ALLOWED_EVENT_TYPES)}"
            )
        self._events.append(
            TelemetryEvent(
                event_type=event_type,
                timestamp=datetime.now(timezone.utc).isoformat(),
                metadata=dict(metadata) if metadata else {},
            )
        )

    def events(self) -> list[TelemetryEvent]:
        """Return all recorded events in insertion order (copy)."""
        return list(self._events)

    def count(self, event_type: str) -> int:
        """Return the count of events of a given type."""
        return sum(1 for e in self._events if e.event_type == event_type)

    def summary(self) -> dict[str, int]:
        """Return a count summary keyed by event type."""
        result: dict[str, int] = {}
        for e in self._events:
            result[e.event_type] = result.get(e.event_type, 0) + 1
        return result
