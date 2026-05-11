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


# ── Phase 6 not yet implemented ───────────────────────────────────────────────

class TestPhase6NotImplemented:
    def test_audit_verify_endpoint_not_implemented(self):
        """Phase 6: /audit/verify does not exist yet."""
        response = client.get("/audit/verify")
        assert response.status_code == 404
