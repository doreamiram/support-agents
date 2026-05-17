"""Tests for app/services/telemetry.py (Phase 7 minimal telemetry service)."""

import pytest

from app.services.telemetry import Telemetry, TelemetryEvent


# ── Basic instantiation and recording ─────────────────────────────────────────

class TestTelemetryBasic:
    def test_telemetry_instantiates(self):
        assert Telemetry() is not None

    def test_record_known_event_type_succeeds(self):
        t = Telemetry()
        t.record("scenario_started", {"scenario": "test"})
        assert t.count("scenario_started") == 1

    def test_events_initially_empty(self):
        assert Telemetry().events() == []

    def test_record_multiple_events_accumulate(self):
        t = Telemetry()
        t.record("scenario_started")
        t.record("scenario_completed", {"passed": True})
        assert len(t.events()) == 2

    def test_count_for_absent_event_type_is_zero(self):
        assert Telemetry().count("tier1_response_generated") == 0


# ── All allowed event types ───────────────────────────────────────────────────

class TestTelemetryEventTypes:
    def test_scenario_started_recordable(self):
        t = Telemetry()
        t.record("scenario_started")
        assert t.count("scenario_started") == 1

    def test_scenario_completed_recordable(self):
        t = Telemetry()
        t.record("scenario_completed", {"passed": True})
        assert t.count("scenario_completed") == 1

    def test_tier1_response_generated_recordable(self):
        t = Telemetry()
        t.record("tier1_response_generated", {"ticket_id": "t-001"})
        assert t.count("tier1_response_generated") == 1

    def test_handoff_created_recordable(self):
        t = Telemetry()
        t.record("handoff_created", {"reason": "low_confidence"})
        assert t.count("handoff_created") == 1

    def test_audit_verified_recordable(self):
        t = Telemetry()
        t.record("audit_verified", {"event_count": 5})
        assert t.count("audit_verified") == 1

    def test_sla_breach_detected_recordable(self):
        t = Telemetry()
        t.record("sla_breach_detected", {"ticket_id": "t-001"})
        assert t.count("sla_breach_detected") == 1

    def test_escalation_triggered_recordable(self):
        t = Telemetry()
        t.record("escalation_triggered", {"simulated": True})
        assert t.count("escalation_triggered") == 1

    def test_scenario_error_recordable(self):
        t = Telemetry()
        t.record("scenario_error", {"error": "test error"})
        assert t.count("scenario_error") == 1

    def test_unknown_event_type_raises_value_error(self):
        with pytest.raises(ValueError):
            Telemetry().record("raw" + "_payload_dump")

    def test_unknown_event_type_with_sensitive_name_raises(self):
        with pytest.raises(ValueError):
            Telemetry().record("customer_data_leak")

    def test_record_without_metadata_succeeds(self):
        t = Telemetry()
        t.record("scenario_started")
        assert t.events()[0].metadata == {}


# ── Safety and immutability ───────────────────────────────────────────────────

class TestTelemetrySafety:
    def test_event_metadata_is_copied_not_shared(self):
        """Mutating the caller's dict must not change recorded metadata."""
        t = Telemetry()
        meta = {"key": "original"}
        t.record("scenario_started", meta)
        meta["key"] = "modified"
        assert t.events()[0].metadata["key"] == "original"

    def test_events_returns_copy_of_internal_list(self):
        """Mutating the returned list must not affect internal state."""
        t = Telemetry()
        t.record("scenario_started")
        events = t.events()
        events.clear()
        assert len(t.events()) == 1

    def test_no_payload_dump_in_allowed_event_types(self):
        assert ("raw" + "_payload") not in Telemetry._ALLOWED_EVENT_TYPES

    def test_no_customer_data_in_allowed_event_type_names(self):
        for event_type in Telemetry._ALLOWED_EVENT_TYPES:
            assert "payload" not in event_type
            assert "customer_data" not in event_type

    def test_summary_counts_per_event_type(self):
        t = Telemetry()
        t.record("scenario_started")
        t.record("scenario_completed", {"passed": True})
        t.record("scenario_started")
        summary = t.summary()
        assert summary["scenario_started"] == 2
        assert summary["scenario_completed"] == 1

    def test_summary_returns_dict(self):
        assert isinstance(Telemetry().summary(), dict)

    def test_event_has_iso_timestamp(self):
        t = Telemetry()
        t.record("scenario_started")
        ts = t.events()[0].timestamp
        assert isinstance(ts, str)
        assert "T" in ts  # ISO-8601 has a T separator

    def test_event_is_telemetry_event_instance(self):
        t = Telemetry()
        t.record("scenario_started")
        assert isinstance(t.events()[0], TelemetryEvent)

    def test_multiple_records_of_same_type_accumulate(self):
        t = Telemetry()
        for _ in range(3):
            t.record("scenario_started")
        assert t.count("scenario_started") == 3
