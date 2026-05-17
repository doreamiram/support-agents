"""Stdlib-only real LLM provider for controlled, sanitized demo tasks."""

from __future__ import annotations

import json
import socket
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Mapping, Optional

from app.services.llm_provider import (
    LLMProvider,
    LLMRequest,
    LLMResponse,
    LLMTaskType,
    merge_safe_context,
)


class RealLLMProviderConfigError(ValueError):
    """Raised when real provider configuration is incomplete or unsupported."""


class RealLLMProviderCallError(RuntimeError):
    """Raised for timeout, transport, HTTP, or malformed-response failures."""


@dataclass(frozen=True)
class RealLLMProviderConfig:
    provider: str
    base_url: str
    api_key: str
    model: str
    timeout_seconds: float = 10.0


class RealLLMProvider(LLMProvider):
    """Generic HTTP provider constrained to safe text-generation side tasks."""

    _ALLOWED_TASKS = frozenset(
        {
            LLMTaskType.demo_summary,
            LLMTaskType.handoff_summary,
            LLMTaskType.customer_response_polish,
        }
    )

    def __init__(self, config: RealLLMProviderConfig) -> None:
        if config.provider != "generic_http":
            raise RealLLMProviderConfigError("UnsupportedProvider")
        if not config.base_url or not config.api_key or not config.model:
            raise RealLLMProviderConfigError("MissingConfig")
        if config.timeout_seconds <= 0:
            raise RealLLMProviderConfigError("InvalidTimeout")
        self.config = config

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> "RealLLMProvider":
        timeout_raw = env.get("LLM_TIMEOUT_SECONDS", "10")
        try:
            timeout_seconds = float(timeout_raw)
        except ValueError as exc:
            raise RealLLMProviderConfigError("InvalidTimeout") from exc

        config = RealLLMProviderConfig(
            provider=env.get("LLM_PROVIDER", "generic_http"),
            base_url=env.get("LLM_API_BASE_URL", ""),
            api_key=env.get("LLM_API_KEY", ""),
            model=env.get("LLM_MODEL", ""),
            timeout_seconds=timeout_seconds,
        )
        return cls(config)

    def complete(self, request: LLMRequest) -> LLMResponse:
        if request.task not in self._ALLOWED_TASKS:
            raise RealLLMProviderCallError("UnsupportedTask")

        payload = self._build_payload(request)
        body = json.dumps(payload, sort_keys=True).encode("utf-8")
        http_request = urllib.request.Request(
            self.config.base_url,
            data=body,
            headers={
                "Authorization": "Bearer " + self.config.api_key,
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(
                http_request,
                timeout=self.config.timeout_seconds,
            ) as response:
                status_code = getattr(response, "status", 200)
                if status_code < 200 or status_code >= 300:
                    raise RealLLMProviderCallError("HTTPError")
                response_body = response.read(65536)
        except TimeoutError as exc:
            raise RealLLMProviderCallError("Timeout") from exc
        except socket.timeout as exc:
            raise RealLLMProviderCallError("Timeout") from exc
        except urllib.error.HTTPError as exc:
            raise RealLLMProviderCallError("HTTPError") from exc
        except urllib.error.URLError as exc:
            raise RealLLMProviderCallError("TransportError") from exc

        text = self._extract_text(response_body)
        if not text:
            raise RealLLMProviderCallError("EmptyResponse")

        return LLMResponse(
            text=text[:4000],
            source_metadata={
                "provider": "real",
                "provider_mode": "real",
                "task": request.task.value,
                "model": self.config.model,
                "fallback_used": "false",
                "last_call_status": "success",
            },
        )

    def _build_payload(self, request: LLMRequest) -> dict[str, Any]:
        safe_context = merge_safe_context({}, request.safe_context)
        return {
            "model": self.config.model,
            "task": request.task.value,
            "instructions": self._task_instruction(request.task),
            "input": {
                "safe_context": safe_context,
                "category": request.category,
                "severity": request.severity,
                "component": request.component,
                "kb_article_id": request.kb_article_id,
            },
        }

    def _task_instruction(self, task: LLMTaskType) -> str:
        if task is LLMTaskType.demo_summary:
            return (
                "Summarize only the provided safe demo scenario context. "
                "Do not add claims, diagnostics, credentials, or hidden details."
            )
        if task is LLMTaskType.handoff_summary:
            return (
                "Write a concise Tier 2 engineer handoff summary from only the "
                "provided deterministic context. Do not add troubleshooting steps."
            )
        if task is LLMTaskType.customer_response_polish:
            return (
                "Rewrite only the provided grounded customer response for clarity. "
                "Do not add steps, claims, severity changes, routing, or escalation."
            )
        raise RealLLMProviderCallError("UnsupportedTask")

    def _extract_text(self, response_body: bytes) -> str:
        try:
            data = json.loads(response_body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RealLLMProviderCallError("MalformedResponse") from exc

        candidates: list[Optional[str]] = [
            data.get("text") if isinstance(data, dict) else None,
            data.get("completion") if isinstance(data, dict) else None,
            data.get("response") if isinstance(data, dict) else None,
        ]
        if isinstance(data, dict):
            message = data.get("message")
            if isinstance(message, dict):
                candidates.append(message.get("content"))

        for candidate in candidates:
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()
        return ""
