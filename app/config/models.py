import re
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

_TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
_VALID_DAYS = {
    "monday", "tuesday", "wednesday", "thursday",
    "friday", "saturday", "sunday",
}


# ── Tenants ───────────────────────────────────────────────────────────────────

class Contact(BaseModel):
    id: str
    name: str
    channel: Literal["slack", "jira", "whatsapp", "email"]
    external_id: str
    role: str
    email: Optional[str] = None


class Tenant(BaseModel):
    id: str
    name: str
    timezone: str
    webhook_secret: str
    contacts: list[Contact] = Field(default_factory=list)


class TenantsConfig(BaseModel):
    tenants: list[Tenant] = Field(min_length=1)


# ── Components ────────────────────────────────────────────────────────────────

class Component(BaseModel):
    id: str
    name: str
    description: Optional[str] = None


class ComponentsConfig(BaseModel):
    components: list[Component] = Field(min_length=1)


# ── SLA Rules ─────────────────────────────────────────────────────────────────

class SLARule(BaseModel):
    severity: Literal["P1", "P2", "P3", "P4"]
    response_time_minutes: int = Field(gt=0)
    resolution_time_minutes: int = Field(gt=0)
    breach_action: Literal["escalate", "notify", "log"]


class SLARulesConfig(BaseModel):
    sla_rules: list[SLARule] = Field(min_length=1)


# ── Escalation Chains ─────────────────────────────────────────────────────────

class EscalationContact(BaseModel):
    name: str
    method: Literal["slack", "email", "pagerduty", "phone"]
    address: str
    delay_minutes: int = Field(default=0, ge=0)


class EscalationChain(BaseModel):
    tenant_id: str
    severity: Literal["P1", "P2", "P3", "P4"]
    component: str                    # component id or "*" for all components
    contacts: list[EscalationContact] = Field(default_factory=list)


class EscalationChainsConfig(BaseModel):
    escalation_chains: list[EscalationChain] = Field(min_length=1)


# ── Quiet Hours ───────────────────────────────────────────────────────────────

class QuietWindow(BaseModel):
    days: list[str] = Field(min_length=1)
    start: str
    end: str
    timezone: str

    @field_validator("start", "end")
    @classmethod
    def _validate_time(cls, v: str) -> str:
        if not _TIME_RE.match(v):
            raise ValueError(
                f"Time must be in HH:MM (24-hour) format, got: {v!r}"
            )
        return v

    @field_validator("days")
    @classmethod
    def _validate_days(cls, v: list[str]) -> list[str]:
        normalised = [d.strip().lower() for d in v]
        invalid = [d for d in normalised if d not in _VALID_DAYS]
        if invalid:
            raise ValueError(f"Invalid day name(s): {invalid}")
        return normalised


class QuietHoursRule(BaseModel):
    tenant_id: str
    cooldown_minutes: int = Field(ge=0)
    critical_override: bool
    windows: list[QuietWindow] = Field(default_factory=list)


class QuietHoursConfig(BaseModel):
    quiet_hours: list[QuietHoursRule] = Field(min_length=1)


# ── Knowledge Index ───────────────────────────────────────────────────────────

class KBArticle(BaseModel):
    id: str
    title: str
    file: str
    tags: list[str] = Field(default_factory=list)
    components: list[str] = Field(default_factory=list)
    min_confidence: float = Field(ge=0.0, le=1.0)


class KnowledgeIndexConfig(BaseModel):
    articles: list[KBArticle] = Field(min_length=1)


# ── Composite root ────────────────────────────────────────────────────────────

class AppConfig(BaseModel):
    tenants: TenantsConfig
    components: ComponentsConfig
    sla_rules: SLARulesConfig
    escalation_chains: EscalationChainsConfig
    quiet_hours: QuietHoursConfig
    knowledge_index: KnowledgeIndexConfig
