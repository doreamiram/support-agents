"""Unit tests for the identity resolver."""

import pytest

from app.config.loader import load_config
from app.services.identity_resolver import ContactNotVerifiedError, IdentityResolver

_resolver = IdentityResolver()


@pytest.fixture(scope="module")
def config():
    return load_config()


class TestIdentityResolver:
    def test_verified_slack_contact_resolved(self, config):
        tenant, contact = _resolver.resolve(
            channel="slack",
            external_id="U0ACM001",   # alice.chen in tenants.yaml
            config=config,
        )
        assert tenant.id == "acme-corp"
        assert contact.id == "alice.chen"
        assert contact.channel == "slack"

    def test_verified_jira_contact_resolved(self, config):
        tenant, contact = _resolver.resolve(
            channel="jira",
            external_id="bob.smith@acme-corp.example",
            config=config,
        )
        assert tenant.id == "acme-corp"
        assert contact.id == "bob.smith"

    def test_verified_whatsapp_contact_resolved(self, config):
        tenant, contact = _resolver.resolve(
            channel="whatsapp",
            external_id="+15550100001",   # carol.jones in tenants.yaml
            config=config,
        )
        assert tenant.id == "acme-corp"
        assert contact.id == "carol.jones"

    def test_vertex_tenant_contact_resolved(self, config):
        tenant, contact = _resolver.resolve(
            channel="slack",
            external_id="U0VTX001",   # dave.miller in tenants.yaml
            config=config,
        )
        assert tenant.id == "vertex-systems"
        assert contact.id == "dave.miller"

    def test_unknown_external_id_raises(self, config):
        with pytest.raises(ContactNotVerifiedError):
            _resolver.resolve(
                channel="slack",
                external_id="U_UNKNOWN_999",
                config=config,
            )

    def test_known_id_wrong_channel_raises(self, config):
        # alice.chen is slack only; trying via jira channel must fail
        with pytest.raises(ContactNotVerifiedError):
            _resolver.resolve(
                channel="jira",
                external_id="U0ACM001",
                config=config,
            )

    def test_error_includes_channel_and_external_id(self, config):
        with pytest.raises(ContactNotVerifiedError) as exc_info:
            _resolver.resolve(
                channel="whatsapp",
                external_id="+19990000000",
                config=config,
            )
        assert exc_info.value.channel == "whatsapp"
        assert exc_info.value.external_id == "+19990000000"

    def test_correct_tenant_returned_for_each_contact(self, config):
        # Ensure resolver doesn't cross-match contacts across tenants
        _, contact_a = _resolver.resolve(
            channel="slack", external_id="U0ACM001", config=config
        )
        _, contact_b = _resolver.resolve(
            channel="slack", external_id="U0VTX001", config=config
        )
        assert contact_a.id != contact_b.id
