"""Unit tests for channel adapter payload normalization (no HTTP, no DB)."""

from datetime import datetime, timezone

import pytest

from app.adapters.jira_adapter import normalize_jira_payload
from app.adapters.slack_adapter import normalize_slack_payload
from app.adapters.whatsapp_adapter import normalize_whatsapp_payload
from app.schemas.events import (
    Channel,
    JiraWebhookPayload,
    SlackWebhookPayload,
    WhatsAppWebhookPayload,
)

NOW = datetime.now(timezone.utc)
TENANT = "acme-corp"
CONTACT = "bob.smith"


# ── JIRA normalization ────────────────────────────────────────────────────────

class TestJiraNormalization:
    def _payload(self, **overrides) -> JiraWebhookPayload:
        base = dict(
            event_id="jira-unit-001",
            timestamp=NOW,
            issue_key="SUP-001",
            summary="API Gateway 502 errors",
            description="We see intermittent 502s on api-gateway.",
            reporter_email="bob.smith@acme-corp.example",
            priority="High",
            components=["api-gateway"],
        )
        base.update(overrides)
        return JiraWebhookPayload(**base)

    def test_channel_is_jira(self):
        event = normalize_jira_payload(
            self._payload(), tenant_id=TENANT, contact_id=CONTACT,
            injection_flagged=False, sanitized_body="description text",
        )
        assert event.channel == Channel.JIRA

    def test_summary_maps_to_subject(self):
        payload = self._payload(summary="Critical DB failure")
        event = normalize_jira_payload(
            payload, tenant_id=TENANT, contact_id=CONTACT,
            injection_flagged=False, sanitized_body=payload.description,
        )
        assert event.subject == "Critical DB failure"

    def test_reporter_email_maps_to_external_id(self):
        payload = self._payload()
        event = normalize_jira_payload(
            payload, tenant_id=TENANT, contact_id=CONTACT,
            injection_flagged=False, sanitized_body=payload.description,
        )
        assert event.external_id == "bob.smith@acme-corp.example"

    def test_tenant_and_contact_ids_set(self):
        event = normalize_jira_payload(
            self._payload(), tenant_id=TENANT, contact_id=CONTACT,
            injection_flagged=False, sanitized_body="body",
        )
        assert event.tenant_id == TENANT
        assert event.contact_id == CONTACT

    def test_raw_payload_preserved(self):
        payload = self._payload()
        event = normalize_jira_payload(
            payload, tenant_id=TENANT, contact_id=CONTACT,
            injection_flagged=False, sanitized_body=payload.description,
        )
        assert event.raw_payload["issue_key"] == "SUP-001"
        assert event.raw_payload["reporter_email"] == "bob.smith@acme-corp.example"

    def test_injection_flag_propagated(self):
        event = normalize_jira_payload(
            self._payload(), tenant_id=TENANT, contact_id=CONTACT,
            injection_flagged=True,
            sanitized_body="[MESSAGE WITHHELD — potential prompt injection pattern detected]",
        )
        assert event.injection_flagged is True

    def test_sanitized_body_used_not_original(self):
        event = normalize_jira_payload(
            self._payload(), tenant_id=TENANT, contact_id=CONTACT,
            injection_flagged=True, sanitized_body="SAFE",
        )
        assert event.body == "SAFE"
        assert event.raw_payload["description"] == "We see intermittent 502s on api-gateway."


# ── Slack normalization ───────────────────────────────────────────────────────

class TestSlackNormalization:
    def _payload(self, text="Auth failures since 10am") -> SlackWebhookPayload:
        return SlackWebhookPayload(
            event_id="slack-unit-001",
            timestamp=NOW,
            user_id="U0ACM001",
            channel_id="C01SUPPORT",
            text=text,
        )

    def test_channel_is_slack(self):
        event = normalize_slack_payload(
            self._payload(), tenant_id=TENANT, contact_id="alice.chen",
            injection_flagged=False, sanitized_body="Auth failures since 10am",
        )
        assert event.channel == Channel.SLACK

    def test_user_id_maps_to_external_id(self):
        event = normalize_slack_payload(
            self._payload(), tenant_id=TENANT, contact_id="alice.chen",
            injection_flagged=False, sanitized_body="Auth failures since 10am",
        )
        assert event.external_id == "U0ACM001"

    def test_short_text_used_as_subject(self):
        event = normalize_slack_payload(
            self._payload(text="Short message"), tenant_id=TENANT, contact_id="alice.chen",
            injection_flagged=False, sanitized_body="Short message",
        )
        assert event.subject == "Short message"

    def test_long_text_truncated_in_subject(self):
        long_text = "x" * 200
        event = normalize_slack_payload(
            self._payload(text=long_text), tenant_id=TENANT, contact_id="alice.chen",
            injection_flagged=False, sanitized_body=long_text,
        )
        assert len(event.subject) <= 121   # 120 chars + ellipsis character
        assert event.subject.endswith("…")

    def test_body_is_full_text(self):
        long_text = "y" * 200
        event = normalize_slack_payload(
            self._payload(text=long_text), tenant_id=TENANT, contact_id="alice.chen",
            injection_flagged=False, sanitized_body=long_text,
        )
        assert event.body == long_text

    def test_raw_payload_contains_user_id(self):
        event = normalize_slack_payload(
            self._payload(), tenant_id=TENANT, contact_id="alice.chen",
            injection_flagged=False, sanitized_body="Auth failures since 10am",
        )
        assert event.raw_payload["user_id"] == "U0ACM001"


# ── WhatsApp normalization ────────────────────────────────────────────────────

class TestWhatsAppNormalization:
    def _payload(self, body="Buckets inaccessible") -> WhatsAppWebhookPayload:
        return WhatsAppWebhookPayload(
            event_id="wa-unit-001",
            timestamp=NOW,
            from_number="+15550100001",
            message_id="wamid.001",
            body=body,
        )

    def test_channel_is_whatsapp(self):
        event = normalize_whatsapp_payload(
            self._payload(), tenant_id=TENANT, contact_id="carol.jones",
            injection_flagged=False, sanitized_body="Buckets inaccessible",
        )
        assert event.channel == Channel.WHATSAPP

    def test_from_number_maps_to_external_id(self):
        event = normalize_whatsapp_payload(
            self._payload(), tenant_id=TENANT, contact_id="carol.jones",
            injection_flagged=False, sanitized_body="Buckets inaccessible",
        )
        assert event.external_id == "+15550100001"

    def test_body_used_as_subject_when_short(self):
        event = normalize_whatsapp_payload(
            self._payload(body="Short"), tenant_id=TENANT, contact_id="carol.jones",
            injection_flagged=False, sanitized_body="Short",
        )
        assert event.subject == "Short"

    def test_raw_payload_contains_message_id(self):
        event = normalize_whatsapp_payload(
            self._payload(), tenant_id=TENANT, contact_id="carol.jones",
            injection_flagged=False, sanitized_body="Buckets inaccessible",
        )
        assert event.raw_payload["message_id"] == "wamid.001"
