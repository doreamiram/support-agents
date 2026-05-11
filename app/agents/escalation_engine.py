from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

from app.config.models import AppConfig, EscalationChain
from app.db.repositories.audit_repository import AuditRepository
from app.utils.clock import ClockProvider


@dataclass
class EscalationAction:
    """One simulated contact step in the escalation chain."""

    step: int
    contact_name: str
    contact_method: str       # "slack" | "email" | "pagerduty" | "phone"
    contact_address: str
    delay_minutes: int        # minutes after breach time this step fires
    reason: str               # why escalation was triggered
    would_fire_at: datetime   # breach_time + delay_minutes
    simulated: bool = True    # always True in this prototype


@dataclass
class EscalationResult:
    """Result returned by EscalationEngine.escalate()."""

    ticket_id: str
    tenant_id: str
    severity: str
    component: str
    triggered_at: datetime
    actions: list[EscalationAction] = field(default_factory=list)
    chain_found: bool = False
    component_specific: bool = False   # True if component chain was preferred over wildcard


class EscalationEngine:
    """
    Configurable escalation engine.

    Lookup order for chains: component-specific first, then wildcard component="*".
    No real notifications are sent — returns simulated EscalationAction objects
    showing who would be contacted, when, why, and via which channel.
    Escalation events are recorded in the audit trail.
    """

    def __init__(
        self,
        config: AppConfig,
        clock: ClockProvider,
        audit_repo: AuditRepository,
    ) -> None:
        self._config = config
        self._clock = clock
        self._audit_repo = audit_repo

    def escalate(
        self,
        *,
        ticket_id: str,
        tenant_id: str,
        severity: str,
        component: str,
        reason: str,
    ) -> EscalationResult:
        """
        Find the escalation chain for (tenant_id, severity, component),
        build simulated contact actions, record an audit event, and return
        the EscalationResult. No real notifications are sent.
        """
        now = self._clock.now()
        chain, component_specific = self._find_chain(tenant_id, severity, component)

        if chain is None:
            result = EscalationResult(
                ticket_id=ticket_id,
                tenant_id=tenant_id,
                severity=severity,
                component=component,
                triggered_at=now,
                actions=[],
                chain_found=False,
                component_specific=False,
            )
        else:
            actions = [
                EscalationAction(
                    step=i,
                    contact_name=c.name,
                    contact_method=c.method,
                    contact_address=c.address,
                    delay_minutes=c.delay_minutes,
                    reason=reason,
                    would_fire_at=now + timedelta(minutes=c.delay_minutes),
                    simulated=True,
                )
                for i, c in enumerate(chain.contacts)
            ]
            result = EscalationResult(
                ticket_id=ticket_id,
                tenant_id=tenant_id,
                severity=severity,
                component=component,
                triggered_at=now,
                actions=actions,
                chain_found=True,
                component_specific=component_specific,
            )

        self._audit_repo.append(
            tenant_id=tenant_id,
            event_type="escalation_triggered",
            actor="escalation_engine",
            payload={
                "ticket_id": ticket_id,
                "severity": severity,
                "component": component,
                "reason": reason,
                "chain_found": result.chain_found,
                "component_specific": result.component_specific,
                "action_count": len(result.actions),
                "simulated": True,
            },
        )

        return result

    # ── Private helpers ───────────────────────────────────────────────────────

    def _find_chain(
        self,
        tenant_id: str,
        severity: str,
        component: str,
    ) -> tuple[Optional[EscalationChain], bool]:
        """
        Return (chain, is_component_specific).
        Prefers a component-specific chain (component != "*") over a wildcard.
        Returns (None, False) when no chain is configured.
        """
        chains = self._config.escalation_chains.escalation_chains

        # First pass: component-specific chain.
        for chain in chains:
            if (
                chain.tenant_id == tenant_id
                and chain.severity == severity
                and chain.component == component
                and chain.component != "*"
            ):
                return chain, True

        # Second pass: wildcard component fallback.
        for chain in chains:
            if (
                chain.tenant_id == tenant_id
                and chain.severity == severity
                and chain.component == "*"
            ):
                return chain, False

        return None, False
