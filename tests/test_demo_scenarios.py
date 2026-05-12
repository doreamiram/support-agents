"""Tests for the Phase 7 demo scenario runner (demo/scenarios.py).

Covers:
  - Demo module is importable without real external integrations
  - All required scenario functions exist
  - Scenario runner returns structured, deterministic results
  - All five scenarios pass end-to-end
  - FakeClock is used (no real system time in SLA/escalation scenario)
  - No real LLM, Slack, JIRA, or WhatsApp integration
  - Required documentation files exist and mention expected commands
"""

import inspect
import sys
from pathlib import Path


# ── Import smoke test ─────────────────────────────────────────────────────────

class TestDemoScenariosImport:
    def test_demo_module_importable(self):
        """demo.scenarios must import without real external integrations."""
        from demo import scenarios  # noqa: F401
        assert scenarios is not None

    def test_no_real_llm_library_imported(self):
        """Demo must not import any real LLM library."""
        from demo import scenarios as m
        src = inspect.getsource(m)
        assert "openai" not in src
        assert "anthropic" not in src
        assert "langchain" not in src

    def test_run_all_scenarios_callable(self):
        from demo.scenarios import run_all_scenarios
        assert callable(run_all_scenarios)

    def test_scenario_result_class_exists(self):
        from demo.scenarios import ScenarioResult
        assert ScenarioResult is not None


# ── Required scenario functions ───────────────────────────────────────────────

class TestRequiredScenarios:
    def test_five_scenarios_in_registry(self):
        from demo.scenarios import _SCENARIOS
        assert len(_SCENARIOS) == 5

    def test_tier1_happy_path_exists(self):
        from demo.scenarios import scenario_tier1_happy_path
        assert callable(scenario_tier1_happy_path)

    def test_injection_tier2_exists(self):
        from demo.scenarios import scenario_injection_tier2
        assert callable(scenario_injection_tier2)

    def test_no_kb_match_exists(self):
        from demo.scenarios import scenario_no_kb_match
        assert callable(scenario_no_kb_match)

    def test_sla_escalation_exists(self):
        from demo.scenarios import scenario_sla_escalation
        assert callable(scenario_sla_escalation)

    def test_audit_verification_exists(self):
        from demo.scenarios import scenario_audit_verification
        assert callable(scenario_audit_verification)


# ── Scenario runner results ───────────────────────────────────────────────────

class TestScenarioResults:
    def test_run_all_returns_list(self):
        from demo.scenarios import run_all_scenarios
        results = run_all_scenarios()
        assert isinstance(results, list)

    def test_run_all_returns_five_results(self):
        from demo.scenarios import run_all_scenarios
        results = run_all_scenarios()
        assert len(results) == 5

    def test_every_result_has_non_empty_name(self):
        from demo.scenarios import run_all_scenarios
        for r in run_all_scenarios():
            assert isinstance(r.name, str) and r.name

    def test_every_result_has_passed_bool(self):
        from demo.scenarios import run_all_scenarios
        for r in run_all_scenarios():
            assert isinstance(r.passed, bool)

    def test_every_result_has_non_empty_summary(self):
        from demo.scenarios import run_all_scenarios
        for r in run_all_scenarios():
            assert isinstance(r.summary, str) and r.summary

    def test_all_scenarios_pass(self):
        """End-to-end: every scenario must report passed=True."""
        from demo.scenarios import run_all_scenarios
        for r in run_all_scenarios():
            assert r.passed, f"Scenario {r.name!r} failed: {r.error}"


# ── Determinism ───────────────────────────────────────────────────────────────

class TestDeterminism:
    def test_two_consecutive_runs_produce_same_pass_fail_outcomes(self):
        """Running the demo twice must produce identical pass/fail results."""
        from demo.scenarios import run_all_scenarios
        first = [r.passed for r in run_all_scenarios()]
        second = [r.passed for r in run_all_scenarios()]
        assert first == second

    def test_sla_scenario_uses_fake_clock_not_real_time(self):
        """SLA scenario must use FakeClock: no breach at T=0, breach after advance."""
        from demo.scenarios import scenario_sla_escalation
        from app.services.telemetry import Telemetry

        result = scenario_sla_escalation(Telemetry())
        assert result.passed
        # Real time cannot advance 15 minutes during a sub-second test run.
        assert result.details.get("response_breached_at_t0") is False
        assert result.details.get("response_breached_after_advance") is True


# ── No real integrations ──────────────────────────────────────────────────────

class TestNoRealIntegrations:
    def test_no_slack_sdk_imported(self):
        from demo import scenarios  # noqa: F401
        assert "slack_sdk" not in sys.modules
        assert "slack_bolt" not in sys.modules

    def test_no_jira_client_imported(self):
        from demo import scenarios  # noqa: F401
        assert "jira" not in sys.modules

    def test_no_whatsapp_client_imported(self):
        from demo import scenarios  # noqa: F401
        assert "twilio" not in sys.modules

    def test_scenarios_use_in_memory_sqlite(self):
        """All scenarios must use sqlite:///:memory:, not a file-based DB."""
        from demo import scenarios as m
        src = inspect.getsource(m)
        assert "sqlite:///:memory:" in src

    def test_demo_does_not_make_outbound_http_requests(self):
        """Demo module must not import requests or call outbound HTTP."""
        from demo import scenarios as m
        src = inspect.getsource(m)
        assert "requests.get" not in src
        assert "httpx.get" not in src


# ── Documentation presence ────────────────────────────────────────────────────

class TestDocumentationExists:
    _root = Path(__file__).parent.parent

    def test_readme_exists(self):
        assert (self._root / "README.md").exists()

    def test_readme_mentions_pytest(self):
        content = (self._root / "README.md").read_text(encoding="utf-8")
        assert "pytest" in content

    def test_readme_mentions_demo_scenarios(self):
        content = (self._root / "README.md").read_text(encoding="utf-8")
        assert "scenarios" in content

    def test_demo_guide_exists(self):
        assert (self._root / "docs" / "demo_guide.md").exists()

    def test_demo_guide_mentions_demo_command(self):
        content = (self._root / "docs" / "demo_guide.md").read_text(
            encoding="utf-8"
        )
        assert "scenarios" in content

    def test_evaluation_framework_exists(self):
        assert (self._root / "docs" / "evaluation_framework.md").exists()

    def test_evaluation_framework_mentions_prd(self):
        content = (self._root / "docs" / "evaluation_framework.md").read_text(
            encoding="utf-8"
        )
        assert "PRD" in content or "requirements" in content.lower()

    def test_evaluation_framework_mentions_limitations(self):
        content = (self._root / "docs" / "evaluation_framework.md").read_text(
            encoding="utf-8"
        )
        assert "limitation" in content.lower() or "deferred" in content.lower()
