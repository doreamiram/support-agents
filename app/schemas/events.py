from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class Channel(str, Enum):
    JIRA = "jira"
    SLACK = "slack"
    WHATSAPP = "whatsapp"


# ── Channel-specific raw payloads (simulated webhook bodies) ──────────────────

class JiraWebhookPayload(BaseModel):
    event_id: str
    timestamp: datetime
    issue_key: str
    issue_type: str = "Bug"
    summary: str
    description: str = ""
    reporter_email: str          # maps to contact external_id for JIRA channel
    priority: str = "Medium"
    components: list[str] = Field(default_factory=list)


class SlackWebhookPayload(BaseModel):
    event_id: str
    timestamp: datetime
    user_id: str                 # Slack user ID → contact external_id
    channel_id: str
    text: str
    thread_ts: Optional[str] = None


class WhatsAppWebhookPayload(BaseModel):
    event_id: str
    timestamp: datetime
    from_number: str             # E.164 phone number → contact external_id
    message_id: str
    body: str


# ── Canonical inbound event ───────────────────────────────────────────────────

class InboundEvent(BaseModel):
    event_id: str
    tenant_id: str
    contact_id: str
    channel: Channel
    external_id: str
    timestamp: datetime
    subject: str
    body: str                    # sanitized; may be replaced if injection detected
    raw_payload: dict[str, Any]  # original channel payload, kept for debugging
    injection_flagged: bool = False
    received_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


# ── Webhook response ──────────────────────────────────────────────────────────

class WebhookResponse(BaseModel):
    status: str                  # "accepted"
    event_id: str
    tenant_id: str
    contact_id: str
    channel: str
    injection_flagged: bool
