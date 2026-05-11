from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from app.agents.classifier import Category, ClassificationResult
from app.db.models import DataClassification
from app.schemas.events import InboundEvent

# ── Required fields per (category, component) ────────────────────────────────
# Only incident events have required diagnostic fields.
# Fields listed here must either be directly extractable by _EXTRACTION_PATTERNS
# or covered by a satisfaction alias (e.g. http_error_code satisfies error_code).

_REQUIRED_FIELDS: dict[tuple[str, str], list[str]] = {
    ("incident", "api-gateway"):      ["http_error_code", "affected_endpoint"],
    ("incident", "auth-service"):     ["error_code", "auth_method"],
    ("incident", "compute-engine"):   ["cpu_usage_percent", "affected_instance"],
    ("incident", "storage-service"):  ["bucket_name", "operation_type"],
    ("incident", "network-service"):  ["ip_address"],
    ("incident", "billing-service"):  ["account_id", "billing_period"],
    ("incident", "unknown"):          ["error_description"],
}

# Follow-up questions generated for each missing required field.
_FOLLOW_UP_QUESTIONS: dict[str, str] = {
    "http_error_code": (
        "What HTTP status code are you seeing in the error response "
        "(e.g. 500, 503, 404)?"
    ),
    "affected_endpoint": (
        "Which API endpoint or URL is returning the error? "
        "Please share the full path (without credentials)."
    ),
    "error_code": (
        "What error code or message is displayed? "
        "Please copy the exact text from the error response."
    ),
    "auth_method": (
        "What authentication method are you using "
        "(OAuth 2.0, API key, SSO/SAML, JWT, etc.)?"
    ),
    "cpu_usage_percent": (
        "What is the current CPU utilization percentage on the affected instance? "
        "You can check with: `top -bn1 | head -5` or `vmstat 1 3`."
    ),
    "affected_instance": (
        "What is the instance ID or name of the affected compute resource?"
    ),
    "error_description": (
        "Can you describe the error message or unexpected behaviour in detail? "
        "Please include any error codes or stack trace excerpts."
    ),
    "bucket_name": (
        "What is the name of the storage bucket or container you are accessing?"
    ),
    "operation_type": (
        "What storage operation were you attempting "
        "(upload, download, delete, list, stat)?"
    ),
    "ip_address": (
        "What is the source IP address or hostname of the affected system? "
        "You can find it with: `ip addr show` or `hostname -I`."
    ),
    "account_id": (
        "What is your Modelyo account ID? "
        "You can find it in the portal under Account Settings."
    ),
    "billing_period": (
        "Which billing period or invoice ID are you enquiring about "
        "(e.g. 2026-04 or INV-12345)?"
    ),
}

# Extraction patterns: (field_name, regex, DataClassification, group_index).
# group_index=0 means use the entire match; >0 means use that capture group.
_EXTRACTION_PATTERNS: list[tuple[str, str, DataClassification, int]] = [
    (
        "http_error_code",
        r"\b(4\d{2}|5\d{2})\b",
        DataClassification.INTERNAL,
        0,
    ),
    (
        "ip_address",
        r"\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\b",
        DataClassification.CONFIDENTIAL,
        1,
    ),
    (
        "bucket_name",
        r"(?i)bucket[/:\s]+([a-zA-Z0-9_\-\.]{3,63})",
        DataClassification.INTERNAL,
        1,
    ),
    (
        "cpu_usage_percent",
        r"(?i)cpu\b[^%]{0,30}(\d{1,3})\s*%",
        DataClassification.INTERNAL,
        1,
    ),
    (
        "memory_usage_percent",
        r"(?i)(?:memory|ram|mem)\b[^%]{0,30}(\d{1,3})\s*%",
        DataClassification.INTERNAL,
        1,
    ),
    (
        "auth_method",
        r"(?i)\b(oauth2?|api[_\s]?key|saml|sso|bearer\s+token|jwt|certificate|ldap)\b",
        DataClassification.INTERNAL,
        0,
    ),
    (
        "operation_type",
        r"(?i)\b(upload|download|delete|remove|list(?:ing)?|get|put|head|copy|move)\b",
        DataClassification.INTERNAL,
        0,
    ),
]

# Compiled extraction patterns (compiled once at import time).
_COMPILED_EXTRACTION: list[tuple[str, re.Pattern[str], DataClassification, int]] = [
    (name, re.compile(pattern), cls, group)
    for name, pattern, cls, group in _EXTRACTION_PATTERNS
]

# Fields whose presence satisfies another required field name.
_SATISFACTION_ALIASES: dict[str, str] = {
    "http_error_code": "error_code",  # a 4xx/5xx code is a valid error_code
}


# ── Public types ──────────────────────────────────────────────────────────────

@dataclass
class DiagnosticField:
    """One extracted diagnostic datum with its data classification tag."""
    name: str
    value: str
    classification: DataClassification


@dataclass
class DiagnosticsResult:
    """Output of the diagnostics collector for one inbound event."""
    fields: list[DiagnosticField] = field(default_factory=list)
    missing_required: list[str] = field(default_factory=list)
    follow_up_questions: list[str] = field(default_factory=list)
    is_complete: bool = True


# ── Collector ─────────────────────────────────────────────────────────────────

class DiagnosticsCollector:
    """
    Extracts structured diagnostic fields from an inbound event and identifies
    missing required information based on the classification result.

    This component NEVER executes commands against customer infrastructure.
    When required information is absent it generates follow-up questions that
    guide the customer to run diagnostic commands themselves.
    """

    def collect(
        self,
        event: InboundEvent,
        classification: ClassificationResult,
    ) -> DiagnosticsResult:
        extracted = self._extract_fields(event, classification)
        extracted_names = {f.name for f in extracted}

        missing, questions = self._identify_missing(
            extracted_names, classification
        )

        return DiagnosticsResult(
            fields=extracted,
            missing_required=missing,
            follow_up_questions=questions,
            is_complete=len(missing) == 0,
        )

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _extract_fields(
        self,
        event: InboundEvent,
        classification: ClassificationResult,
    ) -> list[DiagnosticField]:
        fields: list[DiagnosticField] = []

        # Always-present structural fields.
        fields.append(DiagnosticField(
            name="channel",
            value=event.channel.value,
            classification=DataClassification.PUBLIC,
        ))
        fields.append(DiagnosticField(
            name="severity",
            value=classification.severity,
            classification=DataClassification.INTERNAL,
        ))
        fields.append(DiagnosticField(
            name="component",
            value=classification.component,
            classification=DataClassification.INTERNAL,
        ))
        fields.append(DiagnosticField(
            name="subject",
            value=event.subject,
            classification=DataClassification.INTERNAL,
        ))
        body_snippet = event.body[:500] if len(event.body) > 500 else event.body
        fields.append(DiagnosticField(
            name="body_summary",
            value=body_snippet,
            classification=DataClassification.INTERNAL,
        ))

        # Pattern-extracted fields from the combined text.
        combined = f"{event.subject} {event.body}"
        seen_field_names: set[str] = set()
        for fname, pattern, cls, group in _COMPILED_EXTRACTION:
            if fname in seen_field_names:
                continue
            m = pattern.search(combined)
            if m:
                value = m.group(group) if group > 0 else m.group(0)
                fields.append(DiagnosticField(
                    name=fname, value=value, classification=cls
                ))
                seen_field_names.add(fname)

        return fields

    def _identify_missing(
        self,
        extracted_names: set[str],
        classification: ClassificationResult,
    ) -> tuple[list[str], list[str]]:
        category = classification.category.value
        component = classification.component

        required = (
            _REQUIRED_FIELDS.get((category, component))
            or _REQUIRED_FIELDS.get((category, "*"))
            or []
        )

        # Expand extracted names with satisfaction aliases.
        effective_extracted = set(extracted_names)
        for extracted_name, satisfied_name in _SATISFACTION_ALIASES.items():
            if extracted_name in effective_extracted:
                effective_extracted.add(satisfied_name)

        missing = [r for r in required if r not in effective_extracted]
        questions = [
            _FOLLOW_UP_QUESTIONS[m]
            for m in missing
            if m in _FOLLOW_UP_QUESTIONS
        ]

        return missing, questions
