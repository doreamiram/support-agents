from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from app.agents.classifier import ClassificationResult
from app.agents.diagnostics_collector import DiagnosticsResult
from app.agents.knowledge_retriever import KBMatch, KnowledgeRetrievalResult, NoMatchResult
from app.db.models import DataClassification
from app.utils.redaction import redact

# Classifications that are safe to include in customer-facing response text.
_CUSTOMER_SAFE_CLASSIFICATIONS: frozenset[DataClassification] = frozenset(
    {DataClassification.PUBLIC, DataClassification.INTERNAL}
)

_FALLBACK_RESPONSE = (
    "Thank you for contacting Modelyo support. We have received your report "
    "and our engineering team has been notified.\n\n"
    "We were unable to locate a matching knowledge base article for your specific "
    "issue at this time. A Modelyo engineer will review your case and follow up shortly."
)


# ── Public types ──────────────────────────────────────────────────────────────

@dataclass
class FirstResponse:
    """The generated first response for a customer interaction."""
    response_text: str
    kb_article_id: Optional[str]
    kb_article_title: Optional[str]
    is_fallback: bool
    source_metadata: dict = field(default_factory=dict)


# ── Generator ─────────────────────────────────────────────────────────────────

class FirstResponseGenerator:
    """
    Deterministic mock first-response generator.

    Rules:
    - When a confident KB match exists, the response is grounded in that article.
    - When no KB match exists, a safe fallback is returned (no invented guidance).
    - Secrets are redacted from all response text before returning.
    - CONFIDENTIAL and RESTRICTED diagnostic fields are excluded from response text.
    """

    def generate(
        self,
        classification: ClassificationResult,
        kb_result: KnowledgeRetrievalResult,
        diagnostics: DiagnosticsResult,
    ) -> FirstResponse:
        if isinstance(kb_result, NoMatchResult):
            return self._fallback_response()

        return self._grounded_response(classification, kb_result, diagnostics)

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _grounded_response(
        self,
        classification: ClassificationResult,
        kb_match: KBMatch,
        diagnostics: DiagnosticsResult,
    ) -> FirstResponse:
        safe_fields = self._safe_diagnostic_summary(diagnostics)
        context_line = f" regarding your {classification.component} issue" if classification.component != "unknown" else ""

        body_parts = [
            f"Thank you for contacting Modelyo support. We have received your report{context_line}.",
            "",
            f"Based on our knowledge base, we found relevant guidance in: "
            f'"{kb_match.title}" (ref: {kb_match.article_id}).',
            "",
        ]

        if kb_match.excerpt:
            body_parts += [
                "Relevant guidance:",
                "",
                kb_match.excerpt,
                "",
            ]

        if safe_fields:
            body_parts += [
                "Summary of information collected:",
                safe_fields,
                "",
            ]

        body_parts += [
            "Please review the guidance above. If the steps do not apply to your "
            "situation or the issue persists, our engineering team will follow up.",
            "",
            f"Source: {kb_match.article_id}",
        ]

        raw_text = "\n".join(body_parts)
        response_text = redact(raw_text)

        return FirstResponse(
            response_text=response_text,
            kb_article_id=kb_match.article_id,
            kb_article_title=kb_match.title,
            is_fallback=False,
            source_metadata=kb_match.source_metadata,
        )

    def _fallback_response(self) -> FirstResponse:
        return FirstResponse(
            response_text=redact(_FALLBACK_RESPONSE),
            kb_article_id=None,
            kb_article_title=None,
            is_fallback=True,
            source_metadata={},
        )

    def _safe_diagnostic_summary(self, diagnostics: DiagnosticsResult) -> str:
        """
        Build a customer-readable summary from ONLY PUBLIC and INTERNAL fields.
        CONFIDENTIAL and RESTRICTED fields are excluded.
        """
        safe_items = [
            f"- {f.name}: {f.value}"
            for f in diagnostics.fields
            if f.classification in _CUSTOMER_SAFE_CLASSIFICATIONS
        ]
        return "\n".join(safe_items)
