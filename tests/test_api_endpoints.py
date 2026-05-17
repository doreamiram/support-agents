import os

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "version" in body


# ── Demo endpoint ─────────────────────────────────────────────────────────────

class TestDemoAdvanceTime:
    def test_demo_endpoint_returns_404_without_demo_mode(self, monkeypatch):
        """Without DEMO_MODE=true the endpoint must refuse with 404."""
        monkeypatch.delenv("DEMO_MODE", raising=False)
        response = client.post("/demo/advance-time?minutes=60")
        assert response.status_code == 404

    def test_demo_endpoint_returns_404_when_demo_mode_false(self, monkeypatch):
        monkeypatch.setenv("DEMO_MODE", "false")
        response = client.post("/demo/advance-time?minutes=60")
        assert response.status_code == 404

    def test_demo_endpoint_works_when_demo_mode_true(self, monkeypatch):
        monkeypatch.setenv("DEMO_MODE", "true")
        response = client.post("/demo/advance-time?minutes=30")
        assert response.status_code == 200

    def test_demo_response_contains_now_field(self, monkeypatch):
        monkeypatch.setenv("DEMO_MODE", "true")
        response = client.post("/demo/advance-time?minutes=0")
        assert response.status_code == 200
        assert "now" in response.json()

    def test_demo_response_contains_advanced_minutes(self, monkeypatch):
        monkeypatch.setenv("DEMO_MODE", "true")
        response = client.post("/demo/advance-time?minutes=90")
        assert response.status_code == 200
        assert response.json()["advanced_minutes"] == 90

    def test_demo_response_contains_advanced_hours(self, monkeypatch):
        monkeypatch.setenv("DEMO_MODE", "true")
        response = client.post("/demo/advance-time?hours=3")
        assert response.status_code == 200
        assert response.json()["advanced_hours"] == 3

    def test_demo_now_is_iso_string(self, monkeypatch):
        monkeypatch.setenv("DEMO_MODE", "true")
        response = client.post("/demo/advance-time?minutes=0")
        assert response.status_code == 200
        from datetime import datetime
        now_str = response.json()["now"]
        # Must be parseable as ISO 8601
        datetime.fromisoformat(now_str)

    def test_demo_endpoint_case_insensitive_demo_mode(self, monkeypatch):
        """DEMO_MODE value is compared case-insensitively."""
        monkeypatch.setenv("DEMO_MODE", "TRUE")
        response = client.post("/demo/advance-time?minutes=10")
        assert response.status_code == 200


class TestLiveDemoScenarios:
    _safe_trace_steps = {
        "intake_received",
        "identity_verified",
        "interaction_classified",
        "ticket_created",
        "diagnostics_collected",
        "kb_retrieved",
        "llm_provider_checked",
        "sla_checked",
        "escalation_evaluated",
        "audit_event_written",
    }

    def test_live_demo_endpoint_exists(self):
        response = client.get("/api/demo/scenarios")
        assert response.status_code == 200

    def test_live_demo_endpoint_returns_five_scenarios(self):
        body = client.get("/api/demo/scenarios").json()
        assert len(body["scenarios"]) == 5

    def test_live_demo_meta_marks_mock_phase(self):
        body = client.get("/api/demo/scenarios").json()
        assert body["meta"]["mode"] == "live_backend"
        assert body["meta"]["tests_baseline"] == "549/549"
        assert body["meta"]["cli_demo_scenarios"] == "5/5"
        assert body["meta"]["llm_provider_mode"] == "mock_for_now"

    def test_every_live_demo_scenario_passes(self):
        body = client.get("/api/demo/scenarios").json()
        assert all(s["status"] == "PASS" for s in body["scenarios"])

    def test_every_live_demo_scenario_has_execution_trace(self):
        body = client.get("/api/demo/scenarios").json()
        for scenario in body["scenarios"]:
            assert scenario["execution_trace"]
            assert isinstance(scenario["execution_trace"], list)

    def test_live_demo_trace_contains_only_safe_step_names(self):
        body = client.get("/api/demo/scenarios").json()
        for scenario in body["scenarios"]:
            assert set(scenario["execution_trace"]) <= self._safe_trace_steps

    def test_live_demo_response_excludes_sensitive_terms(self):
        text = client.get("/api/demo/scenarios").text.lower()
        forbidden = [
            "raw_payload",
            "api_key",
            "apikey",
            "secret",
            "token",
            "credential",
        ]
        for term in forbidden:
            assert term not in text

    def test_live_demo_cors_allows_local_static_demo_origin(self):
        response = client.options(
            "/api/demo/scenarios",
            headers={
                "Origin": "http://127.0.0.1:8080",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == (
            "http://127.0.0.1:8080"
        )

    def test_live_demo_cors_does_not_allow_broad_origin(self):
        response = client.options(
            "/api/demo/scenarios",
            headers={
                "Origin": "http://example.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert response.status_code == 400


# ── Phase 6: /audit/verify endpoint ──────────────────────────────────────────
# These tests use the `client` fixture from conftest.py, which injects an
# in-memory SQLite database so each test has a clean, isolated audit chain.

class TestAuditVerify:
    def test_audit_verify_returns_200_with_tenant_id(self, client):
        response = client.get("/audit/verify?tenant_id=acme-corp")
        assert response.status_code == 200

    def test_audit_verify_returns_200_without_tenant_id(self, client):
        response = client.get("/audit/verify")
        assert response.status_code == 200

    def test_audit_verify_response_has_valid_field(self, client):
        response = client.get("/audit/verify?tenant_id=acme-corp")
        assert "valid" in response.json()

    def test_audit_verify_response_has_event_count(self, client):
        response = client.get("/audit/verify?tenant_id=acme-corp")
        assert "event_count" in response.json()

    def test_audit_verify_response_has_chain_breaks(self, client):
        response = client.get("/audit/verify?tenant_id=acme-corp")
        assert "chain_breaks" in response.json()

    def test_audit_verify_response_has_tenants_verified(self, client):
        response = client.get("/audit/verify?tenant_id=acme-corp")
        assert "tenants_verified" in response.json()

    def test_audit_verify_empty_chain_is_valid(self, client):
        response = client.get("/audit/verify?tenant_id=acme-corp")
        body = response.json()
        assert body["valid"] is True
        assert body["event_count"] == 0

    def test_audit_verify_no_tenant_id_verifies_multiple_tenants(self, client):
        response = client.get("/audit/verify")
        body = response.json()
        assert isinstance(body["tenants_verified"], list)
        assert len(body["tenants_verified"]) >= 1

    def test_audit_verify_does_not_expose_payload_content(self, client):
        response = client.get("/audit/verify?tenant_id=acme-corp")
        body = response.json()
        # The response must not contain raw audit payload fields.
        assert "payload_json" not in str(body)
        assert "payload_json" not in body

    def test_audit_verify_valid_field_is_bool(self, client):
        response = client.get("/audit/verify?tenant_id=acme-corp")
        body = response.json()
        assert isinstance(body["valid"], bool)

    def test_audit_verify_event_count_is_int(self, client):
        response = client.get("/audit/verify?tenant_id=acme-corp")
        body = response.json()
        assert isinstance(body["event_count"], int)

    def test_audit_verify_chain_breaks_is_list(self, client):
        response = client.get("/audit/verify?tenant_id=acme-corp")
        body = response.json()
        assert isinstance(body["chain_breaks"], list)

    def test_audit_verify_tenants_verified_contains_requested_tenant(self, client):
        response = client.get("/audit/verify?tenant_id=acme-corp")
        body = response.json()
        assert "acme-corp" in body["tenants_verified"]

