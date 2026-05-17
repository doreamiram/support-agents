# LLM integration notes (prototype readiness)

This document explains how the Modelyo Support Agents prototype aligns with the
PRD description of an **LLM-based agent system**, what is implemented today, and
how optional text-generation calls are constrained **without** changing the trust
and safety posture of the deterministic pipeline.

---

## 1. PRD alignment

The PRD positions Tier 1 / Tier 2 support automation as an LLM-based system. The
prototype remains **fully runnable without any external inference API**: routing,
diagnostics, KB retrieval, first-response wording, SLA, escalation, and handoff
packaging are implemented with **deterministic, test-backed agents**. Phase 8
added an explicit provider contract; Phase 10B adds an optional real provider
for safe demo text while preserving the same **input contracts** and
**classification-based redaction rules**.

---

## 2. What exists in the prototype (Phases 8 and 10B)

| Artifact | Role |
|---|---|
| `LLMProvider` (`app/services/llm_provider.py`) | Abstract contract: one `complete(LLMRequest) -> LLMResponse` step. |
| `MockLLMProvider` | Deterministic, local implementation: same request always yields the same response; **no network I/O**. |
| `RealLLMProvider` (`app/services/real_llm_provider.py`) | Optional stdlib-only `generic_http` provider for controlled demo tasks. |
| Provider selection | `USE_REAL_LLM=false` defaults to mock; missing config or call failure falls back to mock. |
| `LLMRequest` / `LLMResponse` | Small structured types: task label, optional tenant and hints, `safe_context` string map, grounding metadata on output. |
| `LLMUnsupportedTaskError` | Raised when a task string is not one of the supported task types (fail-safe at request construction). |
| Sanitizer helpers | `safe_diagnostic_fields_for_llm*`, `merge_safe_context` — strip `CONFIDENTIAL` / `RESTRICTED` diagnostics and drop dangerous context keys, including raw payload and common secret-style names. |

**Supported mock task types** (for future parity with production prompts):

- `classify_intent`
- `draft_first_response`
- `summarize_handoff`
- `generate_follow_up_question`
- `demo_summary`
- `handoff_summary`
- `customer_response_polish`

The CLI demo and deterministic orchestrator path are unchanged. The live web demo
uses the selected provider only after scenario execution to produce safe display
fields. The mock exists so tests and reviewers can reason about **safe inputs**
and **deterministic outputs** even when real inference is disabled.

---

## 3. Where a real provider would plug in

Recommended integration boundaries (choose one or combine):

1. **Behind `FirstResponseGenerator`** — replace or augment template assembly
   with a call to `LLMProvider.complete` only after KB retrieval has selected an
   article and sanitizers have built `LLMRequest.safe_context` from
   `PUBLIC` / `INTERNAL` diagnostics only.
2. **Intent / summarization sidecar** — optional calls after the rule-based
   classifier or `HandoffBuilder` to produce richer natural language, while
   **keeping classifier and handoff packet fields authoritative** for routing
   and audit.

In all cases, raw inbound payload content must never be passed into
`LLMRequest`. Channel secrets, API keys, and customer credentials stay out of
model context; only redacted or explicitly safe fields belong in `safe_context`.

---

## 4. Production hosting options (PRD T-02)

| Option | Summary |
|---|---|
| **Managed inference API** | Lowest operational burden; requires clear data-processing agreement, region pinning, and egress controls aligned with Modelyo Confidential Cloud. |
| **Self-hosted model** | Full control over weights and traffic; higher ops cost; fits air-gapped or confidential-compute deployments. |
| **Hybrid** | Small on-box model for triage / redaction checks plus managed API for drafting; complexity trade-off for latency and governance. |

The choice is a **trust-boundary and compliance** decision, not an application
code detail; the `LLMProvider` interface is the same regardless.

---

## 5. Trust boundary and confidentiality

- **Data classification** (`PUBLIC`, `INTERNAL`, `CONFIDENTIAL`, `RESTRICTED`)
  already governs diagnostics. Only `PUBLIC` and `INTERNAL` fields may enter
  model-oriented maps via the provided helpers.
- **Tier 2 handoffs** already exclude sensitive diagnostic values from
  `HandoffPacket`; the same rule applies to anything sent to a model.
- **Auditability**: production should log **task type, tenant id, ticket id,
  latency, and outcome** — not raw prompts or completions — unless a separate
  retention policy explicitly allows it.

---

## 6. Optional real inference boundaries

- **Disabled by default** — `USE_REAL_LLM=false` selects `MockLLMProvider`.
- **Configuration gated** — real mode requires `LLM_PROVIDER=generic_http`,
  `LLM_API_BASE_URL`, `LLM_API_KEY`, and `LLM_MODEL`.
- **Fallback protected** — missing config, timeout, HTTP error, malformed
  response, or provider exception returns mock output and safe status metadata.
- **Task limited** — real mode is restricted to `demo_summary`,
  `handoff_summary`, and `customer_response_polish`.
- **No authority transfer** — LLM output does not decide routing, identity,
  security, SLA, escalation, classification, KB confidence, or injection
  handling.

---

## 7. Real provider contract

1. Keep real provider code behind `LLMProvider`.
2. Map `LLMRequest` to the chosen service format **inside that class** only.
3. Translate responses into `LLMResponse`, filling `source_metadata` with
   safe fields only: provider mode, task, model id, status, fallback flag, and
   error type when relevant.
4. Keep **unit tests on the mock** for regression and use fake local HTTP
   responses for real-provider contract tests.

---

## 8. Guardrails before enabling real inference

| Guardrail | Intent |
|---|---|
| **Redaction** | Run `app.utils.redaction.redact` (or equivalent) on any model-produced text before customer delivery. |
| **Classification filtering** | Use `safe_diagnostic_fields_for_llm*`; never downgrade `CONFIDENTIAL` / `RESTRICTED` into prompts. |
| **Timeout** | Cap wall-clock wait; on timeout fall back to Tier 2 or template response. |
| **Fallback** | If the provider errors or returns empty, use existing deterministic paths (no silent failure). |
| **Logging without payloads** | Structured logs: ids, task, status — not prompt/completion bodies. |
| **Prompt-injection controls** | Reuse `InjectionGuard` outcomes; never pass flagged raw text straight into a model without quarantine handling. |
| **Grounded output** | Require citation to KB article id or explicit “no grounded answer” path (already how Tier 1 first response behaves). |

---

## 9. Vendor-specific SDKs

This repository intentionally avoids third-party client packages for Phase 10B.
If Modelyo later selects a vendor SDK, add it only behind the production
`LLMProvider` implementation, keep keys in a secrets manager, and extend the test
suite with contract tests or recorded fixtures as appropriate.
