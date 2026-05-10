from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from app.config.models import AppConfig
from app.schemas.events import InboundEvent

# Minimum score for any category to win outright.
# Below this threshold the result is LOW_CONFIDENCE.
CONFIDENCE_THRESHOLD: float = 0.35

# ── Scoring patterns ──────────────────────────────────────────────────────────
# Each tuple is (regex_pattern, score_contribution).
# Scores for a category accumulate; the sum is capped at 1.0.

_INCIDENT_PATTERNS: list[tuple[str, float]] = [
    (r"\b(down|outage|offline|crash(?:ed)?|unreachable|unavailable)\b", 0.40),
    (r"\b(not working|broken|fail(?:ed|ing)?|failure)\b", 0.40),
    (r"\b(degraded|slow|high latency|impacted|disrupted)\b", 0.35),
    (r"\b(cannot connect|can't connect|connection (?:refused|timeout))\b", 0.35),
    (r"\b(error|exception|500|503|504)\b", 0.20),
]

_QUESTION_PATTERNS: list[tuple[str, float]] = [
    (r"\b(how (?:do|to|can)|what (?:is|are)|where (?:can|do)|when (?:can|will))\b", 0.45),
    (r"\b(explain|guide|documentation|tutorial|help me understand)\b", 0.35),
    (r"\?", 0.15),
    (r"\b(does|can I|is there|are there)\b", 0.20),
]

# Follow-up subject patterns (checked against the subject field only).
_FOLLOW_UP_SUBJECT_PATTERNS: list[tuple[str, float]] = [
    (r"^re:", 0.60),
]

# Follow-up body/combined patterns.
_FOLLOW_UP_BODY_PATTERNS: list[tuple[str, float]] = [
    (r"\b(following up|any update|status update|update on|any news|any progress)\b", 0.50),
    (r"\b(still waiting|still pending|not yet resolved)\b", 0.35),
]

# Noise patterns — checked against the stripped combined text.
_NOISE_PATTERNS: list[tuple[str, float]] = [
    (r"^(test(?:ing)?|ping|hello|hi|hey|ok|okay|thanks|thank you|bye|yes|no|ack)\.?$", 0.70),
    (r"^[\W\d\s]+$", 0.55),  # only non-word characters, digits, or whitespace
]

# Severity: checked in P1→P2→P3 order; first match wins. Default is P4.
_SEVERITY_PATTERNS: dict[str, list[str]] = {
    "P1": [r"\b(critical|down|outage|offline|crash(?:ed)?|unreachable|unavailable|emergency|urgent)\b"],
    "P2": [r"\b(degraded|slow|high latency|fail(?:ed|ing)?|error|exception|significant|multiple users)\b"],
    "P3": [r"\b(partial|some users|workaround|occasionally|intermittent|impairment|minor impact)\b"],
}

# Component detection: (component_id, pattern).
# Evaluated in order; the first match wins.
_COMPONENT_PATTERNS: list[tuple[str, str]] = [
    ("api-gateway",     r"\b(api|gateway|endpoint|ingress|routing)\b"),
    ("auth-service",    r"\b(auth(?:entication)?|login|logout|token|oauth|credential|password|sso|saml)\b"),
    ("compute-engine",  r"\b(compute|vm\b|instance|workload|cpu|virtual machine|container|pod)\b"),
    ("storage-service", r"\b(storage|bucket|upload|download|file|disk|object|blob)\b"),
    ("network-service", r"\b(network|dns|vpc|firewall|connectivity|ping|vpn|subnet)\b"),
    ("billing-service", r"\b(billing|invoice|subscription|charge|payment|cost|usage|meter)\b"),
]

# Human-agent escalation request patterns.
_HUMAN_REQUEST_PATTERNS: list[str] = [
    r"\b(speak|talk|connect)\b.{0,30}\b(human|person|agent|engineer|representative)\b",
    r"\b(human|live|real)\b.{0,10}\b(agent|support|person|representative)\b",
    r"\bi\s+(want|need|would like)\b.{0,20}\b(human|person|agent|someone)\b",
    r"\bescalate\b.{0,20}\b(this|to a|to human|my issue|my case)\b",
]


# ── Public types ──────────────────────────────────────────────────────────────

class Category(str, Enum):
    INCIDENT = "incident"
    QUESTION = "question"
    FOLLOW_UP = "follow_up"
    NOISE = "noise"
    LOW_CONFIDENCE = "low_confidence"


@dataclass
class ClassificationResult:
    category: Category
    severity: str            # P1 / P2 / P3 / P4
    component: str           # component id or "unknown"
    confidence_score: float  # 0.0 – 1.0, rounded to 4 decimal places
    reasoning: str


# ── Classifier ────────────────────────────────────────────────────────────────

class InteractionClassifier:
    """
    Deterministic rule-based classifier.  No LLM or external I/O.

    Accepts an optional AppConfig; when provided, component IDs are validated
    against the loaded components list.  Without config, the classifier falls
    back to the hardcoded component ID set in _COMPONENT_PATTERNS.
    """

    def __init__(self, config: Optional[AppConfig] = None) -> None:
        self._config = config
        self._valid_components: frozenset[str] = (
            frozenset(c.id for c in config.components.components)
            if config is not None
            else frozenset(cid for cid, _ in _COMPONENT_PATTERNS)
        )

    def classify(self, event: InboundEvent) -> ClassificationResult:
        subject = event.subject.strip()
        body = event.body.strip()
        combined = f"{subject} {body}".strip()
        combined_stripped = combined.strip()

        scores: dict[Category, float] = {
            Category.INCIDENT:  0.0,
            Category.QUESTION:  0.0,
            Category.FOLLOW_UP: 0.0,
            Category.NOISE:     0.0,
        }

        for pattern, weight in _INCIDENT_PATTERNS:
            if re.search(pattern, combined, re.I):
                scores[Category.INCIDENT] += weight

        for pattern, weight in _QUESTION_PATTERNS:
            if re.search(pattern, combined, re.I):
                scores[Category.QUESTION] += weight

        for pattern, weight in _FOLLOW_UP_SUBJECT_PATTERNS:
            if re.search(pattern, subject.lower()):
                scores[Category.FOLLOW_UP] += weight

        for pattern, weight in _FOLLOW_UP_BODY_PATTERNS:
            if re.search(pattern, combined, re.I):
                scores[Category.FOLLOW_UP] += weight

        for pattern, weight in _NOISE_PATTERNS:
            if re.search(pattern, combined_stripped, re.I):
                scores[Category.NOISE] += weight

        # Cap each category at 1.0
        scores = {k: min(v, 1.0) for k, v in scores.items()}

        best_category = max(scores, key=lambda c: scores[c])
        best_score = scores[best_category]

        if best_score < CONFIDENCE_THRESHOLD:
            return ClassificationResult(
                category=Category.LOW_CONFIDENCE,
                severity="P4",
                component=self._detect_component(combined),
                confidence_score=round(best_score, 4),
                reasoning=(
                    f"Best score {best_score:.2f} is below confidence threshold "
                    f"{CONFIDENCE_THRESHOLD:.2f}; cannot reliably classify"
                ),
            )

        severity = self._detect_severity(combined, best_category)
        component = self._detect_component(combined)

        return ClassificationResult(
            category=best_category,
            severity=severity,
            component=component,
            confidence_score=round(best_score, 4),
            reasoning=(
                f"category={best_category.value} (score={best_score:.2f}); "
                f"severity={severity}; component={component}"
            ),
        )

    def _detect_severity(self, text: str, category: Category) -> str:
        if category in (Category.QUESTION, Category.NOISE, Category.FOLLOW_UP):
            return "P4"
        for sev in ("P1", "P2", "P3"):
            for pattern in _SEVERITY_PATTERNS[sev]:
                if re.search(pattern, text, re.I):
                    return sev
        return "P4"

    def _detect_component(self, text: str) -> str:
        for component_id, pattern in _COMPONENT_PATTERNS:
            if re.search(pattern, text, re.I) and component_id in self._valid_components:
                return component_id
        return "unknown"


# ── Utility ───────────────────────────────────────────────────────────────────

def check_human_requested(event: InboundEvent) -> bool:
    """Return True if the inbound text contains an explicit request for a human agent."""
    text = f"{event.subject} {event.body}"
    return any(re.search(p, text, re.I) for p in _HUMAN_REQUEST_PATTERNS)
