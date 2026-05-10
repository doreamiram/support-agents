import re
from typing import Final

# Each entry is (compiled_pattern, replacement_string).
_RULES: Final[list[tuple[re.Pattern[str], str]]] = [
    # password=value or password:value (case-insensitive)
    (re.compile(r"(?i)(password|passwd|pwd)\s*[:=]\s*\S+"), "<password:REDACTED>"),
    # api_key=value or apikey=value
    (re.compile(r"(?i)(api[_-]?key|apikey)\s*[:=]\s*\S+"), "<api_key:REDACTED>"),
    # Bearer token in Authorization headers or inline text
    (re.compile(r"(?i)Bearer\s+[A-Za-z0-9\-._~+/]+=*"), "Bearer <token:REDACTED>"),
    # OpenAI / Anthropic style secret keys (sk-...)
    (re.compile(r"sk-[A-Za-z0-9]{20,}"), "<sk_secret:REDACTED>"),
    # GitHub personal access tokens (ghp_...)
    (re.compile(r"ghp_[A-Za-z0-9]{36}"), "<github_token:REDACTED>"),
    # AWS access key IDs
    (re.compile(r"AKIA[0-9A-Z]{16}"), "<aws_access_key:REDACTED>"),
    # generic secret=value or token=value
    (re.compile(r"(?i)(secret|token)\s*[:=]\s*\S+"), "<secret:REDACTED>"),
]


def redact(text: str) -> str:
    """Remove obvious secrets from text before it is logged or sent to customers."""
    for pattern, replacement in _RULES:
        text = pattern.sub(replacement, text)
    return text
