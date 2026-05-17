"""Web-demo regression tests: static fallback plus optional live backend run."""

from __future__ import annotations

import json
import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_WEB_DEMO = _REPO_ROOT / "web-demo"
_DEMO_DATA = _WEB_DEMO / "demo-data.json"
_INDEX = _WEB_DEMO / "index.html"
_APP_JS = _WEB_DEMO / "app.js"
_STYLES = _WEB_DEMO / "styles.css"
_REQUIRED_SCENARIO_IDS = frozenset(
    {
        "tier1-happy-path",
        "injection-tier2",
        "no-kb-tier2",
        "sla-escalation",
        "audit-verify",
    }
)

_FORBIDDEN_IN_JSON = re.compile(
    r"raw[_]payload|api[_\s-]*key|token|password|credential|openai|anthropic|langchain|sk[-]",
    re.IGNORECASE,
)


def test_web_demo_files_exist():
    assert _INDEX.is_file()
    assert _STYLES.is_file()
    assert _APP_JS.is_file()
    assert _DEMO_DATA.is_file()


def test_no_package_json_required():
    pkg = _REPO_ROOT / "package.json"
    assert not pkg.is_file(), "Phase 10B must not add package.json"


def test_demo_data_json_structure():
    data = json.loads(_DEMO_DATA.read_text(encoding="utf-8"))
    scenarios = data.get("scenarios")
    assert isinstance(scenarios, list)
    ids = {s.get("id") for s in scenarios}
    assert ids == _REQUIRED_SCENARIO_IDS
    for s in scenarios:
        assert s.get("status") == "PASS"
        assert s.get("action")
        assert s.get("reason")
        assert s.get("key_result")
        assert s.get("prd_capability")
        assert s.get("simulated")
        assert s.get("real")
        assert s.get("execution_trace")
        assert isinstance(s.get("execution_trace"), list)
    meta = data.get("meta")
    assert meta.get("tests_baseline") == "557/557"
    assert meta.get("llm_provider_mode") == "mock"
    assert meta.get("real_llm_enabled") is False
    assert meta.get("fallback_used") is False
    assert meta.get("last_llm_call_status") == "skipped"
    assert data.get("llm_summary")
    assert data.get("llm_provider_status", {}).get("provider_mode") == "mock"
    no_kb = next(s for s in scenarios if s.get("id") == "no-kb-tier2")
    assert "Engineer should |" not in no_kb.get("llm_handoff_summary", "")
    assert (
        "review the attempted steps, KB miss reason, diagnostics completeness, and SLA state"
        in no_kb.get("llm_handoff_summary", "")
    )
    tier1 = next(s for s in scenarios if s.get("id") == "tier1-happy-path")
    assert "..." not in tier1.get("llm_customer_response_polish", "")


def test_demo_data_json_has_no_sensitive_substrings():
    text = _DEMO_DATA.read_text(encoding="utf-8")
    assert _FORBIDDEN_IN_JSON.search(text) is None


def test_index_html_messaging():
    raw = _INDEX.read_text(encoding="utf-8")
    html = raw.lower()
    assert "deterministic prototype" in html
    assert "no real external integrations" in html
    assert "mockllmprovider" in html.replace(" ", "")
    assert "realllmprovider" in html.replace(" ", "")
    assert "llm-ready" in html.replace(" ", "") or "llm-ready" in html
    assert "llm provider status" in html
    assert "demo summary" in html
    assert "static snapshot" in html
    assert "local fastapi backend" in html
    assert "run live demo" in html
    assert "python.exe -m demo.scenarios" in raw
    assert "pytest.exe -q" in raw
    assert "static snapshot remains available" in html


def test_index_html_has_no_payload_literal():
    assert ("raw" + "_payload") not in _INDEX.read_text(encoding="utf-8").lower()


def test_index_html_has_run_live_demo_button():
    raw = _INDEX.read_text(encoding="utf-8")
    assert 'id="run-live-demo"' in raw
    assert "Run Live Demo" in raw


def test_app_js_uses_fetch_without_cdn():
    js = _APP_JS.read_text(encoding="utf-8")
    assert "fetch(" in js
    assert "demo-data.json" in js
    assert "cdn." not in js.lower()
    assert "unpkg" not in js.lower()


def test_app_js_has_backend_url_and_static_fallback():
    js = _APP_JS.read_text(encoding="utf-8")
    assert "BACKEND_DEMO_URL" in js
    assert "http://127.0.0.1:8000/api/demo/scenarios" in js
    assert "Live backend unavailable, showing static snapshot." in js
    assert "STATIC_DEMO_URL" in js


def test_app_js_renders_execution_trace():
    js = _APP_JS.read_text(encoding="utf-8")
    assert "execution_trace" in js
    assert "execution-trace" in js


def test_app_js_renders_safe_llm_fields():
    js = _APP_JS.read_text(encoding="utf-8")
    assert "llm_provider_status" in js
    assert "llm_summary" in js
    assert "llm_handoff_summary" in js
    assert "llm_customer_response_polish" in js
    assert ".innerHTML" in js
    assert "llmText.textContent" in js


def test_styles_self_contained():
    css = _STYLES.read_text(encoding="utf-8")
    assert "@import" not in css.lower()
