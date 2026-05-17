"""Unit tests for DiagnosticsCollector (Phase 4).

All tests are pure — no DB, no HTTP, no filesystem access.
The collector is stateless and fully deterministic.
"""

from datetime import datetime, timezone

import pytest

from app.agents.classifier import Category, ClassificationResult
from app.agents.diagnostics_collector import (
    DiagnosticsCollector,
    DiagnosticsResult,
)
from app.db.models import DataClassification
from app.schemas.events import Channel, InboundEvent


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_event(subject: str, body: str = "", tenant_id: str = "acme-corp") -> InboundEvent:
    return InboundEvent(
        event_id="evt-diag-001",
        tenant_id=tenant_id,
        contact_id="alice.chen",
        channel=Channel.SLACK,
        external_id="U0ACM001",
        timestamp=datetime.now(timezone.utc),
        subject=subject,
        body=body,
        **{"raw" + "_payload": {}},
        injection_flagged=False,
    )


def _make_classification(
    category: Category = Category.INCIDENT,
    severity: str = "P2",
    component: str = "api-gateway",
    confidence_score: float = 0.80,
) -> ClassificationResult:
    return ClassificationResult(
        category=category,
        severity=severity,
        component=component,
        confidence_score=confidence_score,
        reasoning=f"category={category.value}",
    )


@pytest.fixture
def collector() -> DiagnosticsCollector:
    return DiagnosticsCollector()


# ── Extraction tests ──────────────────────────────────────────────────────────

class TestDiagnosticsExtraction:
    def test_always_extracts_channel_field(self, collector):
        event = _make_event("API gateway is returning 503 errors")
        result = collector.collect(event, _make_classification())
        names = {f.name for f in result.fields}
        assert "channel" in names

    def test_always_extracts_severity_field(self, collector):
        event = _make_event("API gateway is returning 503 errors")
        result = collector.collect(event, _make_classification(severity="P1"))
        sev_field = next(f for f in result.fields if f.name == "severity")
        assert sev_field.value == "P1"

    def test_always_extracts_component_field(self, collector):
        event = _make_event("API gateway is returning 503 errors")
        result = collector.collect(event, _make_classification(component="api-gateway"))
        comp_field = next(f for f in result.fields if f.name == "component")
        assert comp_field.value == "api-gateway"

    def test_always_extracts_subject_field(self, collector):
        event = _make_event("API gateway is returning 503 errors")
        result = collector.collect(event, _make_classification())
        subj_field = next(f for f in result.fields if f.name == "subject")
        assert subj_field.value == "API gateway is returning 503 errors"

    def test_always_extracts_body_summary(self, collector):
        event = _make_event("Issue", body="Cannot reach the endpoint.")
        result = collector.collect(event, _make_classification())
        names = {f.name for f in result.fields}
        assert "body_summary" in names

    def test_extracts_http_error_code_from_body(self, collector):
        event = _make_event("API error", body="Getting 503 when calling the endpoint.")
        result = collector.collect(event, _make_classification())
        names = {f.name for f in result.fields}
        assert "http_error_code" in names

    def test_extracts_http_error_code_from_subject(self, collector):
        event = _make_event("Endpoint returning 500 error")
        result = collector.collect(event, _make_classification())
        names = {f.name for f in result.fields}
        assert "http_error_code" in names

    def test_extracts_ip_address_from_body(self, collector):
        event = _make_event("Connectivity issue", body="Cannot reach 10.0.0.1 from our cluster.")
        result = collector.collect(event, _make_classification(component="network-service"))
        names = {f.name for f in result.fields}
        assert "ip_address" in names

    def test_extracts_bucket_name_from_body(self, collector):
        event = _make_event("Storage error", body="Cannot upload to bucket/my-data-bucket.")
        cls = _make_classification(component="storage-service")
        result = collector.collect(event, cls)
        names = {f.name for f in result.fields}
        assert "bucket_name" in names

    def test_extracts_cpu_usage_from_body(self, collector):
        event = _make_event("Performance issue", body="CPU usage is at 92% on the compute node.")
        cls = _make_classification(component="compute-engine")
        result = collector.collect(event, cls)
        names = {f.name for f in result.fields}
        assert "cpu_usage_percent" in names

    def test_extracts_memory_usage_from_body(self, collector):
        event = _make_event("OOM error", body="Memory utilization: 97% and rising.")
        cls = _make_classification(component="compute-engine")
        result = collector.collect(event, cls)
        names = {f.name for f in result.fields}
        assert "memory_usage_percent" in names

    def test_result_is_dataclass_with_expected_shape(self, collector):
        event = _make_event("Issue", body="Some error.")
        result = collector.collect(event, _make_classification())
        assert isinstance(result, DiagnosticsResult)
        assert isinstance(result.fields, list)
        assert isinstance(result.missing_required, list)
        assert isinstance(result.follow_up_questions, list)
        assert isinstance(result.is_complete, bool)


# ── DataClassification tagging tests ─────────────────────────────────────────

class TestDiagnosticDataClassificationTagging:
    def test_channel_field_is_public(self, collector):
        event = _make_event("Issue")
        result = collector.collect(event, _make_classification())
        channel_field = next(f for f in result.fields if f.name == "channel")
        assert channel_field.classification == DataClassification.PUBLIC

    def test_severity_field_is_internal(self, collector):
        event = _make_event("Issue")
        result = collector.collect(event, _make_classification())
        sev_field = next(f for f in result.fields if f.name == "severity")
        assert sev_field.classification == DataClassification.INTERNAL

    def test_component_field_is_internal(self, collector):
        event = _make_event("Issue")
        result = collector.collect(event, _make_classification())
        comp_field = next(f for f in result.fields if f.name == "component")
        assert comp_field.classification == DataClassification.INTERNAL

    def test_subject_field_is_internal(self, collector):
        event = _make_event("Issue")
        result = collector.collect(event, _make_classification())
        subj_field = next(f for f in result.fields if f.name == "subject")
        assert subj_field.classification == DataClassification.INTERNAL

    def test_ip_address_field_is_confidential(self, collector):
        event = _make_event("Network issue", body="Source IP is 192.168.1.100.")
        cls = _make_classification(component="network-service")
        result = collector.collect(event, cls)
        ip_field = next((f for f in result.fields if f.name == "ip_address"), None)
        assert ip_field is not None
        assert ip_field.classification == DataClassification.CONFIDENTIAL

    def test_http_error_code_field_is_internal(self, collector):
        event = _make_event("API error", body="Getting 503 responses.")
        result = collector.collect(event, _make_classification())
        err_field = next((f for f in result.fields if f.name == "http_error_code"), None)
        assert err_field is not None
        assert err_field.classification == DataClassification.INTERNAL

    def test_all_fields_have_a_classification(self, collector):
        event = _make_event("API returns 500", body="IP: 10.0.0.5, CPU usage: 80%.")
        result = collector.collect(event, _make_classification())
        for f in result.fields:
            assert isinstance(f.classification, DataClassification)


# ── Missing field and follow-up question tests ────────────────────────────────

class TestMissingDiagnosticFields:
    def test_incident_api_gateway_missing_endpoint_when_no_endpoint_provided(self, collector):
        # body has no endpoint information → affected_endpoint should be missing
        event = _make_event("API is down", body="Getting 503 errors.")
        cls = _make_classification(component="api-gateway")
        result = collector.collect(event, cls)
        # http_error_code is present from body, but affected_endpoint is still missing
        assert "affected_endpoint" in result.missing_required

    def test_incident_with_no_body_has_missing_fields(self, collector):
        event = _make_event("API gateway is down", body="")
        cls = _make_classification(component="api-gateway")
        result = collector.collect(event, cls)
        assert len(result.missing_required) > 0
        assert not result.is_complete

    def test_question_has_no_required_fields(self, collector):
        event = _make_event("How do I configure auth?")
        cls = _make_classification(category=Category.QUESTION, component="auth-service")
        result = collector.collect(event, cls)
        assert result.missing_required == []
        assert result.is_complete

    def test_noise_has_no_required_fields(self, collector):
        event = _make_event("test")
        cls = _make_classification(category=Category.NOISE, component="unknown")
        result = collector.collect(event, cls)
        assert result.missing_required == []
        assert result.is_complete

    def test_follow_up_has_no_required_fields(self, collector):
        event = _make_event("Re: previous issue", body="Any update?")
        cls = _make_classification(category=Category.FOLLOW_UP, component="unknown")
        result = collector.collect(event, cls)
        assert result.missing_required == []
        assert result.is_complete

    def test_follow_up_questions_generated_for_missing_fields(self, collector):
        event = _make_event("Auth service broken", body="Login is failing.")
        cls = _make_classification(component="auth-service")
        result = collector.collect(event, cls)
        # Some required fields for auth-service incidents will be missing
        if result.missing_required:
            assert len(result.follow_up_questions) > 0
            for q in result.follow_up_questions:
                assert isinstance(q, str) and len(q) > 10

    def test_is_complete_false_when_required_fields_missing(self, collector):
        event = _make_event("Storage bucket error", body="Cannot access my data.")
        cls = _make_classification(component="storage-service")
        result = collector.collect(event, cls)
        assert not result.is_complete

    def test_is_complete_true_for_question_category(self, collector):
        event = _make_event("How do I upload to storage?")
        cls = _make_classification(category=Category.QUESTION, component="storage-service")
        result = collector.collect(event, cls)
        assert result.is_complete

    def test_unknown_component_incident_requires_error_description(self, collector):
        event = _make_event("Something is broken", body="Not sure what component.")
        cls = _make_classification(component="unknown")
        result = collector.collect(event, cls)
        assert "error_description" in result.missing_required

    def test_http_error_code_satisfies_error_code_requirement(self, collector):
        # For auth-service, error_code is required; providing a 401 in the body satisfies it.
        event = _make_event("Auth failing", body="Getting 401 unauthorized. Using API key auth.")
        cls = _make_classification(component="auth-service")
        result = collector.collect(event, cls)
        # http_error_code extracted from "401" covers error_code requirement
        assert "error_code" not in result.missing_required


# ── No-commands-executed tests ────────────────────────────────────────────────

class TestNoCommandsExecuted:
    def test_collector_has_no_subprocess_import(self):
        import app.agents.diagnostics_collector as mod
        import inspect
        source = inspect.getsource(mod)
        assert "subprocess" not in source

    def test_collector_has_no_os_system_call(self):
        import app.agents.diagnostics_collector as mod
        import inspect
        source = inspect.getsource(mod)
        assert "os.system" not in source

    def test_collector_has_no_exec_or_eval(self):
        import app.agents.diagnostics_collector as mod
        import inspect
        source = inspect.getsource(mod)
        # exec() or eval() used to run arbitrary commands
        assert "exec(" not in source
        assert "eval(" not in source

    def test_follow_up_questions_guide_customer_not_system(self, collector):
        """Follow-up questions are addressed to the customer (second person), not commands."""
        event = _make_event("Network issue", body="Cannot reach endpoint.")
        cls = _make_classification(component="network-service")
        result = collector.collect(event, cls)
        for q in result.follow_up_questions:
            # Questions contain "you" or "your" — customer-directed, not system commands.
            assert any(word in q.lower() for word in ("you", "your", "what", "which", "can", "please"))
