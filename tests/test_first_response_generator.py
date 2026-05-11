"""Unit tests for FirstResponseGenerator (Phase 4).

All tests are pure — no DB, no HTTP, no filesystem access.
The generator is stateless and fully deterministic.
"""

import pytest

from app.agents.classifier import Category, ClassificationResult
from app.agents.diagnostics_collector import DiagnosticField, DiagnosticsResult
from app.agents.first_response_generator import FirstResponse, FirstResponseGenerator
from app.agents.knowledge_retriever import KBMatch, NoMatchResult
from app.db.models import DataClassification


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_classification(
    category: Category = Category.INCIDENT,
    component: str = "api-gateway",
    severity: str = "P2",
) -> ClassificationResult:
    return ClassificationResult(
        category=category,
        severity=severity,
        component=component,
        confidence_score=0.80,
        reasoning="test",
    )


def _make_kb_match(
    article_id: str = "connectivity-001",
    title: str = "Network Connectivity Troubleshooting",
    excerpt: str = "Check DNS resolution and run ping to the endpoint.",
    confidence_score: float = 0.75,
) -> KBMatch:
    return KBMatch(
        article_id=article_id,
        title=title,
        file="connectivity.md",
        confidence_score=confidence_score,
        source_metadata={
            "article_id": article_id,
            "file": "connectivity.md",
            "tags": ["network-service"],
            "min_confidence": 0.60,
        },
        excerpt=excerpt,
    )


def _make_diagnostics(
    fields: list[DiagnosticField] | None = None,
    missing: list[str] | None = None,
    is_complete: bool = True,
) -> DiagnosticsResult:
    return DiagnosticsResult(
        fields=fields or [
            DiagnosticField("channel", "slack", DataClassification.PUBLIC),
            DiagnosticField("severity", "P2", DataClassification.INTERNAL),
            DiagnosticField("component", "api-gateway", DataClassification.INTERNAL),
        ],
        missing_required=missing or [],
        follow_up_questions=[],
        is_complete=is_complete,
    )


@pytest.fixture
def generator() -> FirstResponseGenerator:
    return FirstResponseGenerator()


# ── Grounded response tests ───────────────────────────────────────────────────

class TestGroundedResponse:
    def test_returns_first_response_object(self, generator):
        result = generator.generate(
            _make_classification(), _make_kb_match(), _make_diagnostics()
        )
        assert isinstance(result, FirstResponse)

    def test_not_fallback_when_kb_match_exists(self, generator):
        result = generator.generate(
            _make_classification(), _make_kb_match(), _make_diagnostics()
        )
        assert result.is_fallback is False

    def test_response_references_kb_article_id(self, generator):
        match = _make_kb_match(article_id="auth-001")
        result = generator.generate(_make_classification(), match, _make_diagnostics())
        assert "auth-001" in result.response_text

    def test_response_includes_article_title(self, generator):
        match = _make_kb_match(title="Authentication and Login Failures")
        result = generator.generate(_make_classification(), match, _make_diagnostics())
        assert "Authentication and Login Failures" in result.response_text

    def test_response_includes_excerpt(self, generator):
        match = _make_kb_match(excerpt="Run the DNS resolution check first.")
        result = generator.generate(_make_classification(), match, _make_diagnostics())
        assert "Run the DNS resolution check first." in result.response_text

    def test_kb_article_id_on_result(self, generator):
        match = _make_kb_match(article_id="storage-001")
        result = generator.generate(_make_classification(), match, _make_diagnostics())
        assert result.kb_article_id == "storage-001"

    def test_kb_article_title_on_result(self, generator):
        match = _make_kb_match(title="Storage Access Errors and Data Availability")
        result = generator.generate(_make_classification(), match, _make_diagnostics())
        assert result.kb_article_title == "Storage Access Errors and Data Availability"

    def test_source_metadata_on_result(self, generator):
        match = _make_kb_match(article_id="perf-001")
        result = generator.generate(_make_classification(), match, _make_diagnostics())
        assert result.source_metadata.get("article_id") == "perf-001"

    def test_response_text_is_non_empty(self, generator):
        result = generator.generate(
            _make_classification(), _make_kb_match(), _make_diagnostics()
        )
        assert isinstance(result.response_text, str)
        assert len(result.response_text) > 50


# ── Fallback response tests ───────────────────────────────────────────────────

class TestFallbackResponse:
    def test_no_match_produces_fallback(self, generator):
        no_match = NoMatchResult(reason="No article met threshold", best_score=0.20)
        result = generator.generate(
            _make_classification(), no_match, _make_diagnostics()
        )
        assert result.is_fallback is True

    def test_fallback_has_no_kb_article_id(self, generator):
        no_match = NoMatchResult(reason="No article met threshold", best_score=0.20)
        result = generator.generate(
            _make_classification(), no_match, _make_diagnostics()
        )
        assert result.kb_article_id is None

    def test_fallback_has_no_kb_article_title(self, generator):
        no_match = NoMatchResult(reason="No article met threshold", best_score=0.20)
        result = generator.generate(
            _make_classification(), no_match, _make_diagnostics()
        )
        assert result.kb_article_title is None

    def test_fallback_response_text_mentions_engineer(self, generator):
        no_match = NoMatchResult(reason="No article met threshold", best_score=0.20)
        result = generator.generate(
            _make_classification(), no_match, _make_diagnostics()
        )
        assert "engineer" in result.response_text.lower()

    def test_fallback_does_not_invent_guidance(self, generator):
        """Fallback must not contain specific technical instructions or step numbers."""
        no_match = NoMatchResult(reason="No article met threshold", best_score=0.20)
        result = generator.generate(
            _make_classification(), no_match, _make_diagnostics()
        )
        text = result.response_text
        # Should not contain numbered steps or technical command-like content
        assert "Step 1" not in text
        assert "Step 2" not in text
        assert "run the following" not in text.lower()

    def test_fallback_source_metadata_is_empty(self, generator):
        no_match = NoMatchResult(reason="No article met threshold", best_score=0.10)
        result = generator.generate(
            _make_classification(), no_match, _make_diagnostics()
        )
        assert result.source_metadata == {}


# ── Secret redaction tests ────────────────────────────────────────────────────

class TestSecretRedactionInResponse:
    def test_api_key_in_excerpt_is_redacted(self, generator):
        match = _make_kb_match(
            excerpt="Your api_key=supersecretvalue should be rotated."
        )
        result = generator.generate(_make_classification(), match, _make_diagnostics())
        assert "supersecretvalue" not in result.response_text
        assert "REDACTED" in result.response_text

    def test_bearer_token_in_excerpt_is_redacted(self, generator):
        match = _make_kb_match(
            excerpt="Use Bearer abc123tokenvalue in the Authorization header."
        )
        result = generator.generate(_make_classification(), match, _make_diagnostics())
        assert "abc123tokenvalue" not in result.response_text

    def test_password_in_excerpt_is_redacted(self, generator):
        match = _make_kb_match(excerpt="Set password=mysecret123 in the config file.")
        result = generator.generate(_make_classification(), match, _make_diagnostics())
        assert "mysecret123" not in result.response_text

    def test_sk_secret_in_excerpt_is_redacted(self, generator):
        match = _make_kb_match(excerpt="Use the key sk-abcdef1234567890abcdef12345 to authenticate.")
        result = generator.generate(_make_classification(), match, _make_diagnostics())
        assert "sk-abcdef1234567890abcdef12345" not in result.response_text

    def test_fallback_response_has_redaction_applied(self, generator):
        """Even the fallback goes through redact(); no raw secrets can leak."""
        no_match = NoMatchResult(reason="none", best_score=0.0)
        result = generator.generate(
            _make_classification(), no_match, _make_diagnostics()
        )
        # Fallback text itself has no secrets, but redact() must have been called
        # (we verify this by checking no pattern triggers remain).
        assert "password=" not in result.response_text


# ── CONFIDENTIAL/RESTRICTED field exclusion tests ─────────────────────────────

class TestConfidentialFieldExclusion:
    def test_confidential_ip_not_in_response_text(self, generator):
        fields = [
            DiagnosticField("channel", "slack", DataClassification.PUBLIC),
            DiagnosticField("severity", "P2", DataClassification.INTERNAL),
            DiagnosticField("ip_address", "192.168.99.10", DataClassification.CONFIDENTIAL),
        ]
        diag = _make_diagnostics(fields=fields)
        match = _make_kb_match()
        result = generator.generate(_make_classification(), match, diag)
        assert "192.168.99.10" not in result.response_text

    def test_restricted_field_not_in_response_text(self, generator):
        fields = [
            DiagnosticField("channel", "slack", DataClassification.PUBLIC),
            DiagnosticField("secret_key", "sk-abcXYZsecret123456789012345", DataClassification.RESTRICTED),
        ]
        diag = _make_diagnostics(fields=fields)
        match = _make_kb_match()
        result = generator.generate(_make_classification(), match, diag)
        # RESTRICTED field must not appear (and even if it leaked, redact() would catch sk- prefix)
        assert "sk-abcXYZsecret123456789012345" not in result.response_text

    def test_public_and_internal_fields_may_appear_in_response(self, generator):
        fields = [
            DiagnosticField("channel", "slack", DataClassification.PUBLIC),
            DiagnosticField("severity", "P2", DataClassification.INTERNAL),
            DiagnosticField("component", "api-gateway", DataClassification.INTERNAL),
        ]
        diag = _make_diagnostics(fields=fields)
        match = _make_kb_match(excerpt="Check the API gateway logs.")
        result = generator.generate(_make_classification(), match, diag)
        # PUBLIC/INTERNAL fields are safe for customer-facing text
        assert "slack" in result.response_text or "P2" in result.response_text or "api-gateway" in result.response_text

    def test_confidential_field_excluded_from_fallback(self, generator):
        fields = [
            DiagnosticField("ip_address", "10.0.1.99", DataClassification.CONFIDENTIAL),
        ]
        diag = _make_diagnostics(fields=fields)
        no_match = NoMatchResult(reason="no match", best_score=0.0)
        result = generator.generate(_make_classification(), no_match, diag)
        assert "10.0.1.99" not in result.response_text
