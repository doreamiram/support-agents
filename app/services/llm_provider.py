"""Safe LLM provider abstraction with deterministic default behavior."""

from __future__ import annotations

import hashlib
import json
import os
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
        "raw" + "_payload",
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
    demo_summary = "demo_summary"
    handoff_summary = "handoff_summary"
    customer_response_polish = "customer_response_polish"


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


@dataclass
class LLMProviderStatus:
    """Browser-safe provider state. Never store credentials or raw errors here."""

    configured: bool
    provider_mode: str
    real_llm_enabled: bool
    fallback_used: bool
    last_call_status: str
    error_type: Optional[str] = None

    def to_safe_dict(self) -> dict[str, object]:
        data: dict[str, object] = {
            "configured": self.configured,
            "provider_mode": self.provider_mode,
            "real_llm_enabled": self.real_llm_enabled,
            "fallback_used": self.fallback_used,
            "last_call_status": self.last_call_status,
        }
        if self.error_type:
            data["error_type"] = self.error_type
        return data


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
            "provider_mode": "mock",
            "task": request.task.value,
            "determinism_fingerprint": fp,
            "grounded": "false",
            "fallback_used": "false",
            "last_call_status": "success",
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
        elif request.task is LLMTaskType.demo_summary:
            titles = request.safe_context.get("scenario_titles", "demo scenarios")
            text = (
                "[mock:demo_summary] Demo executed safely for "
                + titles
                + " | fingerprint="
                + fp
            )
        elif request.task is LLMTaskType.handoff_summary:
            action = request.safe_context.get("action", "tier2")
            reason = request.safe_context.get("reason", "review_required")
            suggested = request.safe_context.get("suggested_next_action", "review deterministic handoff context")
            text = (
                "[mock:handoff_summary] "
                + action
                + " due to "
                + reason
                + ". Engineer should "
                + suggested
                + " | fingerprint="
                + fp
            )
        elif request.task is LLMTaskType.customer_response_polish:
            grounded = request.safe_context.get("deterministic_response", "")
            if grounded:
                text = grounded
            else:
                text = (
                    "No grounded response was available, "
                    "so no customer reply was generated."
                )
        else:
            raise LLMUnsupportedTaskError("Unhandled task in mock: " + repr(request.task))

        return LLMResponse(text=text, source_metadata=meta)


class FallbackLLMProvider(LLMProvider):
    """Wrap a provider so failures fall back to deterministic local output."""

    def __init__(
        self,
        primary: Optional[LLMProvider],
        fallback: MockLLMProvider,
        status: LLMProviderStatus,
    ) -> None:
        self.primary = primary
        self.fallback = fallback
        self.status = status

    def complete(self, request: LLMRequest) -> LLMResponse:
        if self.primary is None:
            response = self.fallback.complete(request)
            self.status.provider_mode = "fallback" if self.status.real_llm_enabled else "mock"
            self.status.fallback_used = self.status.real_llm_enabled
            self.status.last_call_status = "fallback" if self.status.real_llm_enabled else "skipped"
            return self._with_status_metadata(response)

        try:
            response = self.primary.complete(request)
        except Exception as exc:
            response = self.fallback.complete(request)
            self.status.provider_mode = "fallback"
            self.status.fallback_used = True
            self.status.last_call_status = "fallback"
            self.status.error_type = type(exc).__name__
            return self._with_status_metadata(response)

        self.status.provider_mode = "real"
        self.status.fallback_used = False
        self.status.last_call_status = "success"
        self.status.error_type = None
        return self._with_status_metadata(response)

    def _with_status_metadata(self, response: LLMResponse) -> LLMResponse:
        meta = dict(response.source_metadata)
        meta["provider_mode"] = self.status.provider_mode
        meta["real_llm_enabled"] = str(self.status.real_llm_enabled).lower()
        meta["fallback_used"] = str(self.status.fallback_used).lower()
        meta["last_call_status"] = self.status.last_call_status
        if self.status.error_type:
            meta["error_type"] = self.status.error_type
        return LLMResponse(text=response.text, source_metadata=meta)


@dataclass(frozen=True)
class LLMProviderSelection:
    provider: LLMProvider
    status: LLMProviderStatus


def _env_truthy(value: Optional[str]) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def select_llm_provider(env: Optional[Mapping[str, str]] = None) -> LLMProviderSelection:
    """Select a provider from environment-style config without exposing secrets."""
    settings = env if env is not None else os.environ
    real_enabled = _env_truthy(settings.get("USE_REAL_LLM", "false"))
    fallback = MockLLMProvider()

    if not real_enabled:
        status = LLMProviderStatus(
            configured=False,
            provider_mode="mock",
            real_llm_enabled=False,
            fallback_used=False,
            last_call_status="skipped",
        )
        return LLMProviderSelection(
            provider=FallbackLLMProvider(None, fallback, status),
            status=status,
        )

    required = ("LLM_API_BASE_URL", "LLM_API_KEY", "LLM_MODEL")
    missing = [name for name in required if not settings.get(name)]
    if missing:
        status = LLMProviderStatus(
            configured=False,
            provider_mode="fallback",
            real_llm_enabled=True,
            fallback_used=True,
            last_call_status="fallback",
            error_type="MissingConfig",
        )
        return LLMProviderSelection(
            provider=FallbackLLMProvider(None, fallback, status),
            status=status,
        )

    try:
        from app.services.real_llm_provider import RealLLMProvider

        primary = RealLLMProvider.from_env(settings)
    except Exception as exc:
        status = LLMProviderStatus(
            configured=False,
            provider_mode="fallback",
            real_llm_enabled=True,
            fallback_used=True,
            last_call_status="fallback",
            error_type=type(exc).__name__,
        )
        return LLMProviderSelection(
            provider=FallbackLLMProvider(None, fallback, status),
            status=status,
        )

    status = LLMProviderStatus(
        configured=True,
        provider_mode="real",
        real_llm_enabled=True,
        fallback_used=False,
        last_call_status="skipped",
    )
    return LLMProviderSelection(
        provider=FallbackLLMProvider(primary, fallback, status),
        status=status,
    )
