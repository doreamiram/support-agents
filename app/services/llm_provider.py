"""
Abstraction for a future managed text-generation backend.

The prototype ships a deterministic mock implementation only: no remote calls,
no third-party client libraries, and no environment-based credentials.
"""

from __future__ import annotations

import hashlib
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable, Mapping, Optional, Union

from app.agents.diagnostics_collector import DiagnosticField, DiagnosticsResult
from app.db.models import DataClassification

_SAFE_CLASSIFICATIONS: frozenset[DataClassification] = frozenset(
    {DataClassification.PUBLIC, DataClassification.INTERNAL}
)

_FORBIDDEN_CONTEXT_KEYS: frozenset[str] = frozenset(
    {
        "raw_payload",
        "api_key",
        "password",
        "token",
        "secret",
        "webhook_secret",
        "authorization",
    }
)


class LLMTaskType(str, Enum):
    classify_intent = "classify_intent"
    draft_first_response = "draft_first_response"
    summarize_handoff = "summarize_handoff"
    generate_follow_up_question = "generate_follow_up_question"


class LLMUnsupportedTaskError(ValueError):
    """Raised when a task label does not map to a supported LLMTaskType."""


def _normalize_task(task: Union[LLMTaskType, str]) -> LLMTaskType:
    if isinstance(task, LLMTaskType):
        return task
    if not isinstance(task, str):
        raise LLMUnsupportedTaskError(
            "Task must be LLMTaskType or str, not " + type(task).__name__ + "."
        )
    key = task.strip()
    if not key:
        raise LLMUnsupportedTaskError(
            "Empty task string is not supported. Supported tasks: "
            + ", ".join(sorted(t.value for t in LLMTaskType))
        )
    try:
        return LLMTaskType(key)
    except ValueError:
        supported = ", ".join(sorted(t.value for t in LLMTaskType))
        raise LLMUnsupportedTaskError(
            "Unsupported task " + repr(task) + ". Supported tasks: " + supported
        ) from None


@dataclass(frozen=True)
class LLMRequest:
    """Minimal structured input for one generation step."""

    task: Union[LLMTaskType, str]
    tenant_id: Optional[str] = None
    safe_context: Mapping[str, str] = field(default_factory=dict)
    category: Optional[str] = None
    severity: Optional[str] = None
    component: Optional[str] = None
    kb_article_id: Optional[str] = None

    def __post_init__(self) -> None:
        normalized = _normalize_task(self.task)
        object.__setattr__(self, "task", normalized)
        object.__setattr__(self, "safe_context", dict(self.safe_context))


@dataclass(frozen=True)
class LLMResponse:
    """Model output plus grounding metadata."""

    text: str
    source_metadata: dict[str, str] = field(default_factory=dict)


class LLMProvider(ABC):
    """Contract for swapping the mock with a production-backed implementation."""

    @abstractmethod
    def complete(self, request: LLMRequest) -> LLMResponse:
        """Run one generation step for the given request."""


def safe_diagnostic_fields_for_llm(
    fields: Iterable[DiagnosticField],
) -> dict[str, str]:
    """Return only PUBLIC and INTERNAL diagnostic field values for model context."""
    out: dict[str, str] = {}
    for f in fields:
        if f.classification in _SAFE_CLASSIFICATIONS:
            out[f.name] = str(f.value)
    return out


def safe_diagnostic_fields_for_llm_from_result(
    diagnostics: DiagnosticsResult,
) -> dict[str, str]:
    """Project DiagnosticsResult to a safe field map for model context."""
    return safe_diagnostic_fields_for_llm(diagnostics.fields)


def merge_safe_context(
    base: Mapping[str, str],
    extra: Mapping[str, str],
) -> dict[str, str]:
    """Merge two string maps, dropping keys that must never reach a model context."""
    merged: dict[str, str] = {}
    for src in (base, extra):
        for k, v in src.items():
            lk = k.lower()
            if lk in _FORBIDDEN_CONTEXT_KEYS or k in _FORBIDDEN_CONTEXT_KEYS:
                continue
            merged[k] = v
    return merged


def _request_fingerprint(request: LLMRequest) -> str:
    payload = {
        "task": request.task.value,
        "tenant_id": request.tenant_id or "",
        "safe_context": dict(sorted(request.safe_context.items())),
        "category": request.category or "",
        "severity": request.severity or "",
        "component": request.component or "",
        "kb_article_id": request.kb_article_id or "",
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


class MockLLMProvider(LLMProvider):
    """Deterministic mock: identical request yields identical response."""

    def complete(self, request: LLMRequest) -> LLMResponse:
        fp = _request_fingerprint(request)
        meta: dict[str, str] = {
            "provider": "mock",
            "task": request.task.value,
            "determinism_fingerprint": fp,
            "grounded": "false",
        }
        if request.kb_article_id:
            meta["grounded"] = "true"
            meta["kb_article_id"] = request.kb_article_id

        if request.task is LLMTaskType.classify_intent:
            cat = request.category or "unknown"
            sev = request.severity or "unknown"
            text = (
                "[mock:classify_intent] fingerprint=" + fp
                + " category=" + cat
                + " severity=" + sev
            )
        elif request.task is LLMTaskType.draft_first_response:
            kb = request.kb_article_id or "none"
            text = "[mock:draft_first_response] fingerprint=" + fp + " kb_article_id=" + kb
        elif request.task is LLMTaskType.summarize_handoff:
            comp = request.component or "unknown"
            text = "[mock:summarize_handoff] fingerprint=" + fp + " component=" + comp
        elif request.task is LLMTaskType.generate_follow_up_question:
            missing = request.safe_context.get("missing_fields", "")
            text = (
                "[mock:generate_follow_up_question] fingerprint="
                + fp
                + " missing="
                + missing
            )
        else:
            raise LLMUnsupportedTaskError("Unhandled task in mock: " + repr(request.task))

        return LLMResponse(text=text, source_metadata=meta)
