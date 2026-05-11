# Modelyo Support Agents — Design Document

> **Phase:** 4 (diagnostics collector, knowledge retriever, first response generator). This document is updated after each implementation phase.

---

## 1. Purpose

This system is a junior-level professional prototype for Modelyo Confidential Cloud enterprise support automation. It simulates Tier 1 and Tier 2 customer support workflows with deterministic orchestration and agentic components.

---

## 2. Architecture Overview

The system is organized into 14 discrete responsibilities:

| # | Component | Responsibility |
|---|---|---|
| 1 | Channel Adapters | Normalize JIRA, Slack, WhatsApp inbound events into a canonical schema |
| 2 | Identity & Tenant Resolver | Verify inbound contacts; resolve tenant context |
| 3 | Interaction Classifier | Map issue text to category, severity, component, confidence |
| 4 | Support Orchestrator | Deterministic workflow: intake → classify → ticket → respond → notify |
| 5 | Ticket Manager | Create, update, close tickets with tenant isolation |
| 6 | Diagnostics Collector | Extract structured fields; generate follow-up questions |
| 7 | Knowledge Retriever | Keyword + tag search against KB markdown files |
| 8 | First Response Generator | Grounded mock-LLM response; safe fallback if no KB match |
| 9 | SLA Tracker | Time-aware state machine; breach detection via ClockProvider |
| 10 | Escalation Engine | Configurable on-call chain; quiet hours; critical override |
| 11 | Communication Policy | Gate outbound messages to meaningful state changes only |
| 12 | Human Handoff Builder | Structured packet for Tier 2 engineers |
| 13 | Audit Logger | Tamper-evident hash-chained audit trail in SQLite |
| 14 | Config Loader | Load and validate all YAML config at startup |

---

## 3. Tier 1 / Tier 2 Workflow

**Tier 1 (automated):** Contact verified → classified → KB match found with high confidence → grounded first response sent → SLA tracking started → on-call notified if severity warrants.

**Tier 2 (human loop-in):** Triggered when any of the following is true:
- Classifier confidence is below configured threshold
- No KB article meets minimum confidence
- Customer explicitly requests a human
- Runbook steps are exhausted without resolution
- A dependent service or integration fails

Tier 2 does not mean the system stops. SLA tracking, audit logging, communication policy, and escalation continue while a human engineer is engaged.

---

## 4. Security Design

- **Webhook signature verification:** HMAC-SHA256 of payload with per-tenant secret
- **Replay protection:** event_id deduplication + timestamp tolerance window
- **Prompt-injection guard:** pattern scanning before inbound text reaches the classifier or LLM
- **Secret redaction:** applied to all logged and outbound text
- **Data classification:** `PUBLIC / INTERNAL / CONFIDENTIAL / RESTRICTED` enum on all customer data fields

---

## 5. Tenant Isolation

Enforced at the repository/data-access layer. Every tenant-scoped repository method requires `tenant_id`. Queries always include `WHERE tenant_id = ?`. Cross-tenant access raises `TenantAccessError` and writes an audit event.

---

## 6. Audit Trail

Stored in SQLite. Each event carries `previous_hash` and `current_hash` forming a tamper-evident chain. The `/audit/verify` utility walks the chain and reports breaks. `audit_logs/` contains exported demo examples only.

---

## 7. SLA and Escalation

SLA deadlines are calculated from severity rules in `config/sla_rules.yaml`. Breach detection uses a `ClockProvider` interface (`SystemClock` in production, `FakeClock` in tests and demo). Escalation chains and quiet hours are configurable per tenant. Sev-1 critical override bypasses quiet hours when `critical_override: true`.

---

## 8. Implementation Phases

| Phase | Scope |
|---|---|
| 1A | Skeleton, health endpoint, README |
| 1B | Config loader, YAML validation |
| 1C | DB models, repositories, isolation tests |
| 2 | Channel adapters, identity, security guards |
| 3 | Classifier, orchestrator, Tier 1/2 routing |
| 4 | Diagnostics, knowledge retrieval, first response |
| 5 | SLA tracker, FakeClock, escalation, communication policy |
| 6 | Handoff builder, full audit chain |
| 7 | Demo scenarios, full test suite, final docs |

---

## 9. Config Layer Design (Phase 1B)

### Config files

| File | Purpose |
|---|---|
| `config/tenants.yaml` | Tenant identity, timezone, registered contacts, per-tenant webhook secret |
| `config/components.yaml` | Platform service/component registry |
| `config/sla_rules.yaml` | Severity → response time, resolution time, breach action |
| `config/escalation_chains.yaml` | Ordered on-call contacts per tenant × severity × component |
| `config/quiet_hours.yaml` | Per-tenant outbound communication windows, cooldown, critical override flag |
| `config/knowledge/index.yaml` | KB article index: title, file, tags, components, min confidence |

### Key design decisions

- **Fail-fast startup:** `load_config()` raises `ConfigLoadError` with a human-readable message if any file is missing or any Pydantic model fails validation. The FastAPI `lifespan` handler re-raises as `RuntimeError`, stopping the process before the server accepts requests.
- **Pydantic model separation:** All config models live in `app/config/models.py`; loading logic lives in `app/config/loader.py`. This allows tests to instantiate models directly without touching the filesystem.
- **YAML integer pitfall:** HTTP status codes (e.g. `401`, `403`) used as KB tags must be quoted in YAML to prevent them being parsed as integers and failing `list[str]` validation.
- **Quiet hours per-tenant scope:** `quiet_hours.yaml` governs outbound customer communication windows, not internal on-call schedules. The `critical_override: true` field makes P1/Sev-1 messages bypass the window regardless of time; this is configurable per tenant. Cooldown prevents message flooding within a single incident.
- **Escalation chain granularity:** Chains are keyed by `(tenant_id, severity, component)`. Use `component: "*"` for a default chain; component-specific chains are checked first (Phase 5 lookup order).

---

## 10. Database and Tenant Isolation Design (Phase 1C)

### ORM models

| Model | PK type | tenant_id | Notes |
|---|---|---|---|
| `Ticket` | UUID string | Required, indexed | Holds SLA deadline columns; status transitions managed by TicketRepository |
| `AuditEvent` | Integer (auto-increment) | Optional (nullable for system events) | Integer PK gives unambiguous insertion order for hash chain |
| `Contact` | UUID string | Required, indexed | Runtime snapshot; source of truth is `tenants.yaml` |
| `Diagnostic` | UUID string | Required, indexed | `classification` field carries `DataClassification` enum value |
| `SLAState` | UUID string | Required, indexed | One-to-one with Ticket via unique FK |
| `ReplayGuard` | UUID string | None (system-wide) | `event_id` is globally unique; no tenant scope |

### Tenant isolation enforcement

- Every public method on every tenant-scoped repository accepts `tenant_id` as a **required keyword argument**.
- `get_by_id` methods first look up the record by primary key alone (no tenant filter), then compare `record.tenant_id` to the caller's `tenant_id`. If they differ, `TenantAccessError` is raised immediately — before any data is returned.
- `list_*` methods always include `WHERE tenant_id = ?` in the query. Cross-tenant records are never included even if their IDs happen to be known.
- `TenantAccessError` carries `resource`, `resource_id`, and `requested_tenant` attributes so callers can log and audit the violation.

### Audit hash chain

- SHA-256 is applied to the concatenated string `previous_hash | event_type | actor | payload_json | created_at_iso`.
- The first event for a tenant has `previous_hash = ""`.
- Each subsequent event stores the prior event's `current_hash` as its own `previous_hash`.
- `AuditRepository.verify_chain(tenant_id)` walks all events in insertion order and re-derives each hash. It returns `(False, message)` on the first mismatch, distinguishing a `previous_hash` link break from a `current_hash` recomputation failure (indicating record tampering).
- Chain verification is per-tenant; chains for different tenants are completely independent.

### Database session management

- `make_engine(url)` and `make_session_factory(engine)` are public helpers so tests can inject an in-memory SQLite engine without touching the module-level singleton.
- `init_db(engine=None)` calls `Base.metadata.create_all()` and is safe to call multiple times. All tests use an in-memory engine injected via the `db_engine` / `db_session` fixtures in `conftest.py`.
- `datetime.utcnow()` is used for all timestamps. These calls will be replaced by `ClockProvider` / `FakeClock` in Phase 5 to enable time-travel tests without deprecation noise.

---

## 11. Intake Adapters and Security Guards Design (Phase 2)

### Channel adapter pipeline

All three webhook endpoints (JIRA, Slack, WhatsApp) share the same seven-step pipeline, executed in this fixed order:

1. **Tenant resolution** — look up `X-Tenant-Id` header in loaded config; return 403 if unknown.
2. **Signature verification** — HMAC-SHA256 of the raw request body using the tenant's `webhook_secret`; header must start with `sha256=`; return 403 on mismatch.
3. **Payload parsing** — Pydantic `model_validate_json()`; return 400 on schema violation.
4. **Replay protection** — timestamp tolerance check (±`REPLAY_TOLERANCE_SECONDS`, default 300 s) first, then event_id dedup against `replay_guard` table; return 400 on stale/future, 409 on duplicate.
5. **Identity resolution** — config-only lookup by `(channel, external_id)` across all tenants; return 403 if contact is not found or is registered for a different channel.
6. **Injection guard** — regex scan of inbound free-text; flags but does NOT reject; returns sanitized body with the original replaced by a safe placeholder.
7. **Normalization** — assemble canonical `InboundEvent`; return `WebhookResponse` (HTTP 200).

### Canonical InboundEvent schema

All channels produce a single `InboundEvent` Pydantic model with:
- `event_id`, `tenant_id`, `contact_id`, `channel` (enum: jira/slack/whatsapp)
- `external_id` — the channel-native identifier (email for JIRA, user_id for Slack, phone number for WhatsApp)
- `timestamp`, `subject`, `body` (sanitized), `raw_payload` (original fields, for audit)
- `injection_flagged` — carried through to the orchestrator (Phase 3 decides quarantine)
- `received_at` — gateway arrival time (defaults to `datetime.now(timezone.utc)`)

### Identity resolution design

`IdentityResolver.resolve()` takes `(channel, external_id, config)` and iterates all tenants' contact lists looking for an exact `(channel, external_id)` match. This is config-only (no DB query). The DB `Contact` table exists for runtime snapshots in later phases; it is not authoritative for identity verification.

This design avoids the cross-tenant query problem: searching the DB by `external_id` alone would require a full-table scan across all tenants, creating a potential information-disclosure risk. Config lookup is O(N×C) where N is tenants and C is contacts per tenant — acceptable for the prototype scale.

`ContactNotVerifiedError` carries `channel` and `external_id` attributes so callers can log the violation without exposing contact details in the HTTP response body.

### Security guard design

**`SignatureVerifier`**
- `verify(tenant_secret, payload_bytes, signature_header)` — raises `SignatureVerificationError` if the header lacks the `sha256=` prefix, if the hex is malformed, or if the HMAC does not match. Uses `hmac.compare_digest` to prevent timing attacks.
- `compute(tenant_secret, payload_bytes)` — helper for test signature generation.

**`ReplayGuardService`**
- `check_and_record(event_id, timestamp)` — timestamp tolerance is checked BEFORE the DB lookup. Stale events are rejected without being recorded, so a retry with a corrected timestamp would succeed rather than producing a false 409.
- Backed by `ReplayGuardRepository` which stores only `(event_id, received_at)`. No tenant scope — event IDs are globally unique across tenants.
- Tolerance configured via `REPLAY_TOLERANCE_SECONDS` env var (default 300 s).

**`InjectionGuard`**
- Scans text against 9 compiled regex patterns: `ignore-instructions`, `system-prompt`, `inst-tag`, `im-start-tag`, `im-end-tag`, `forget-training`, `jailbreak`, `dan-mode`, `disregard-previous`.
- Returns `InjectionResult(flagged, matched_pattern, sanitized_text)`. Never raises; never rejects the event.
- When flagged, `sanitized_text` replaces the original body with `[MESSAGE WITHHELD — potential prompt injection pattern detected]`. The original text is preserved in `raw_payload` for audit purposes.

**`redact(text: str) → str`**
- Applied before any text reaches a log sink or outbound message. Covers: `password=`, `api_key=`, Bearer tokens, `sk-` prefixed keys, `ghp_` GitHub tokens, `AKIA` AWS access keys, and generic `secret=`/`token=` patterns.

### Test strategy

- **Unit tests** (`test_adapters.py`, `test_security.py`, `test_identity_resolver.py`): pure functions and services, no HTTP, no DB. Injected dependencies only.
- **Integration tests** (`test_webhook_endpoints.py`): full FastAPI TestClient with `get_db` overridden to an in-memory SQLite using `StaticPool`. `StaticPool` ensures all sessions within a test share one connection (and one in-memory database), preventing the "no such table" failure that occurs when the default pool hands out a fresh connection to each request.

---

## 12. Classifier and Orchestrator Design (Phase 3)

### Interaction Classifier

`InteractionClassifier` (`app/agents/classifier.py`) is a fully deterministic, rule-based component — no LLM or external I/O.

**Category enum**

| Value | Meaning |
|---|---|
| `incident` | An active service failure, outage, or degradation |
| `question` | A "how do I" or informational enquiry |
| `follow_up` | A status check on a previous request |
| `noise` | A greeting, test message, or otherwise content-free text |
| `low_confidence` | Classifier cannot reliably assign any of the above |

**ClassificationResult fields**

| Field | Type | Description |
|---|---|---|
| `category` | `Category` | Winning category (or `low_confidence`) |
| `severity` | `str` | P1 / P2 / P3 / P4 |
| `component` | `str` | Matched component id from config, or `"unknown"` |
| `confidence_score` | `float` | 0.0–1.0; highest accumulated pattern score |
| `reasoning` | `str` | Human-readable explanation of the decision |

**Scoring approach**

Each category accumulates a score from weighted regex patterns. The score for a single category is capped at 1.0. The category with the highest score wins. If the winning score is below `CONFIDENCE_THRESHOLD` (0.35), the result is `LOW_CONFIDENCE`. A `LOW_CONFIDENCE` result is explicit, carries its own reasoning string, and is guaranteed to route to Tier 2 by the orchestrator.

**Severity detection**

Incident events are further classified into P1–P4 using a separate set of severity patterns checked in priority order. Questions, noise, and follow-ups are always P4. The default severity for incidents without a strong severity signal is P4.

**Component detection**

Component IDs are matched by regex against the combined subject + body text. The first matching component from the ordered `_COMPONENT_PATTERNS` list wins. When `AppConfig` is provided, the matched ID is validated against the loaded `components.yaml` list; only IDs that appear in config are returned. Unmatched → `"unknown"`.

**Human-request detection**

`check_human_requested(event)` scans subject + body for explicit requests for a human agent (e.g. "speak to a human", "connect me with a person", "I need a live agent"). This check runs inside the orchestrator before routing and overrides category-based routing.

### Support Orchestrator

`SupportOrchestrator` (`app/agents/orchestrator.py`) is the Phase 3 entry point for a validated `InboundEvent`.

**Processing pipeline**

1. Call `InteractionClassifier.classify(event)` → `ClassificationResult`.
2. Write `classification_completed` audit event via `AuditRepository`.
3. Run routing decision (`_route`):
   - `injection_flagged=True` → Tier 2, reason `"injection_flagged"`.
   - Human request detected → Tier 2, reason `"customer_requested_human"`.
   - Category is `LOW_CONFIDENCE` → Tier 2, reason `"low_confidence"`.
   - Category not in `{incident, question, follow_up, noise}` → Tier 2, reason `"unknown_category"`.
   - Otherwise → Tier 1, reason = category value.
4. For Tier 1 + category in `{incident, question}`: create a ticket via `TicketManager`.
5. Write `routing_decision` audit event.
6. Return `OrchestratorResult(action, reason, classification, ticket_id)`.

**Ticket creation**

`TicketManager` (`app/services/ticket_manager.py`) wraps `TicketRepository` and creates tickets with `tenant_id` taken directly from the event. Tenant isolation is enforced by `TicketRepository`. `TicketManager` never bypasses the repository layer.

**What is NOT implemented in Phase 3 (now implemented in Phase 4)**

| Component | Phase |
|---|---|
| Diagnostics Collector | 4 ✓ |
| Knowledge Retriever | 4 ✓ |
| First Response Generator | 4 ✓ |
| SLA Tracker | 5 |
| Escalation Engine | 5 |
| Communication Policy | 5 |
| Human Handoff Builder | 6 |

### Test strategy

- **`tests/test_classifier.py`** (36 tests): pure unit tests, no DB or HTTP. Module-scoped `config` and `classifier` fixtures. Covers all 5 categories, severity, component, confidence, reasoning, and human-request detection.
- **`tests/test_orchestrator.py`** (32 tests): integration tests with function-scoped in-memory SQLite (`db_session` fixture). Covers Tier 1/Tier 2 routing, ticket creation, tenant isolation, audit event recording, Phase 4 diagnostics/KB/first-response path, and negative assertions that Phase 5–6 components are absent.

---

## 13a. Diagnostics, Knowledge Retrieval, and First Response Design (Phase 4)

### Diagnostics Collector

`DiagnosticsCollector` (`app/agents/diagnostics_collector.py`) is a stateless, deterministic component. No LLM, no external I/O, no commands executed against infrastructure.

**DiagnosticsResult fields**

| Field | Type | Description |
|---|---|---|
| `fields` | `list[DiagnosticField]` | Extracted structured fields, each with a `DataClassification` tag |
| `missing_required` | `list[str]` | Required field names not present in the extracted set |
| `follow_up_questions` | `list[str]` | Customer-facing questions for each missing field |
| `is_complete` | `bool` | True when all required fields are present |

**Field extraction**

Structural fields (always extracted): `channel` (PUBLIC), `severity` (INTERNAL), `component` (INTERNAL), `subject` (INTERNAL), `body_summary` (INTERNAL).

Pattern-extracted fields (from combined subject + body text):

| Field | Pattern | Classification |
|---|---|---|
| `http_error_code` | 4xx/5xx digit triplet | INTERNAL |
| `ip_address` | IPv4 dotted-decimal | CONFIDENTIAL |
| `bucket_name` | `bucket/<name>` | INTERNAL |
| `cpu_usage_percent` | `cpu … N%` | INTERNAL |
| `memory_usage_percent` | `memory/ram … N%` | INTERNAL |
| `auth_method` | oauth, api_key, saml, sso, bearer, jwt, certificate, ldap | INTERNAL |
| `operation_type` | upload, download, delete, list, get, put, head, copy, move | INTERNAL |

**Required fields per (category, component)**

Only `incident` events have required fields. All other categories (`question`, `follow_up`, `noise`, `low_confidence`) always return `is_complete=True`.

| Component | Required fields |
|---|---|
| api-gateway | http_error_code, affected_endpoint |
| auth-service | error_code (satisfied by http_error_code), auth_method |
| compute-engine | cpu_usage_percent, affected_instance |
| storage-service | bucket_name, operation_type |
| network-service | ip_address |
| billing-service | account_id, billing_period |
| unknown | error_description |

**No-command guarantee**

The collector never calls `subprocess`, `os.system`, `exec()`, or `eval()`. Follow-up questions are phrased in the second person, guiding the customer to run commands themselves.

### Knowledge Retriever

`KnowledgeRetriever` (`app/agents/knowledge_retriever.py`) is a deterministic keyword-, tag-, and component-based retriever. No vector database, no LLM, no live signals.

**Scoring algorithm**

For each article in `config/knowledge/index.yaml`:
- Component match bonus: +0.30 if the event's component is in `article.components`
- Tag match: +0.10 per tag that appears (as whole word or substring) in the query, capped at 0.50
- Final score capped at 1.0

An article is returned as `KBMatch` only if its score meets or exceeds its own `min_confidence`. Otherwise `NoMatchResult` is returned.

**KBMatch fields**

| Field | Description |
|---|---|
| `article_id` | Article ID from index |
| `title` | Article title |
| `file` | Markdown filename |
| `confidence_score` | Score achieved (0.0–1.0) |
| `source_metadata` | Dict with article_id, file, tags, min_confidence |
| `excerpt` | Relevant excerpt from the markdown file |

**Tenant boundary**

KB articles are authoritative Modelyo runbooks (PUBLIC/INTERNAL scope). They contain no customer-specific data, so no per-tenant filter is applied to the article set. Customer ticket history (which IS tenant-scoped) is not a knowledge source in Phase 4 (deferred to Phase 7).

### First Response Generator

`FirstResponseGenerator` (`app/agents/first_response_generator.py`) is a deterministic mock response generator. No LLM.

**Rules**

1. If `kb_result` is `KBMatch`: build a grounded response referencing the article title, article ID, and excerpt. Include a safe-field summary of diagnostics (PUBLIC and INTERNAL only).
2. If `kb_result` is `NoMatchResult`: return the safe fallback response. No technical guidance is invented.
3. `redact()` is applied to all response text before returning (covers passwords, API keys, Bearer tokens, sk- keys, GitHub tokens, AWS keys, generic secret= patterns).
4. CONFIDENTIAL and RESTRICTED diagnostic fields are never included in response text.

**FirstResponse fields**

| Field | Description |
|---|---|
| `response_text` | Redacted customer-facing text |
| `kb_article_id` | Article ID used, or None for fallback |
| `kb_article_title` | Article title, or None for fallback |
| `is_fallback` | True when no KB match was found |
| `source_metadata` | Forwarded from KBMatch, or empty dict for fallback |

### Orchestrator Phase 4 extension

The Tier 1 path for `incident` and `question` events is extended after ticket creation:

1. **Diagnostics collection** — `DiagnosticsCollector.collect(event, classification)` → `DiagnosticsResult`
2. **Incomplete diagnostics** — if `is_complete=False`: set `follow_up_questions` in result; skip KB retrieval; return action=tier1.
3. **KB retrieval** — `KnowledgeRetriever.retrieve(query, classification)` → `KBMatch | NoMatchResult`
4. **KB miss for incidents** — if `NoMatchResult` and category is `INCIDENT`: change action to tier2, reason="no_kb_match". Questions with no KB match stay tier1.
5. **First response** — if `KBMatch`: `FirstResponseGenerator.generate(...)` → `FirstResponse`; set on result.

`OrchestratorResult` gains three new optional fields: `diagnostics_result`, `first_response`, `follow_up_questions`.

---

## 14. Data Flow

```
Inbound event (JIRA / Slack / WhatsApp)
  └─► Channel Adapter (normalize)                                           Phase 2 ✓
        └─► Security Guards (signature, replay, injection)                  Phase 2 ✓
              └─► Identity Resolver (verify contact, resolve tenant)        Phase 2 ✓
                    └─► Classifier (category, severity, component)          Phase 3 ✓
                          └─► Orchestrator                                  Phase 3 ✓
                                ├─► Ticket Manager (create ticket)          Phase 3 ✓
                                ├─► Diagnostics Collector                   Phase 4 ✓
                                ├─► Knowledge Retriever                     Phase 4 ✓
                                ├─► First Response Generator                Phase 4 ✓
                                │       └─► Comms Policy ──► Customer       Phase 5
                                ├─► SLA Tracker                             Phase 5
                                └─► Escalation Engine ──► On-call contacts  Phase 5
```

---

## 14. PRD Coverage and Prototype Scope Exclusions

> Added 2026-05-10 following PRD alignment review against `docs/source/PRD.md` (version 0.1, 2026-05-02).

### PRD Requirements Covered by Each Phase

| Phase | PRD Requirements Satisfied |
|---|---|
| 1A–1B | Config load, fail-fast startup |
| 1C | NFR-01, NFR-02 (tenant isolation at storage layer), NFR-04 (data classification), NFR-05, NFR-06 (tamper-evident audit trail) |
| 2 | FR-01–FR-04 (channel intake, identity verification), NFR-08 (signature + replay), NFR-09 (injection guard), NFR-10 (secret redaction), IR-05–IR-07 |
| 3 | FR-05 (classify interactions; low-confidence → Tier 2) |
| 4 | FR-08, FR-09, FR-11 (diagnostics collection; no infra commands), FR-12, FR-13, FR-14 (first response grounded in KB; fallback), FR-26, FR-27, FR-28 (KB retrieval; live signals excluded; tenant boundaries), NFR-13 (graceful degradation via fallback route) |
| 5 | FR-15, FR-17 (engineer notification, notified-vs-engaged state), FR-16 (SLA timer), FR-18 (escalation on breach), FR-19, FR-20 (configurable chain, escalation audit), FR-21–FR-23 (communication policy, quiet hours, cooldown) |
| 6 | FR-24, FR-25 (human handoff packet, handoff at any workflow point) |
| 7 | NFR-07, NFR-14, NFR-15 (telemetry, evaluation framework, regression gating) |

### PRD Requirements Not Covered by This Prototype

The following requirements are in the PRD but are explicitly deferred in this prototype because they require live external integrations that are out of prototype scope:

| PRD Ref | Description | Reason deferred |
|---|---|---|
| FR-06, FR-07 | Guide Slack/WhatsApp contacts through opening a JIRA ticket with all required fields | Requires real JIRA write API and real outbound channel messaging |
| FR-10 | Attach collected diagnostics to the JIRA Service Desk ticket | Prototype stores diagnostics in SQLite only; JIRA attachment requires live integration |
| IR-01 (full) | Handle JIRA ticket lifecycle: comment, status-changed, resolved events | Prototype handles new-ticket webhooks only |
| IR-02, IR-03 | Read/write JIRA fields; thread comments as an identified automated agent | Requires JIRA Service Desk API |
| IR-04 | JIRA permissions scoped strictly per customer | Simulated via SQLite tenant isolation |
| IR-08 | WhatsApp outbound compliance with Business session-window policies | Requires live WhatsApp Business API and Meta-approved templates |
| IR-09, IR-10 | Consume live on-call schedule; receive acknowledgement signals | Simulated by `config/escalation_chains.yaml` |

### PRD Open Decisions (T-xx / D-xx)

The PRD lists 15 Architecture & Design Tasks (T-01 to T-15) and 7 Open Decisions (D-01 to D-07) owned by Modelyo stakeholders. This prototype addresses the following tasks implicitly through design:

- **T-01** (agent decomposition): implemented across `app/agents/`, `app/services/`, `app/adapters/`
- **T-03** (data classification): `DataClassification` enum, `app/db/models.py`
- **T-05** (integration data contracts): `InboundEvent` schema, `app/schemas/events.py`
- **T-06** (webhook security): `SignatureVerifier`, `ReplayGuardService`
- **T-07** (injection mitigation): `InjectionGuard`
- **T-08** (audit trail schema): `AuditEvent` model, `AuditRepository`, hash chain
- **T-10** (escalation chain config): `config/escalation_chains.yaml`
- **T-12** (communication policy): `config/quiet_hours.yaml`

Tasks T-02 (LLM hosting), T-04 (trust boundaries), T-09 (SLA timing model detail), T-11 (canonical state-change list), T-13 (knowledge freshness), T-14 (failure mode behaviors), and T-15 (evaluation framework and latency targets) are design decisions to be finalized before production deployment; their prototype equivalents are simplified stubs.
