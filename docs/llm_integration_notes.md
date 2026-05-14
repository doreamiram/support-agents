# LLM integration notes (prototype readiness)

This document explains how the Modelyo Support Agents prototype aligns with the
PRD description of an **LLM-based agent system**, what is implemented today, and
how a production text-generation backend would be introduced **without** changing
the trust and safety posture of the deterministic pipeline.

---

## 1. PRD alignment

The PRD positions Tier 1 / Tier 2 support automation as an LLM-based system. The
prototype remains **fully runnable without any external inference API**: routing,
diagnostics, KB retrieval, first-response wording, SLA, escalation, and handoff
packaging are implemented with **deterministic, test-backed agents**. Phase 8
adds an explicit **readiness layer** so production can swap in a real model
implementation later while preserving the same **input contracts** and
**classification-based redaction rules**.

---

## 2. What exists in the prototype (Phase 8)

| Artifact | Role |
|---|---|
| `LLMProvider` (`app/services/llm_provider.py`) | Abstract contract: one `complete(LLMRequest) -> LLMResponse` step. |
| `MockLLMProvider` | Deterministic, local implementation: same request always yields the same response; **no network I/O**. |
| `LLMRequest` / `LLMResponse` | Small structured types: task label, optional tenant and hints, `safe_context` string map, grounding metadata on output. |
| `LLMUnsupportedTaskError` | Raised when a task string is not one of the supported task types (fail-safe at request construction). |
| Sanitizer helpers | `safe_diagnostic_fields_for_llm*`, `merge_safe_context` — strip `CONFIDENTIAL` / `RESTRICTED` diagnostics and drop dangerous context keys (e.g. `raw_payload`, common secret key names). |

**Supported mock task types** (for future parity with production prompts):

- `classify_intent`
- `draft_first_response`
- `summarize_handoff`
- `generate_follow_up_question`

The **demo and full pytest suite** do not require calling `MockLLMProvider`; the
existing orchestrator path is unchanged. The mock exists so tests and reviewers
can reason about **safe inputs** and **deterministic outputs** before any real
inference is enabled.

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

In all cases, **`InboundEvent.raw_payload` must never be passed into
`LLMRequest`**. Channel secrets, API keys, and customer credentials stay out of
model context; only redacted or explicitly safe fields belong in
`safe_context`.

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

## 6. Why the prototype does not call a real LLM

- **Reproducibility** — CI and demos must be bitwise-stable without API keys or
  network flakes.
- **Safety reviews** — reviewers can audit behaviour without data leaving the
  workstation.
- **Cost and rate limits** — not applicable to open-source evaluation of this
  repository.

---

## 7. Replacing `MockLLMProvider` later

1. Subclass or implement `LLMProvider` in a new module (e.g.
   `app/services/production_llm_provider.py` — not shipped in this repo).
2. Map `LLMRequest` to the vendor’s message format **inside that class** only.
3. Translate responses into `LLMResponse`, filling `source_metadata` with
   grounding references (KB article id, citation ids, model id, content policy
   version).
4. Inject the implementation at composition root (future factory or FastAPI
   dependency); keep **unit tests on the mock** for regression.

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

This repository intentionally avoids naming or importing third-party client
packages in the readiness module. When Modelyo selects a hosting option, add the
vendor SDK **only** behind the production `LLMProvider` implementation, keep
keys in a secrets manager, and extend the test suite with contract tests or
recorded fixtures as appropriate.
