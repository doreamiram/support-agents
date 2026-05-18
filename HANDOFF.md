# Modelyo Support Agents - Handoff Document

**Generated:** 2026-05-11  
**Last updated:** 2026-05-17 (Phase 10B complete)
**Status:** Phase 10B complete - 557/557 tests passing; optional real LLM provider added safely behind feature flags; mock remains default fallback

---

## 1. Current Project Status

Phase 10B is **complete** with 557/557 tests passing. Phase 10A's browser demo keeps the Phase 9 static
snapshot fallback and local live backend path through `GET /api/demo/scenarios`.
Phase 10B adds `RealLLMProvider` behind `USE_REAL_LLM=true`, with
`MockLLMProvider` still selected by default and used as the safe fallback for
missing config, timeout, HTTP error, or malformed provider output. No API keys,
new dependencies, `package.json`, schema changes, or live Slack/JIRA/WhatsApp/
PagerDuty integrations were added.

---

## 2. Completed Phases

| Phase | Scope | Test Count | Status |
|---|---|---|---|
| 1A | Skeleton, /health endpoint, README stub, docs stubs | 1 | Complete |
| 1B | Config loader, all YAML configs, Pydantic validation | 41 | Complete |
| 1C | SQLite DB, SQLAlchemy models, repositories, tenant isolation tests, audit hash chain | 76 total | Complete |
| 2 | Channel adapters, identity resolution, security guards | 152 total | Complete |
| 3 | Interaction classifier, support orchestrator, Tier 1/2 routing, ticket creation | 214 total | Complete |
| 4 | Diagnostics collector, knowledge retriever, first response generator | 297 total | Complete |
| 5 | SLA tracker, FakeClock, escalation engine, communication policy, demo endpoint | 382 total | Complete |
| 6 | Handoff builder, audit logger service, /audit/verify endpoint, orchestrator extension | 458 total | Complete |
| **7** | **Demo scenarios, telemetry service, evaluation framework, final documentation** | **512 total** | **Complete** |
| **8** | **LLM readiness layer (`LLMProvider`, `MockLLMProvider`, sanitization, docs)** | **529 total** | **Complete** |
| **9** | **Static Vercel-ready visual web demo (`web-demo/`), regression tests** | **537 total** | **Complete** |
| **10A** | **Live backend-driven web demo endpoint + static fallback** | **549 total** | **Complete** |
| **10B** | **Optional RealLLMProvider + safe demo LLM tasks + provider status UI** | **557 total** | **Complete** |

---

## 3g. Phase 10B Status

**Approved scope:** `app/services/llm_provider.py`,
`app/services/real_llm_provider.py`, `demo/scenarios.py`, `web-demo/`,
`tests/test_llm_provider.py`, `tests/test_api_endpoints.py`,
`tests/test_web_demo_static.py`, `.env.example`, README/HANDOFF/docs updates.

**Code status:** `RealLLMProvider` uses stdlib HTTP only and supports
`demo_summary`, `handoff_summary`, and `customer_response_polish`. Provider
selection defaults to `MockLLMProvider`; real mode requires `USE_REAL_LLM=true`,
`LLM_PROVIDER=generic_http`, `LLM_API_BASE_URL`, `LLM_API_KEY`, and `LLM_MODEL`.
The live demo payload includes browser-safe provider metadata and optional safe
generated content. Current verification is 557/557 tests passing and 5/5 CLI
demo scenarios passing.

**Safety boundaries:** The LLM is not used for routing, security, SLA,
escalation, identity, classification, KB confidence, or prompt-injection
decisions. Demo LLM context is limited to high-level sanitized scenario fields,
status, actions, reasons, PRD labels, trace step names, deterministic handoff
summary fields, and the grounded Tier 1 response preview.

**Confirmations:** No API key committed; no SDK dependency; no package manager
changes; no `app/db/*` or `app/agents/*` changes; no real Slack/JIRA/WhatsApp/
PagerDuty integrations.

---

## 3f. Phase 10A Status

**Approved scope:** `app/main.py`, `demo/scenarios.py`, `web-demo/index.html`,
`web-demo/styles.css`, `web-demo/app.js`, `web-demo/demo-data.json`,
`web-demo/README.md`, `tests/test_api_endpoints.py`,
`tests/test_web_demo_static.py`, and focused documentation updates.

**Code status:** `GET /api/demo/scenarios` runs the existing deterministic demo
flow and returns browser-safe JSON. `web-demo/` has a **Run Live Demo** button,
local backend URL config, status summary, scenario count, Phase 10A test baseline
display, execution traces, and static fallback messaging.

**Confirmations:** No `RealLLMProvider`; no real inference API call; no external
LLM SDK; no credentials; no npm, `package.json`, React, Next.js, Docker, or
deployment automation; no database schema changes; no changes to `app/agents/*`
or `app/db/*`; no real Slack/JIRA/WhatsApp/PagerDuty integrations.

**Local CORS:** FastAPI CORS is limited to `http://localhost:8080` and
`http://127.0.0.1:8080` for the static local demo server only.

---

## 3. Phase 9 Status

**Approved scope:** `web-demo/index.html`, `styles.css`, `app.js`, `demo-data.json`, `web-demo/README.md`, `tests/test_web_demo_static.py`, documentation updates. Presentation layer only; CLI demo `python -m demo.scenarios` unchanged.

**Code status:** 537/537 tests passing. `python -m demo.scenarios`: 5/5 passed.

**Confirmations:** Static assets only; no FastAPI or orchestrator invoked from the web page; no real LLM; no external API calls; no new dependencies; no database schema changes.

---

## 3e. Files Created and Modified in Phase 9

### New files
| File | Purpose |
|---|---|
| `web-demo/index.html` | Static landing page: title, system status, prototype boundary note, card mount points |
| `web-demo/styles.css` | Lightweight responsive styling (no external CSS framework) |
| `web-demo/app.js` | Loads `demo-data.json` via `fetch`; fallback message for `file://` |
| `web-demo/demo-data.json` | Deterministic scenario snapshot (no sensitive payloads) |
| `web-demo/README.md` | Local static server + optional Vercel root-directory instructions |
| `tests/test_web_demo_static.py` | 8 tests: file presence, JSON structure, PASS status, forbidden substrings, HTML messaging, no `package.json` |

### Modified files
| File | Change |
|---|---|
| `README.md` | Phase 9 status, 537 tests, Visual Web Demo section, `web-demo/` in project structure |
| `docs/demo_guide.md` | Optional visual demo; 537-test baseline; interpretation vs CLI |
| `docs/evaluation_framework.md` | Phase 9 scope, 537 baseline, functional row, Section 4 Phase 9 subsection |
| `docs/design_document.md` | Phase 9 banner; Section 17 Visual Web Demo Layer |
| `docs/requirements_traceability.md` | Q-02 -> 537/537 Phase 9; Q-05 static web demo Done |
| `HANDOFF.md` | Phase 9 summary, phase table row, this section |

---

## 3a. Phase 8 Status

**Approved scope:** `LLMProvider` abstraction, `MockLLMProvider`, `LLMRequest` / `LLMResponse`, task validation (`LLMUnsupportedTaskError`), diagnostic sanitization helpers, `tests/test_llm_provider.py`, `docs/llm_integration_notes.md`, documentation and traceability updates. No orchestrator wiring; no database schema changes; no new dependencies.

**Code status:** 529/529 tests passing. `python -m demo.scenarios`: 5/5 passed.

**Confirmations:** No real LLM inference; no external API calls from the new module; no API keys or env-based credentials for inference; deterministic agents remain the source of truth for routing and customer-facing output.

---

## 3b. Phase 7 Status

**Approved scope:** Demo scenarios, telemetry service, evaluation framework, README, demo guide, documentation consistency updates.

**Code status:** All files written and tested. 512/512 tests passing. All documentation updated.

---

## 3c. Files Created and Modified in Phase 8

### New files
| File | Purpose |
|---|---|
| `app/services/llm_provider.py` | `LLMTaskType`, `LLMRequest`, `LLMResponse`, `LLMUnsupportedTaskError`, `LLMProvider` ABC, `MockLLMProvider`, diagnostic sanitization helpers, `merge_safe_context` |
| `tests/test_llm_provider.py` | 17 tests: determinism, task strings, unsupported tasks, sanitization, forbidden substring scan on module source, grounding metadata |
| `docs/llm_integration_notes.md` | PRD alignment, trust boundary, production hosting options, guardrails, how to replace mock with production provider |

### Modified files
| File | Change |
|---|---|
| `README.md` | Phase 8 status, 529 tests, LLM-ready row, architecture line, key design bullets, `docs/llm_integration_notes.md` pointer |
| `docs/design_document.md` | Phase 8 banner; 15 components; Section 16 LLM readiness; evaluation test count 529 |
| `docs/evaluation_framework.md` | Scope Phase 1-8, 529 baseline, checklist rows, Phase 8 test table row, limitations row |
| `docs/requirements_traceability.md` | Q-02 -> 529/529 Phase 8; Q-03 LLM-ready Done; Q-04 real inference Deferred; prototype-deferred intro |
| `docs/demo_guide.md` | Pytest baseline comment updated to 529 tests |
| `HANDOFF.md` | Phase 8 summary, phase table row, this section |

---

## 3d. Phase 6 Status

**Approved scope:** Handoff builder, audit logger service wrapper, `/audit/verify` endpoint, orchestrator extension for structured handoff packets.

**Code status:** All files written and tested. 458/458 tests passing. All documentation updated.

---

## 4. Files Created and Modified in Phase 7

### New files
| File | Purpose |
|---|---|
| `demo/__init__.py` | Demo package marker |
| `demo/scenarios.py` | Five end-to-end demo scenarios; `run_all_scenarios()` runner; `ScenarioResult` dataclass; `_print_results()` for CLI output |
| `app/services/telemetry.py` | `Telemetry` service; `TelemetryEvent` dataclass; closed set of allowed event types; no sensitive data or external provider |
| `tests/test_demo_scenarios.py` | 30 tests: import, required scenarios, runner results, determinism, no-real-integrations, documentation existence |
| `tests/test_telemetry.py` | 21 tests: all event types, unknown type rejection, metadata immutability, safety constraints |
| `docs/demo_guide.md` | Recommended demo script, commands, expected outputs, PRD mapping, how to explain limitations |
| `docs/evaluation_framework.md` | PRD coverage table, functional checklist, security checklist, test counts, known limitations, production next steps |

### Modified files
| File | Change |
|---|---|
| `README.md` | Full project documentation: what it is, problem, scope, architecture, setup, test/demo commands, security notes, production roadmap |
| `tests/test_api_endpoints.py` | Removed `TestPhase7NotImplemented` guard test (demo/scenarios.py now exists) |
| `tests/test_orchestrator.py` | Removed `TestPhase7NotImplemented` guard test |
| `docs/design_document.md` | Phase header updated to 7; Section 15 added (demo scenarios, telemetry, evaluation framework design); PRD coverage table updated; phase list updated |
| `docs/requirements_traceability.md` | O-08, Q-01, Q-02 marked Done with file/test references |
| `HANDOFF.md` | This file |

---

## 4b. Files Created and Modified in Phase 6

### New files
| File | Purpose |
|---|---|
| `app/agents/handoff_builder.py` | `HandoffPacket` dataclass + `HandoffBuilder`; builds structured context packet for Tier 2 / human review; CONFIDENTIAL/RESTRICTED fields excluded |
| `app/services/audit_logger.py` | `AuditLogger` service wrapper around `AuditRepository`; `VerificationResult` dataclass; exposes `append()`, `list_events()`, `verify_chain()` |
| `tests/test_handoff_builder.py` | 40 tests covering all required fields, data classification safety, suggested_next_action, handoff reason scenarios, attempted steps |
| `tests/test_audit_logger.py` | 24 tests covering append, list_events, verify_chain, tampering detection, payload non-exposure |

### Modified files
| File | Change |
|---|---|
| `app/agents/orchestrator.py` | Added `HandoffBuilder` import; `handoff_packet: Optional[HandoffPacket]` on `OrchestratorResult`; `_handoff_builder` private instance attribute; handoff built for all Tier 2 outcomes |
| `app/main.py` | Added `GET /audit/verify` endpoint; accepts optional `tenant_id`; verifies single tenant or all configured tenants; no payload content exposed |
| `tests/test_api_endpoints.py` | Replaced `TestPhase6NotImplemented` with `TestAuditVerify` (13 tests); added `TestPhase7NotImplemented` (1 test) |
| `tests/test_orchestrator.py` | Replaced `TestPhase6NotImplemented` with `TestPhase6HandoffIntegration` (10 tests) + `TestPhase7NotImplemented` (1 test); added `HandoffPacket` import |
| `docs/design_document.md` | Phase header updated to 6; Section 13c added (handoff builder, audit logger, /audit/verify design); data flow diagram updated; PRD coverage table updated |
| `docs/requirements_traceability.md` | F-22, O-05, O-06, S-08 marked Done |
| `HANDOFF.md` | This file |

---

## 4b. Files Created and Modified in Phase 5

### New files
| File | Purpose |
|---|---|
| `app/utils/clock.py` | `ClockProvider` (abstract), `SystemClock` (production), `FakeClock` (tests/demo); `FakeClock.advance(minutes, hours)` |
| `app/agents/sla_tracker.py` | `SLATracker`, `SLAStatus`; state machine OPEN -> ENGINEER_NOTIFIED -> ACKNOWLEDGED -> RESOLVED/BREACHED; breach detection via ClockProvider; persists to `SLAStateRepository` |
| `app/agents/escalation_engine.py` | `EscalationEngine`, `EscalationResult`, `EscalationAction`; configurable chain lookup (component-specific first, then wildcard); simulated contacts; audit event per escalation |
| `app/services/communication_policy.py` | `CommunicationPolicy`, `CommDecision`; quiet hours via static UTC offset table; cooldown enforcement; P1 critical override; tenant-scoped rules from `quiet_hours.yaml` |
| `tests/test_clock.py` | 17 tests for ClockProvider, SystemClock, FakeClock |
| `tests/test_sla_tracker.py` | 26 tests: SLA initialization, breach detection with FakeClock, engineer-notified vs engineer-engaged distinction |
| `tests/test_escalation_engine.py` | 15 tests: chain selection, simulated actions, audit event recording |
| `tests/test_communication_policy.py` | 16 tests: quiet hours suppress, P1 critical override, cooldown, no-config fallback |

### Modified files
| File | Change |
|---|---|
| `app/agents/orchestrator.py` | Added optional `clock: ClockProvider` param; private `_sla_tracker`, `_escalation_engine`, `_communication_policy` instance attributes; SLA initialized for incident tickets; comm policy gates first-response generation; escalation fired on breach; `OrchestratorResult` extended with `sla_status`, `escalation_result`, `comm_decision` |
| `app/main.py` | Added `POST /demo/advance-time` endpoint; gated by `DEMO_MODE=true` at request time; advances module-level `FakeClock`; returns 404 if not in demo mode |
| `tests/test_api_endpoints.py` | Added `TestDemoAdvanceTime` (8 tests) and `TestPhase6NotImplemented` (1 test) |
| `tests/test_orchestrator.py` | Removed 3 now-obsolete Phase 5 negative tests; added `TestPhase5SLAIntegration` (5 tests); renamed negative class to `TestPhase6NotImplemented`; updated module docstring |
| `docs/design_document.md` | Phase header updated to 5; Section 13b added (SLA/escalation/comms/demo design); data flow diagram updated; PRD coverage table updated |
| `docs/requirements_traceability.md` | F-16 through F-27, O-03, O-04 marked Done |
| `HANDOFF.md` | This file |

---

## 5. Tests Created in Phase 7

### `tests/test_demo_scenarios.py` (30 tests)
- `TestDemoScenariosImport` (4): demo module importable; no real LLM library; `run_all_scenarios` callable; `ScenarioResult` class exists
- `TestRequiredScenarios` (6): 5 scenarios in `_SCENARIOS`; all 5 scenario functions exist by name
- `TestScenarioResults` (6): runner returns list of 5; every result has name, passed bool, summary; all scenarios pass
- `TestDeterminism` (2): two consecutive runs produce identical outcomes; FakeClock confirmed (no breach at T=0, breach at T+20)
- `TestNoRealIntegrations` (5): no slack_sdk, jira, twilio in sys.modules; sqlite:///:memory: in source; no outbound HTTP
- `TestDocumentationExists` (7): README exists + mentions pytest + mentions scenarios; demo_guide.md exists + mentions scenario command; evaluation_framework.md exists + mentions PRD + mentions limitations

### `tests/test_telemetry.py` (21 tests)
- `TestTelemetryBasic` (5): instantiation, record known type, initially empty, multiple events, zero count for absent type
- `TestTelemetryEventTypes` (11): all 8 allowed event types recordable; unknown type raises ValueError; record without metadata succeeds
- `TestTelemetrySafety` (9): metadata copied not shared; events() returns copy; no raw payload event type is allowed; no `payload`/`customer_data` in event names; summary returns correct counts; events have ISO timestamps; events are TelemetryEvent instances; multiple records of same type accumulate

### Removed guard tests (net -2)
- Removed `TestPhase7NotImplemented` (1) from `tests/test_api_endpoints.py`
- Removed `TestPhase7NotImplemented` (1) from `tests/test_orchestrator.py`

---

## 5b. Tests Created in Phase 6

### `tests/test_handoff_builder.py` (40 tests)
- `TestHandoffPacketFields` (13): all required fields present (tenant_id, ticket_id, handoff_reason, channel, contact_id, customer_goal, classification fields, routing fields, attempted_steps, diagnostics_summary, suggested_next_action, created_at); packet is HandoffPacket instance
- `TestHandoffDataClassification` (5): ip_address (CONFIDENTIAL) excluded from diagnostics_summary; RESTRICTED fields excluded; PUBLIC channel field included; INTERNAL severity included; CONFIDENTIAL value not in any top-level string field
- `TestSuggestedNextAction` (5): low_confidence mentions contact; injection_flagged mentions injection; customer_requested_human mentions contact; no_kb_match mentions KB/runbook; suggested action non-empty for all reasons
- `TestHandoffReasonScenarios` (7): low_confidence packet correct; customer_requested_human packet correct; no_kb_match packet with KB and step coverage; injection_flagged packet correct; SLA fields present when SLA status given; SLA fields None when not available
- `TestAttemptedSteps` (2): early Tier 2 has only classification step; no_kb_match has diagnostics + KB + SLA steps

### `tests/test_audit_logger.py` (24 tests)
- `TestAuditLoggerAppend` (6): returns AuditEvent; stores event_type, tenant_id, actor; delegates to repository; multiple appends ordered
- `TestAuditLoggerListEvents` (3): empty for unknown tenant; only tenant events returned; insertion order preserved
- `TestAuditLoggerVerifyChain` (11): empty chain valid; event_count zero; no breaks; single event valid; multiple events valid; count matches appended; result has message; result is dataclass; tampering detected; chain_breaks contain description on tampering; result does not expose payload content; different tenants independent

### Updates to `tests/test_api_endpoints.py` (+13 net tests, -1 removed)
- `TestAuditVerify` (13): returns 200 with and without tenant_id; response has valid, event_count, chain_breaks, tenants_verified fields; empty chain is valid (event_count=0); no-tenant_id verifies multiple; payload_json not in response; valid is bool; event_count is int; chain_breaks is list; tenants_verified contains requested tenant
- `TestPhase7NotImplemented` (1): demo/scenarios.py not present - **removed in Phase 7** (see Section 4. Files Created and Modified in Phase 7)

### Updates to `tests/test_orchestrator.py` (+11 net tests, -1 removed)
- `TestPhase6HandoffIntegration` (10): low_confidence has HandoffPacket; customer_requested_human has HandoffPacket; injection_flagged has HandoffPacket; no_kb_match has HandoffPacket; Tier 1 has no HandoffPacket; packet has all required fields; customer_goal matches subject; routing_action is tier2; result has handoff_packet attribute; question Tier 1 result handoff_packet is None
- `TestPhase7NotImplemented` (1): demo/scenarios.py not present - **removed in Phase 7** (see Section 4. Files Created and Modified in Phase 7)

## 5b. Tests Created in Phase 5

### `tests/test_clock.py` (17 tests)
- `TestClockProviderInterface` (3): SystemClock and FakeClock are instances of ClockProvider; `now()` is callable
- `TestSystemClock` (4): returns datetime; timezone-aware; UTC offset zero; non-decreasing across two calls
- `TestFakeClockStart` (4): default start deterministic; custom start returned; same value on repeated calls; timezone-aware
- `TestFakeClockAdvance` (6): advance by minutes; advance by hours; combined; accumulates; zero-advance no-op; deterministic (never reads real time)

### `tests/test_sla_tracker.py` (26 tests)
- `TestSLAInitialization` (10): returns SLAStatus; state=OPEN; no breach flags; engineer flags false; P1/P2 response and resolution deadlines; DB record created; get_status returns snapshot; unknown ticket returns None
- `TestSLABreachDetection` (7): no breach before deadline; response and resolution breach after deadline; state=BREACHED on breach; P2 deadline respected; check_breach on unknown ticket raises ValueError
- `TestEngineerNotifiedVsEngaged` (9): mark_notified sets notified only; state=ENGINEER_NOTIFIED; mark_engaged sets both flags; state=ACKNOWLEDGED; notified/engaged are distinct transitions; response not breached after engagement; mark_resolved sets RESOLVED; resolved ticket not re-evaluated

### `tests/test_escalation_engine.py` (15 tests)
- `TestEscalationChainSelection` (6): component-specific preferred over wildcard; wildcard used as fallback; no chain for unknown tenant; vertex tenant uses vertex contacts; different tenants have different contacts; P3 wildcard found
- `TestSimulatedActions` (6): all actions simulated=True; fired in configured step order; delay_minutes matches config; would_fire_at = triggered_at + delay; reason propagated; contact_method and address present
- `TestEscalationAudit` (3): audit event recorded; payload contains ticket_id and simulated=True; no-chain scenario still records audit

### `tests/test_communication_policy.py` (16 tests)
- `TestQuietHoursSuppress` (5): non-critical suppressed during quiet hours; allowed during business hours; P3 suppressed; reason string non-empty; Vertex different timezone/window
- `TestCriticalOverride` (4): P1 bypasses quiet hours; reason contains "critical_override"; suppressed_by is None; P2 not overridden
- `TestCooldown` (5): suppressed within cooldown window; allowed after full window; exact boundary allowed (strict less-than); no cooldown without last_message; Vertex longer cooldown
- `TestNoConfigFallback` (2): unknown tenant always allowed; CommDecision is a dataclass with correct fields

### Updates to `tests/test_api_endpoints.py` (+9 net tests)
- `TestDemoAdvanceTime` (8): 404 without DEMO_MODE; 404 with DEMO_MODE=false; 200 with DEMO_MODE=true; `now` field present; `advanced_minutes` echoed; `advanced_hours` echoed; `now` is parseable ISO-8601; case-insensitive DEMO_MODE check
- `TestPhase6NotImplemented` (1): `/audit/verify` returns 404

### Updates to `tests/test_orchestrator.py` (+2 net tests)
- `TestPhase5SLAIntegration` (5 tests): incident result has sla_status; it's an SLAStatus instance; DB record created; question does not initialize SLA; result has all Phase 5 fields
- Removed: 3 now-obsolete Phase 5 negative tests (test_no_sla_tracking, test_no_escalation, test_no_communication_policy)
- `TestPhase6NotImplemented` (1, unchanged): test_no_handoff_builder

---

## 6. Test Results

| Phase | Tests | Result |
|---|---|---|
| 1A | 1 | 1/1 passed |
| 1B | 41 | 41/41 passed |
| 1C | 76 total | 76/76 passed |
| 2 | ~76 new | 152/152 passed |
| 3 | 62 new | 214/214 passed |
| 4 | 83 new | 297/297 passed |
| 5 | 85 new | 382/382 passed |
| 6 | 76 new | 458/458 passed |
| **7** | **54 net new** | **512/512 passed** |

---

## 7. Important Architecture Decisions (Phase 7 additions)

### Demo scenarios use private orchestrator attributes for SLA time-travel
Scenario 4 (SLA escalation) calls `orch._sla_tracker.check_breach()` and
`orch._escalation_engine.escalate()` directly to demonstrate breach detection
after FakeClock advancement.  These are private attributes (by convention) but
accessible in Python.  This is intentional for demo purposes only - production
code should not access private orchestrator internals.

### Telemetry is closed, not open
`Telemetry.record()` raises `ValueError` for any unknown event type.  This
prevents accidental logging of raw payloads or sensitive data by code that
imports the class without knowing the allowed set.  New event types must be
explicitly added to `_ALLOWED_EVENT_TYPES`.

### Demo clock fixed to business-hours UTC for comm policy
Scenarios 1 and 5 use `FakeClock(start=datetime(2026, 1, 5, 14, 0, 0, UTC))`
so that the communication policy (acme-corp quiet hours: 22:00-08:00 Eastern)
allows the first response to be generated.  14:00 UTC = 09:00 Eastern on Monday,
inside business hours.

### Scenarios 3 and 4 use the default FakeClock start (09:00 UTC)
Scenarios 2, 3, and 4 do not need comm policy to allow messages (Scenario 2
has no ticket, Scenario 3 routes to Tier 2 before first response, Scenario 4
has incomplete diagnostics so first response is never attempted).  Default
FakeClock is used.

---

## 7b. Important Architecture Decisions (Phase 6 additions)

### HandoffPacket built after all processing, not at first Tier 2 decision
The handoff packet is built at the END of `process()` after the final `action` value is known. This means a Tier 1 event that later becomes Tier 2 (e.g., `no_kb_match` after diagnostics/KB retrieval) still gets a fully populated packet including diagnostics, KB outcome, and SLA state.

### CONFIDENTIAL/RESTRICTED exclusion is enforced at the builder layer, not the orchestrator
`HandoffBuilder._SAFE_CLASSIFICATIONS` is a frozenset containing only `PUBLIC` and `INTERNAL`. The builder iterates `DiagnosticsResult.fields` and skips any field whose `.classification` is not in this set. This makes the exclusion rule explicit and independently testable.

### AuditLogger does not own its own DB session
`AuditLogger.__init__` accepts an injected `Session` (same as `AuditRepository`). This keeps the service stateless and allows it to participate in the same transaction as other repository operations without requiring a separate connection.

### /audit/verify never returns payload content
The endpoint returns only: `valid`, `event_count`, `chain_breaks`, `tenants_verified`. The `chain_breaks` list contains only positional/structural descriptions (e.g. "Chain break at position 2 - hash mismatch"), not payload values. Raw `AuditEvent.payload_json` content is never included in the HTTP response.

### Phase 7 guard tests removed from both test files
`TestPhase7NotImplemented` was present in both `tests/test_orchestrator.py` and `tests/test_api_endpoints.py` during Phase 6 as a scope guard. Both were removed in Phase 7 when `demo/scenarios.py` was created.

---

## 7b. Important Architecture Decisions (Phase 5 additions)

### ClockProvider abstraction
All time operations in Phase 5 code go through the injected `ClockProvider`. Neither `SLATracker`, `EscalationEngine`, nor `CommunicationPolicy` call `datetime.utcnow()` or `datetime.now()` directly. This makes all SLA breach tests deterministic (no real-time waiting) and enables demo time travel without any actual sleeping.

### Private attributes prevent negative assertion breakage
Phase 5 agents are stored as `_sla_tracker`, `_escalation_engine`, and `_communication_policy` - private instance attributes (set in `__init__`, not as class variables). Python's `hasattr(SupportOrchestrator, "sla_tracker")` only finds class-level names; instance attributes are invisible. This allows the Phase 5 orchestrator extension to coexist with clean separation between phase assertions.

### Timezone handling without tzdata
The `CommunicationPolicy` uses a static `_UTC_OFFSET_MINUTES` lookup table for IANA timezone names (e.g., `"America/New_York": -300`). This avoids a runtime dependency on `tzdata` (not installed) or `pytz` (not available). DST is not modelled - acceptable for a prototype. Tests use carefully chosen UTC times that map correctly to local-time windows using the static offsets.

### Quiet hours overnight windows
The quiet hours check correctly handles overnight windows (e.g., 22:00-08:00) by detecting when `start_minutes > end_minutes` and evaluating the two sub-ranges (current >= start OR current < end).

### Escalation always records audit
Even when no escalation chain is found (unknown tenant, unconfigured severity), `EscalationEngine.escalate()` writes an `escalation_triggered` audit event with `chain_found=False`. This ensures all escalation attempts are observable regardless of outcome.

### SLA initialized before KB routing change
In the orchestrator, SLA is initialized immediately after ticket creation (before KB retrieval). This means incidents that later route to Tier 2 due to `no_kb_match` still have SLA tracking active. SLA continuation for Tier 2-routed incidents is correct by design.

### Demo clock is separate from orchestrator clock
The module-level `_demo_clock` in `app/main.py` is a display-only FakeClock for the demo endpoint. It does not feed into any SLATracker or EscalationEngine instance. Demo scenarios wire FakeClock directly into the orchestrator for deterministic SLA testing - implemented in `demo/scenarios.py` (Phase 7).

---

## 8. PRD Alignment (Phase 7)

Phase 7 satisfies:
- **NFR-07** (operational telemetry): `Telemetry` service records classification, handoff, SLA, and escalation events at prototype scope
- **NFR-14** (measurable behaviour): `Telemetry.summary()` provides per-event-type counts; demo scenarios produce a structured pass/fail report
- **NFR-15** (regression-detectable): 537-test pytest suite with full coverage of all core behaviours; all passing (includes Phase 8 LLM readiness and Phase 9 static web-demo tests)

---

## 8b. Known Issues and Unfinished Tasks

1. **`follow_up` ticket update not implemented** - For follow-up events the orchestrator routes Tier 1 but does not update any existing ticket.
2. **Diagnostics not persisted to DB** - `DiagnosticRepository` exists (Phase 1C) but the orchestrator does not save extracted diagnostic fields to DB. Deferred.
3. **`affected_endpoint` and `affected_instance` not extractable** - These required fields for `api-gateway` and `compute-engine` incidents have no regex extraction pattern. Intentional.
4. **SLA deadline not persisted to Ticket columns** - `Ticket.sla_deadline_response` and `Ticket.sla_deadline_resolution` remain NULL; deadlines are held in-memory in `SLATracker._states`. Adequate for the prototype; a production system would persist these for crash recovery.
5. **Demo clock disconnected from SLA clock** - `/demo/advance-time` advances a standalone FakeClock that is not wired to any orchestrator instance. Phase 7 demo scenarios will wire them together.
6. **DST not modelled in CommunicationPolicy** - Static UTC offsets are used instead of IANA timezone data. Acceptable for prototype with deterministic FakeClock tests.

---

## 9. PRD Alignment (Phase 6)

Phase 6 satisfies:
- **FR-24** (structured context packet: customer goal, attempts, diagnostics, SLA state, suggested next action): `HandoffBuilder` + `HandoffPacket`
- **FR-25** (handoff at any workflow point: low-confidence, injection flagged, customer request, no KB match, unknown category): all Tier 2 routing outcomes trigger handoff
- **NFR-03, NFR-04** (confidentiality, data classification): CONFIDENTIAL/RESTRICTED fields excluded from `HandoffPacket.diagnostics_summary`
- **NFR-05, NFR-06** (audit trail tamper-evident + API-accessible): `AuditLogger.verify_chain()` + `GET /audit/verify`

---

## 9b. PRD Alignment (Phase 5)

Phase 5 satisfies:
- **FR-15** (engineer notification): simulated via EscalationEngine
- **FR-16** (SLA timer from first contact, severity-based): `SLATracker.initialize()` from `sla_rules.yaml`
- **FR-17** (notified vs. engaged distinction): `engineer_notified` and `engineer_engaged` tracked separately
- **FR-18** (escalation on SLA timer expiry): `check_breach()` -> `escalation_engine.escalate()`
- **FR-19** (configurable chain by severity x component): `EscalationEngine._find_chain()` with component-specific priority
- **FR-20** (escalation audit): `escalation_triggered` audit event on every call
- **FR-21, FR-22** (proactive comms on state changes only; no unsolicited pings): `CommunicationPolicy` gates first-response generation
- **FR-23** (quiet hours, cooldown, Sev-1 override): fully implemented in `CommunicationPolicy`

---

## 10. Exact Next Recommended Step

**Phase 10B is complete and verified.** The prototype includes a live backend-driven web demo, an optional `RealLLMProvider` behind feature flags, `MockLLMProvider` as the default fallback, and 557/557 tests passing. It is ready for Modelyo review.

To evaluate the prototype:

```powershell
cd c:\modelyo-support-agents

# Run all 557/557 tests
.\.venv\Scripts\pytest.exe -q

# Run the demo
.\.venv\Scripts\python.exe -m demo.scenarios

# Optional: static visual demo (from web-demo/)
cd web-demo
python -m http.server 8080

# Optional: live backend
cd c:\modelyo-support-agents
uvicorn app.main:app --reload
```

See `docs/demo_guide.md` for a full walkthrough, `docs/llm_integration_notes.md` for LLM production extension guidance, `web-demo/README.md` for the visual layer, and `docs/evaluation_framework.md`
for the PRD coverage checklist.

For production next steps, see Section 6 of `docs/evaluation_framework.md`.
