import re
from dataclasses import dataclass
from typing import Final, Optional

# Patterns targeting prompt-injection techniques, not common support language.
# Each tuple is (compiled_pattern, label).
_PATTERNS: Final[list[tuple[re.Pattern[str], str]]] = [
    (re.compile(r"(?i)ignore\s+(?:all\s+)?(?:previous|prior|above)\s+instructions?|ignore\s+all\s+instructions?"),  "ignore-instructions"),
    (re.compile(r"(?i)\bsystem\s+prompt\b"),                                  "system-prompt"),
    (re.compile(r"\[INST\]"),                                                  "inst-tag"),
    (re.compile(r"<\|im_start\|>"),                                            "im-start-tag"),
    (re.compile(r"<\|im_end\|>"),                                              "im-end-tag"),
    (re.compile(r"(?i)forget\s+your\s+(instructions?|training|previous)"),    "forget-training"),
    (re.compile(r"(?i)\bjailbreak\b"),                                         "jailbreak"),
    (re.compile(r"(?i)\bDAN\s+(mode|prompt|persona)\b"),                      "dan-mode"),
    (re.compile(r"(?i)disregard\s+(all|your)\s+previous"),                    "disregard-previous"),
]

_SAFE_BODY = "[MESSAGE WITHHELD — potential prompt injection pattern detected]"


@dataclass
class InjectionResult:
    flagged: bool
    matched_pattern: Optional[str]
    sanitized_text: str            # use this as the event body, not the raw text


class InjectionGuard:
    """Scan inbound customer text for prompt-injection patterns."""

    def scan(self, text: str) -> InjectionResult:
        for pattern, label in _PATTERNS:
            if pattern.search(text):
                return InjectionResult(
                    flagged=True,
                    matched_pattern=label,
                    sanitized_text=_SAFE_BODY,
                )
        return InjectionResult(
            flagged=False,
            matched_pattern=None,
            sanitized_text=text,
        )
