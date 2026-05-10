"""Tests for the config loader and all Pydantic config models."""

import pytest
from pydantic import ValidationError

from app.config.loader import ConfigLoadError, load_config
from app.config.models import (
    Contact,
    EscalationChain,
    EscalationContact,
    KBArticle,
    QuietHoursRule,
    QuietWindow,
    SLARule,
    Tenant,
)


# ── Happy path ────────────────────────────────────────────────────────────────

class TestLoadConfig:
    def test_load_config_succeeds(self):
        config = load_config()
        assert config is not None

    def test_at_least_two_tenants_loaded(self):
        config = load_config()
        assert len(config.tenants.tenants) >= 2

    def test_all_four_sla_severities_present(self):
        config = load_config()
        severities = {rule.severity for rule in config.sla_rules.sla_rules}
        assert severities == {"P1", "P2", "P3", "P4"}

    def test_components_loaded(self):
        config = load_config()
        assert len(config.components.components) >= 1

    def test_escalation_chains_loaded(self):
        config = load_config()
        assert len(config.escalation_chains.escalation_chains) >= 1

    def test_quiet_hours_loaded(self):
        config = load_config()
        assert len(config.quiet_hours.quiet_hours) >= 1

    def test_knowledge_articles_loaded(self):
        config = load_config()
        assert len(config.knowledge_index.articles) >= 1

    def test_each_tenant_has_webhook_secret(self):
        config = load_config()
        for tenant in config.tenants.tenants:
            assert tenant.webhook_secret, f"Tenant {tenant.id!r} is missing webhook_secret"

    def test_config_load_error_on_missing_directory(self, tmp_path):
        empty_dir = tmp_path / "no-config"
        with pytest.raises(ConfigLoadError, match="not found"):
            load_config(config_dir=empty_dir)


# ── Tenant and Contact model validation ──────────────────────────────────────

class TestTenantModel:
    def test_tenant_missing_id_raises(self):
        with pytest.raises(ValidationError):
            Tenant(name="X", timezone="UTC", webhook_secret="s", contacts=[])

    def test_tenant_missing_name_raises(self):
        with pytest.raises(ValidationError):
            Tenant(id="t1", timezone="UTC", webhook_secret="s", contacts=[])

    def test_tenant_missing_timezone_raises(self):
        with pytest.raises(ValidationError):
            Tenant(id="t1", name="X", webhook_secret="s", contacts=[])

    def test_tenant_missing_webhook_secret_raises(self):
        with pytest.raises(ValidationError):
            Tenant(id="t1", name="X", timezone="UTC", contacts=[])

    def test_valid_tenant_accepts_empty_contacts(self):
        tenant = Tenant(id="t1", name="X", timezone="UTC", webhook_secret="s")
        assert tenant.contacts == []


class TestContactModel:
    def test_contact_missing_channel_raises(self):
        with pytest.raises(ValidationError):
            Contact(id="c1", name="Alice", external_id="U1", role="admin")

    def test_contact_missing_external_id_raises(self):
        with pytest.raises(ValidationError):
            Contact(id="c1", name="Alice", channel="slack", role="admin")

    def test_contact_invalid_channel_raises(self):
        with pytest.raises(ValidationError):
            Contact(id="c1", name="Alice", channel="telegram",
                    external_id="U1", role="admin")

    def test_valid_contact_without_email(self):
        contact = Contact(
            id="c1", name="Alice", channel="slack",
            external_id="U1", role="admin",
        )
        assert contact.email is None


# ── SLA Rule model validation ─────────────────────────────────────────────────

class TestSLARuleModel:
    def test_sla_rule_missing_severity_raises(self):
        with pytest.raises(ValidationError):
            SLARule(
                response_time_minutes=15,
                resolution_time_minutes=240,
                breach_action="escalate",
            )

    def test_sla_rule_invalid_severity_raises(self):
        with pytest.raises(ValidationError):
            SLARule(
                severity="P5",
                response_time_minutes=15,
                resolution_time_minutes=240,
                breach_action="escalate",
            )

    def test_sla_rule_zero_response_time_raises(self):
        with pytest.raises(ValidationError):
            SLARule(
                severity="P1",
                response_time_minutes=0,
                resolution_time_minutes=240,
                breach_action="escalate",
            )

    def test_sla_rule_invalid_breach_action_raises(self):
        with pytest.raises(ValidationError):
            SLARule(
                severity="P1",
                response_time_minutes=15,
                resolution_time_minutes=240,
                breach_action="ignore",
            )


# ── Escalation Chain model validation ────────────────────────────────────────

class TestEscalationChainModel:
    def test_escalation_chain_missing_tenant_id_raises(self):
        with pytest.raises(ValidationError):
            EscalationChain(severity="P1", component="*", contacts=[])

    def test_escalation_chain_missing_severity_raises(self):
        with pytest.raises(ValidationError):
            EscalationChain(tenant_id="acme-corp", component="*", contacts=[])

    def test_escalation_chain_missing_component_raises(self):
        with pytest.raises(ValidationError):
            EscalationChain(tenant_id="acme-corp", severity="P1", contacts=[])

    def test_escalation_chain_invalid_severity_raises(self):
        with pytest.raises(ValidationError):
            EscalationChain(
                tenant_id="acme-corp", severity="critical",
                component="*", contacts=[],
            )

    def test_escalation_contact_negative_delay_raises(self):
        with pytest.raises(ValidationError):
            EscalationContact(
                name="Eng", method="slack", address="@eng", delay_minutes=-1
            )

    def test_valid_escalation_chain_with_wildcard_component(self):
        chain = EscalationChain(
            tenant_id="acme-corp", severity="P1", component="*", contacts=[]
        )
        assert chain.component == "*"


# ── Quiet Hours model validation ──────────────────────────────────────────────

class TestQuietHoursModel:
    def test_critical_override_true_stored_correctly(self):
        rule = QuietHoursRule(
            tenant_id="acme-corp",
            cooldown_minutes=30,
            critical_override=True,
            windows=[],
        )
        assert rule.critical_override is True

    def test_critical_override_false_stored_correctly(self):
        rule = QuietHoursRule(
            tenant_id="vertex-systems",
            cooldown_minutes=0,
            critical_override=False,
            windows=[],
        )
        assert rule.critical_override is False

    def test_negative_cooldown_raises(self):
        with pytest.raises(ValidationError):
            QuietHoursRule(
                tenant_id="acme-corp",
                cooldown_minutes=-1,
                critical_override=True,
                windows=[],
            )

    def test_quiet_hours_missing_tenant_id_raises(self):
        with pytest.raises(ValidationError):
            QuietHoursRule(cooldown_minutes=30, critical_override=True, windows=[])

    def test_quiet_window_invalid_start_time_raises(self):
        with pytest.raises(ValidationError):
            QuietWindow(
                days=["monday"],
                start="25:00",
                end="08:00",
                timezone="America/New_York",
            )

    def test_quiet_window_invalid_end_time_raises(self):
        with pytest.raises(ValidationError):
            QuietWindow(
                days=["monday"],
                start="22:00",
                end="8pm",
                timezone="America/New_York",
            )

    def test_quiet_window_invalid_day_name_raises(self):
        with pytest.raises(ValidationError):
            QuietWindow(
                days=["funday"],
                start="22:00",
                end="08:00",
                timezone="America/New_York",
            )

    def test_quiet_window_days_normalised_to_lowercase(self):
        window = QuietWindow(
            days=["Monday", "FRIDAY"],
            start="22:00",
            end="08:00",
            timezone="UTC",
        )
        assert window.days == ["monday", "friday"]

    def test_quiet_hours_critical_override_loaded_for_all_tenants(self):
        config = load_config()
        for rule in config.quiet_hours.quiet_hours:
            assert isinstance(rule.critical_override, bool), (
                f"Tenant {rule.tenant_id!r}: critical_override must be bool"
            )


# ── Knowledge Index model validation ─────────────────────────────────────────

class TestKBArticleModel:
    def test_min_confidence_above_1_raises(self):
        with pytest.raises(ValidationError):
            KBArticle(
                id="x", title="X", file="x.md",
                tags=[], components=[], min_confidence=1.1,
            )

    def test_min_confidence_below_0_raises(self):
        with pytest.raises(ValidationError):
            KBArticle(
                id="x", title="X", file="x.md",
                tags=[], components=[], min_confidence=-0.1,
            )

    def test_valid_min_confidence_boundary_values(self):
        low = KBArticle(
            id="x", title="X", file="x.md",
            tags=[], components=[], min_confidence=0.0,
        )
        high = KBArticle(
            id="x", title="X", file="x.md",
            tags=[], components=[], min_confidence=1.0,
        )
        assert low.min_confidence == 0.0
        assert high.min_confidence == 1.0
