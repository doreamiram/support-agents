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


# ── Phase 7 not yet implemented ───────────────────────────────────────────────

class TestPhase7NotImplemented:
    def test_demo_scenarios_file_not_present(self):
        """Phase 7: demo/scenarios.py must not exist yet."""
        from pathlib import Path
        scenarios = Path(__file__).parent.parent / "demo" / "scenarios.py"
        assert not scenarios.exists(), (
            "demo/scenarios.py exists — Phase 7 has been implemented prematurely"
        )
