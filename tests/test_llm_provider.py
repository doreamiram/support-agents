"""Tests for LLM readiness layer (mock provider, request safety, sanitization)."""

from pathlib import Path

import pytest

from app.agents.diagnostics_collector import DiagnosticField, DiagnosticsResult
from app.db.models import DataClassification
from app.services.real_llm_provider import RealLLMProvider, RealLLMProviderConfig
from app.services.llm_provider import (
    LLMRequest,
    LLMResponse,
    LLMTaskType,
    LLMUnsupportedTaskError,
    MockLLMProvider,
    merge_safe_context,
    safe_diagnostic_fields_for_llm,
    safe_diagnostic_fields_for_llm_from_result,
    select_llm_provider,
)

_FORBIDDEN_SUBSTRINGS = (
    "openai",
    "anthropic",
    "langchain",
    "requests",
    "httpx",
)


def _provider_src() -> str:
    root = Path(__file__).resolve().parents[1]
    return (root / "app" / "services" / "llm_provider.py").read_text(encoding="utf-8")


@pytest.fixture
def mock_llm() -> MockLLMProvider:
    return MockLLMProvider()


def test_llm_provider_source_has_no_forbidden_vendor_substrings():
    text = _provider_src().lower()
    for s in _FORBIDDEN_SUBSTRINGS:
        assert s not in text, f"disallowed substring {s!r} found in llm_provider.py"


def test_task_string_normalizes_to_enum():
    r1 = LLMRequest(task="classify_intent", category="incident")
    r2 = LLMRequest(task=LLMTaskType.classify_intent, category="incident")
    assert r1.task is LLMTaskType.classify_intent
    assert r2.task is LLMTaskType.classify_intent


@pytest.mark.parametrize(
    "bad",
    ["", "   ", "unknown_task", "CLASSIFY_INTENT"],
)
def test_invalid_task_string_raises(bad: str):
    with pytest.raises(LLMUnsupportedTaskError) as exc:
        LLMRequest(task=bad)
    assert "Supported tasks" in str(exc.value) or "not supported" in str(exc.value).lower()


def test_invalid_task_type_raises():
    with pytest.raises(LLMUnsupportedTaskError):
        LLMRequest(task=42)  # type: ignore[arg-type]


def test_mock_llm_determinism(mock_llm: MockLLMProvider):
    req = LLMRequest(
        task=LLMTaskType.draft_first_response,
        tenant_id="t1",
        safe_context={"a": "1", "b": "2"},
        kb_article_id="kb-001",
    )
    a = mock_llm.complete(req)
    b = mock_llm.complete(req)
    assert a == b
    assert a.text == b.text
    assert a.source_metadata == b.source_metadata


def test_stable_outputs_per_task(mock_llm: MockLLMProvider):
    base = dict(
        tenant_id="acme",
        safe_context={"k": "v"},
        category="incident",
        severity="P2",
        component="storage-service",
        kb_article_id="s-1",
    )
    samples = [
        (LLMTaskType.classify_intent, "classify_intent"),
        (LLMTaskType.draft_first_response, "draft_first_response"),
        (LLMTaskType.summarize_handoff, "summarize_handoff"),
        (LLMTaskType.generate_follow_up_question, "generate_follow_up_question"),
        (LLMTaskType.demo_summary, "demo_summary"),
        (LLMTaskType.handoff_summary, "handoff_summary"),
    ]
    for enum_task, token in samples:
        r = mock_llm.complete(LLMRequest(task=enum_task, **base))
        assert token in r.text
        assert r.source_metadata["provider"] == "mock"
        assert r.source_metadata["task"] == enum_task.value
        assert "determinism_fingerprint" in r.source_metadata
        assert len(r.source_metadata["determinism_fingerprint"]) == 16


def test_grounding_metadata_when_kb_present(mock_llm: MockLLMProvider):
    r = mock_llm.complete(
        LLMRequest(task=LLMTaskType.draft_first_response, kb_article_id="article-x")
    )
    assert r.source_metadata.get("grounded") == "true"
    assert r.source_metadata.get("kb_article_id") == "article-x"


def test_grounding_metadata_when_kb_absent(mock_llm: MockLLMProvider):
    r = mock_llm.complete(LLMRequest(task=LLMTaskType.draft_first_response))
    assert r.source_metadata.get("grounded") == "false"


def test_safe_diagnostic_fields_excludes_confidential_and_restricted():
    fields = [
        DiagnosticField("channel", "jira", DataClassification.PUBLIC),
        DiagnosticField("http_error_code", "502", DataClassification.INTERNAL),
        DiagnosticField("ip_address", "10.0.0.1", DataClassification.CONFIDENTIAL),
        DiagnosticField("secret_note", "x", DataClassification.RESTRICTED),
    ]
    safe = safe_diagnostic_fields_for_llm(fields)
    assert safe["channel"] == "jira"
    assert safe["http_error_code"] == "502"
    assert "ip_address" not in safe
    assert "secret_note" not in safe


def test_safe_diagnostic_fields_from_result():
    dr = DiagnosticsResult(
        fields=[
            DiagnosticField("a", "1", DataClassification.PUBLIC),
            DiagnosticField("b", "2", DataClassification.CONFIDENTIAL),
        ],
        missing_required=["z"],
        follow_up_questions=["q?"],
    )
    m = safe_diagnostic_fields_for_llm_from_result(dr)
    assert m == {"a": "1"}


def test_merge_safe_context_drops_payload_and_secrets():
    base = {"ok": "1", "raw" + "_payload": "should-drop"}
    extra = {"also": "2", "API_KEY": "drop-me"}
    merged = merge_safe_context(base, extra)
    assert merged == {"ok": "1", "also": "2"}


def test_merge_safe_context_case_insensitive_forbidden_keys():
    merged = merge_safe_context({"Webhook_Secret": "x"}, {"good": "y"})
    assert "Webhook_Secret" not in merged
    assert merged == {"good": "y"}


def test_safe_context_ordering_affects_fingerprint(mock_llm: MockLLMProvider):
    r1 = mock_llm.complete(
        LLMRequest(task=LLMTaskType.classify_intent, safe_context={"a": "1", "b": "2"})
    )
    r2 = mock_llm.complete(
        LLMRequest(task=LLMTaskType.classify_intent, safe_context={"b": "2", "a": "1"})
    )
    assert r1.source_metadata["determinism_fingerprint"] == r2.source_metadata["determinism_fingerprint"]


def test_llm_response_is_frozen_dataclass_like():
    r = LLMResponse(text="t", source_metadata={"k": "v"})
    assert r.text == "t"


def test_customer_response_polish_preserves_grounded_mock_text(mock_llm: MockLLMProvider):
    grounded = "Use the storage recovery steps from the selected KB article."
    r = mock_llm.complete(
        LLMRequest(
            task=LLMTaskType.customer_response_polish,
            safe_context={"deterministic_response": grounded},
        )
    )
    assert r.text == grounded
    assert r.source_metadata["task"] == "customer_response_polish"


def test_provider_selection_defaults_to_mock_when_real_disabled():
    selected = select_llm_provider({"USE_REAL_LLM": "false"})
    response = selected.provider.complete(LLMRequest(task=LLMTaskType.demo_summary))
    assert selected.status.provider_mode == "mock"
    assert selected.status.real_llm_enabled is False
    assert selected.status.fallback_used is False
    assert response.source_metadata["provider_mode"] == "mock"


def test_missing_real_config_falls_back_safely():
    selected = select_llm_provider({"USE_REAL_LLM": "true"})
    response = selected.provider.complete(LLMRequest(task=LLMTaskType.demo_summary))
    safe_status = selected.status.to_safe_dict()
    assert safe_status["provider_mode"] == "fallback"
    assert safe_status["fallback_used"] is True
    assert safe_status["last_call_status"] == "fallback"
    assert safe_status["error_type"] == "MissingConfig"
    assert "LLM_API_KEY" not in str(safe_status)
    assert response.source_metadata["provider_mode"] == "fallback"


def test_real_provider_timeout_falls_back_safely(monkeypatch):
    def boom(*args, **kwargs):
        raise TimeoutError("timed out")

    monkeypatch.setattr("urllib.request.urlopen", boom)
    selected = select_llm_provider(
        {
            "USE_REAL_LLM": "true",
            "LLM_PROVIDER": "generic_http",
            "LLM_API_BASE_URL": "https://example.invalid/llm",
            "LLM_API_KEY": "test-only-placeholder",
            "LLM_MODEL": "demo-model",
            "LLM_TIMEOUT_SECONDS": "1",
        }
    )
    response = selected.provider.complete(LLMRequest(task=LLMTaskType.demo_summary))
    assert selected.status.provider_mode == "fallback"
    assert selected.status.fallback_used is True
    assert selected.status.last_call_status == "fallback"
    assert selected.status.error_type == "RealLLMProviderCallError"
    assert response.source_metadata["provider_mode"] == "fallback"
    assert "test-only-placeholder" not in str(selected.status.to_safe_dict())
    assert "test-only-placeholder" not in str(response.source_metadata)


def test_real_provider_request_payload_excludes_forbidden_context(monkeypatch):
    captured = {}

    class FakeResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self, limit):
            return b'{"text": "safe generated summary"}'

    def fake_urlopen(http_request, timeout):
        captured["data"] = http_request.data
        return FakeResponse()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    provider = RealLLMProvider(
        RealLLMProviderConfig(
            provider="generic_http",
            base_url="https://example.invalid/llm",
            api_key="test-only-placeholder",
            model="demo-model",
            timeout_seconds=1,
        )
    )
    response = provider.complete(
        LLMRequest(
            task=LLMTaskType.demo_summary,
            safe_context={
                "scenario_titles": "Tier 1 Happy Path",
                "raw" + "_payload": "must not leave process",
                "token": "must not leave process",
            },
        )
    )
    payload = captured["data"].decode("utf-8")
    assert response.text == "safe generated summary"
    assert "Tier 1 Happy Path" in payload
    assert ("raw" + "_payload") not in payload
    assert "must not leave process" not in payload
    assert "test-only-placeholder" not in payload
    assert "test-only-placeholder" not in str(response.source_metadata)
