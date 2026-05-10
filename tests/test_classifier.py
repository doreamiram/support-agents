"""Unit tests for the InteractionClassifier (Phase 3).

All tests are pure — no DB, no HTTP.  The classifier is deterministic and
rule-based; tests verify that specific inputs produce the expected category,
severity, component, and confidence values.
"""

from datetime import datetime, timezone

import pytest

from app.agents.classifier import (
    CONFIDENCE_THRESHOLD,
    Category,
    InteractionClassifier,
    check_human_requested,
)
from app.config.loader import load_config
from app.schemas.events import Channel, InboundEvent


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_event(
    subject: str,
    body: str = "",
    injection_flagged: bool = False,
) -> InboundEvent:
    return InboundEvent(
        event_id="evt-clf-001",
        tenant_id="acme-corp",
        contact_id="alice.chen",
        channel=Channel.SLACK,
        external_id="U0ACM001",
        timestamp=datetime.now(timezone.utc),
        subject=subject,
        body=body,
        raw_payload={},
        injection_flagged=injection_flagged,
    )


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def config():
    return load_config()


@pytest.fixture(scope="module")
def classifier(config):
    return InteractionClassifier(config)


# ── Incident classification ───────────────────────────────────────────────────

class TestIncidentClassification:
    def test_service_down_is_incident(self, classifier):
        event = _make_event(
            "The API gateway is down",
            "Cannot reach any endpoints since 9 am.",
        )
        result = classifier.classify(event)
        assert result.category == Category.INCIDENT

    def test_outage_is_p1(self, classifier):
        event = _make_event(
            "API gateway outage",
            "Service is completely unavailable.",
        )
        result = classifier.classify(event)
        assert result.category == Category.INCIDENT
        assert result.severity == "P1"

    def test_crashed_is_incident(self, classifier):
        event = _make_event(
            "Compute engine crashed",
            "VM instances are unreachable.",
        )
        result = classifier.classify(event)
        assert result.category == Category.INCIDENT

    def test_incident_component_detected(self, classifier):
        event = _make_event(
            "Auth service is failing",
            "Login tokens are not being issued.",
        )
        result = classifier.classify(event)
        assert result.category == Category.INCIDENT
        assert result.component == "auth-service"

    def test_incident_confidence_above_threshold(self, classifier):
        event = _make_event(
            "Network service is down and unreachable",
            "VPN connection refused.",
        )
        result = classifier.classify(event)
        assert result.category == Category.INCIDENT
        assert result.confidence_score >= CONFIDENCE_THRESHOLD

    def test_incident_has_reasoning(self, classifier):
        event = _make_event("Storage service is unavailable", "Cannot upload files.")
        result = classifier.classify(event)
        assert result.category == Category.INCIDENT
        assert isinstance(result.reasoning, str)
        assert len(result.reasoning) > 0

    def test_degraded_service_is_p2(self, classifier):
        event = _make_event(
            "API gateway is degraded",
            "Responses are slow for multiple users.",
        )
        result = classifier.classify(event)
        assert result.category == Category.INCIDENT
        assert result.severity == "P2"


# ── Question classification ───────────────────────────────────────────────────

class TestQuestionClassification:
    def test_how_to_is_question(self, classifier):
        event = _make_event("How do I configure the authentication service?")
        result = classifier.classify(event)
        assert result.category == Category.QUESTION

    def test_what_is_is_question(self, classifier):
        event = _make_event("What is the billing cycle?")
        result = classifier.classify(event)
        assert result.category == Category.QUESTION

    def test_question_severity_is_p4(self, classifier):
        event = _make_event("How do I set up OAuth2?")
        result = classifier.classify(event)
        assert result.category == Category.QUESTION
        assert result.severity == "P4"

    def test_question_component_detected(self, classifier):
        event = _make_event("How do I manage my storage buckets?")
        result = classifier.classify(event)
        assert result.category == Category.QUESTION
        assert result.component == "storage-service"

    def test_question_confidence_above_threshold(self, classifier):
        event = _make_event("Where can I find the API documentation?")
        result = classifier.classify(event)
        assert result.category == Category.QUESTION
        assert result.confidence_score >= CONFIDENCE_THRESHOLD


# ── Follow-up classification ──────────────────────────────────────────────────

class TestFollowUpClassification:
    def test_re_subject_prefix_is_follow_up(self, classifier):
        event = _make_event("Re: API gateway outage", "Any update on this?")
        result = classifier.classify(event)
        assert result.category == Category.FOLLOW_UP

    def test_following_up_body_is_follow_up(self, classifier):
        event = _make_event(
            "Previous request",
            "Just following up on my earlier message. Any update?",
        )
        result = classifier.classify(event)
        assert result.category == Category.FOLLOW_UP

    def test_any_update_body_is_follow_up(self, classifier):
        event = _make_event("Checking in", "Any update on the ticket?")
        result = classifier.classify(event)
        assert result.category == Category.FOLLOW_UP

    def test_follow_up_severity_is_p4(self, classifier):
        event = _make_event("Re: billing inquiry")
        result = classifier.classify(event)
        assert result.category == Category.FOLLOW_UP
        assert result.severity == "P4"

    def test_follow_up_confidence_above_threshold(self, classifier):
        event = _make_event("Re: outage report", "Still waiting for a response.")
        result = classifier.classify(event)
        assert result.category == Category.FOLLOW_UP
        assert result.confidence_score >= CONFIDENCE_THRESHOLD


# ── Noise classification ──────────────────────────────────────────────────────

class TestNoiseClassification:
    def test_test_message_is_noise(self, classifier):
        event = _make_event("test")
        result = classifier.classify(event)
        assert result.category == Category.NOISE

    def test_hello_is_noise(self, classifier):
        event = _make_event("hello")
        result = classifier.classify(event)
        assert result.category == Category.NOISE

    def test_ping_is_noise(self, classifier):
        event = _make_event("ping")
        result = classifier.classify(event)
        assert result.category == Category.NOISE

    def test_thanks_is_noise(self, classifier):
        event = _make_event("thanks")
        result = classifier.classify(event)
        assert result.category == Category.NOISE

    def test_noise_severity_is_p4(self, classifier):
        event = _make_event("hi")
        result = classifier.classify(event)
        assert result.category == Category.NOISE
        assert result.severity == "P4"


# ── Low-confidence classification ─────────────────────────────────────────────

class TestLowConfidenceClassification:
    def test_unrecognised_text_is_low_confidence(self, classifier):
        event = _make_event("something random", "I don't know")
        result = classifier.classify(event)
        assert result.category == Category.LOW_CONFIDENCE

    def test_unknown_subject_empty_body_is_low_confidence(self, classifier):
        event = _make_event("xyz abc")
        result = classifier.classify(event)
        assert result.category == Category.LOW_CONFIDENCE

    def test_low_confidence_score_below_threshold(self, classifier):
        event = _make_event("maybe perhaps", "possibly")
        result = classifier.classify(event)
        assert result.category == Category.LOW_CONFIDENCE
        assert result.confidence_score < CONFIDENCE_THRESHOLD

    def test_low_confidence_has_reasoning(self, classifier):
        event = _make_event("something")
        result = classifier.classify(event)
        assert result.category == Category.LOW_CONFIDENCE
        assert isinstance(result.reasoning, str)
        assert "threshold" in result.reasoning.lower()

    def test_all_fields_present_on_low_confidence(self, classifier):
        event = _make_event("foo bar baz")
        result = classifier.classify(event)
        assert result.category == Category.LOW_CONFIDENCE
        assert isinstance(result.severity, str)
        assert isinstance(result.component, str)
        assert isinstance(result.confidence_score, float)
        assert isinstance(result.reasoning, str)


# ── Human-request detection ───────────────────────────────────────────────────

class TestHumanRequestDetection:
    def test_speak_to_human_detected(self):
        event = _make_event("I need help", "I want to speak to a human agent.")
        assert check_human_requested(event) is True

    def test_connect_to_person_detected(self):
        event = _make_event("Connect me with a person please")
        assert check_human_requested(event) is True

    def test_need_a_human_detected(self):
        event = _make_event("Network down", "I need a human to look at this.")
        assert check_human_requested(event) is True

    def test_live_agent_phrase_detected(self):
        event = _make_event("Please transfer me to a live agent")
        assert check_human_requested(event) is True

    def test_normal_incident_not_human_request(self):
        event = _make_event("API gateway is down", "Cannot reach the endpoint.")
        assert check_human_requested(event) is False

    def test_question_not_human_request(self):
        event = _make_event("How do I configure auth?")
        assert check_human_requested(event) is False


# ── Config integration ────────────────────────────────────────────────────────

class TestClassifierWithConfig:
    def test_config_component_ids_are_valid(self, classifier, config):
        valid_ids = {c.id for c in config.components.components}
        event = _make_event("The billing service is down")
        result = classifier.classify(event)
        assert result.category == Category.INCIDENT
        assert result.component in valid_ids

    def test_unknown_component_returns_unknown(self, classifier):
        event = _make_event("The frobnicator is down", "Cannot reach the zorblax.")
        result = classifier.classify(event)
        assert result.component == "unknown"

    def test_classifier_without_config_still_works(self):
        clf = InteractionClassifier()  # no config
        event = _make_event("API gateway is down", "Service unavailable.")
        result = clf.classify(event)
        assert result.category == Category.INCIDENT
        assert result.component == "api-gateway"
