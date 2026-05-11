from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from app.config.models import AppConfig, SLARule
from app.db.repositories.sla_state_repository import SLAStateRepository
from app.utils.clock import ClockProvider


@dataclass
class SLAStatus:
    """In-memory snapshot of SLA state for one ticket."""

    ticket_id: str
    tenant_id: str
    severity: str
    # Lifecycle state string (not the DB enum — richer granularity here)
    state: str                      # OPEN | ENGINEER_NOTIFIED | ACKNOWLEDGED | RESOLVED | BREACHED
    response_deadline: datetime
    resolution_deadline: datetime
    response_breached: bool
    resolution_breached: bool
    # Distinction: notified = we fired the first escalation step;
    # engaged = the engineer actually acknowledged the ticket.
    engineer_notified: bool
    engineer_engaged: bool
    created_at: datetime
    checked_at: datetime


class SLATracker:
    """
    SLA state machine for incident tickets.

    Uses ClockProvider (never datetime.utcnow) for all time operations.
    Persists key state transitions to SLAStateRepository.
    Keeps full SLAStatus in-memory for fast breach checks (prototype scope).

    States: OPEN → ENGINEER_NOTIFIED → ACKNOWLEDGED → RESOLVED / BREACHED
    """

    def __init__(
        self,
        config: AppConfig,
        clock: ClockProvider,
        db: Session,
    ) -> None:
        self._clock = clock
        self._sla_repo = SLAStateRepository(db)
        # Index SLA rules by severity for O(1) lookup.
        self._rules: dict[str, SLARule] = {
            r.severity: r for r in config.sla_rules.sla_rules
        }
        # In-memory state store: ticket_id → SLAStatus.
        self._states: dict[str, SLAStatus] = {}

    # ── Public API ────────────────────────────────────────────────────────────

    def initialize(
        self,
        ticket_id: str,
        tenant_id: str,
        severity: str,
    ) -> SLAStatus:
        """
        Initialize SLA state for a newly created ticket.
        Creates a DB record and returns the in-memory SLAStatus snapshot.
        """
        now = self._clock.now()
        rule = self._rules.get(severity) or self._rules.get("P4")
        response_deadline = now + timedelta(minutes=rule.response_time_minutes)
        resolution_deadline = now + timedelta(minutes=rule.resolution_time_minutes)

        self._sla_repo.create(tenant_id=tenant_id, ticket_id=ticket_id)

        status = SLAStatus(
            ticket_id=ticket_id,
            tenant_id=tenant_id,
            severity=severity,
            state="OPEN",
            response_deadline=response_deadline,
            resolution_deadline=resolution_deadline,
            response_breached=False,
            resolution_breached=False,
            engineer_notified=False,
            engineer_engaged=False,
            created_at=now,
            checked_at=now,
        )
        self._states[ticket_id] = status
        return status

    def check_breach(self, ticket_id: str, tenant_id: str) -> SLAStatus:
        """
        Evaluate breach conditions at the current clock time.
        Persists ESCALATED status to DB if a breach is newly detected.
        Returns the updated SLAStatus snapshot.
        """
        status = self._get_state(ticket_id)
        if status.state == "RESOLVED":
            status.checked_at = self._clock.now()
            return status

        now = self._clock.now()
        status.checked_at = now

        # Response SLA: not breached once the engineer has engaged (acknowledged).
        response_breached = (
            not status.engineer_engaged and now > status.response_deadline
        )
        # Resolution SLA: breached if not yet resolved past the deadline.
        resolution_breached = now > status.resolution_deadline

        status.response_breached = response_breached
        status.resolution_breached = resolution_breached

        if response_breached or resolution_breached:
            if status.state != "BREACHED":
                status.state = "BREACHED"
                self._sla_repo.update(
                    tenant_id=tenant_id,
                    ticket_id=ticket_id,
                    status="ESCALATED",
                    breached=True,
                    breached_at=now,
                )

        return status

    def mark_engineer_notified(self, ticket_id: str, tenant_id: str) -> SLAStatus:
        """Record that the on-call engineer has been notified (step fired)."""
        status = self._get_state(ticket_id)
        if not status.engineer_notified:
            status.engineer_notified = True
            status.state = "ENGINEER_NOTIFIED"
            now = self._clock.now()
            # in_progress_at records when the engineer was first notified.
            self._sla_repo.update(
                tenant_id=tenant_id,
                ticket_id=ticket_id,
                status="IN_PROGRESS",
                in_progress_at=now,
            )
        return status

    def mark_engineer_engaged(self, ticket_id: str, tenant_id: str) -> SLAStatus:
        """Record that the engineer has acknowledged and engaged with the ticket."""
        status = self._get_state(ticket_id)
        if not status.engineer_engaged:
            status.engineer_engaged = True
            status.engineer_notified = True   # engagement implies notification
            status.state = "ACKNOWLEDGED"
            now = self._clock.now()
            self._sla_repo.update(
                tenant_id=tenant_id,
                ticket_id=ticket_id,
                status="ACKNOWLEDGED",
                acknowledged_at=now,
            )
        return status

    def mark_resolved(self, ticket_id: str, tenant_id: str) -> SLAStatus:
        """Record that the incident has been resolved."""
        status = self._get_state(ticket_id)
        status.state = "RESOLVED"
        now = self._clock.now()
        self._sla_repo.update(
            tenant_id=tenant_id,
            ticket_id=ticket_id,
            status="RESOLVED",
            resolved_at=now,
        )
        return status

    def get_status(self, ticket_id: str) -> Optional[SLAStatus]:
        """Return the current in-memory SLAStatus snapshot, or None if not initialized."""
        return self._states.get(ticket_id)

    # ── Private helpers ───────────────────────────────────────────────────────

    def _get_state(self, ticket_id: str) -> SLAStatus:
        status = self._states.get(ticket_id)
        if status is None:
            raise ValueError(
                f"SLA state for ticket {ticket_id!r} not initialized. "
                "Call initialize() first."
            )
        return status
