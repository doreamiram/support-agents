# Modelyo Support Agents — Handoff Document

**Generated:** 2026-05-10  
**Last updated:** 2026-05-10 (PRD alignment review — docs only, no code changes)  
**Status:** Phase 3 complete — 214/214 tests passing

---

## 1. Current Project Status

Phase 3 is **complete**. All 214 tests pass (152 Phase 1–2 + 62 Phase 3). All documentation updated.

---

## 2. Completed Phases

| Phase | Scope | Test Count | Status |
|---|---|---|---|
| 1A | Skeleton, /health endpoint, README stub, docs stubs | 1 | ✅ Complete |
| 1B | Config loader, all YAML configs, Pydantic validation | 41 | ✅ Complete |
| 1C | SQLite DB, SQLAlchemy models, repositories, tenant isolation tests, audit hash chain | 76 total | ✅ Complete |
| 2 | Channel adapters, identity resolution, security guards | 152 total | ✅ Complete |
| 3 | Interaction classifier, support orchestrator, Tier 1/2 routing, ticket creation | 214 total | ✅ Complete |

---

## 3. Phase 3 Status

**Approved scope:** Interaction classifier, support orchestrator foundation, Tier 1/2 routing decisions, basic ticket workflow using existing repositories.

**Code status:** All files written and tested. 214/214 tests passing. All documentation updated.

---

## 4. Files Created and Modified in Phase 3

### New files
| File | Purpose |
|---|---|
| `app/agents/__init__.py` | Package marker for the agents sub-package |
| `app/agents/classifier.py` | `InteractionClassifier`, `ClassificationResult`, `Category` enum, `check_human_requested()` |
| `app/agents/orchestrator.py` | `SupportOrchestrator`, `OrchestratorResult`; calls classifier, creates tickets, writes audit events |
| `app/services/ticket_manager.py` | `TicketManager`; thin wrapper over `TicketRepository` for tenant-isolated ticket creation |
| `tests/test_classifier.py` | 36 classifier unit tests (pure, no DB/HTTP) |
| `tests/test_orchestrator.py` | 26 orchestrator integration tests (in-memory SQLite via `db_session` fixture) |

### Modified files
| File | Change |
|---|---|
| `app/agents/classifier.py` | Incident patterns — raised `fail` weight to 0.40; added `degraded/slow` pattern (0.35) after initial test run revealed two patterns scored below threshold |
| `docs/design_document.md` | Phase header updated to 3; added Section 12 (Classifier and Orchestrator Design); Section 13 data flow updated with phase annotations |
| `docs/requirements_traceability.md` | F-10, F-11, F-12, F-23 marked Done |
| `HANDOFF.md` | This file |

---

## 5. Tests Created in Phase 3

### `tests/test_classifier.py` (36 tests)
- `TestIncidentClassification` (7): service down, P1 outage, crash, component detection, confidence above threshold, reasoning present, P2 for degraded
- `TestQuestionClassification` (5): how-to, what-is, P4 severity, component detection, confidence above threshold
- `TestFollowUpClassification` (5): re: prefix, "following up" body, "any update" body, P4 severity, confidence above threshold
- `TestNoiseClassification` (5): test, hello, ping, thanks, P4 severity
- `TestLowConfidenceClassification` (5): unrecognised text, unknown subject, score below threshold, reasoning mentions threshold, all fields present
- `TestHumanRequestDetection` (6): speak-to-human, connect-to-person, need-a-human, live-agent, normal incident is not a human request, question is not a human request
- `TestClassifierWithConfig` (3): component IDs validated against config, unknown component returns "unknown", classifier works without config

### `tests/test_orchestrator.py` (26 tests)
- `TestTier1Routing` (8): incident→tier1, incident creates ticket, question→tier1+ticket, noise→tier1 no ticket, follow_up→tier1 no ticket, ticket subject matches, ticket description matches, ticket severity from classification
- `TestTier2Routing` (5): low_confidence→tier2, customer_requests_human→tier2, injection_flagged→tier2, low_confidence has classification, human request takes priority over incident category
- `TestTenantIsolation` (3): ticket tenant_id correct, cross-tenant raises TenantAccessError, list_by_tenant excludes other tenant
- `TestAuditEvents` (3): classification_completed event recorded, routing_decision event recorded, audit events scoped to tenant
- `TestPhase4Plus_NotImplemented` (7): no diagnostics_collector, no knowledge_retrieval, no sla_tracking, no escalation, no handoff_builder, no first_response_generator, no communication_policy

---

## 6. Test Results

| Phase | Tests | Result |
|---|---|---|
| 1A | 1 | ✅ 1/1 passed |
| 1B | 41 | ✅ 41/41 passed |
| 1C | 76 total | ✅ 76/76 passed |
| 2 | ~76 new | ✅ 152/152 passed |
| **3** | **62 new** | **✅ 214/214 passed** |

---

## 7. Important Architecture Decisions (Phase 3 additions)

### Classifier confidence threshold
`CONFIDENCE_THRESHOLD = 0.35`. Below this score the result is always `LOW_CONFIDENCE`, which is an explicit, named category (not a fallback). The orchestrator checks for it specifically and routes to Tier 2.

### Low confidence is a first-class category
`LOW_CONFIDENCE` is a value in the `Category` enum, not a separate flag. This makes it directly testable (`result.category == Category.LOW_CONFIDENCE`) and easily extensible if the threshold or rules change.

### Human-request detection runs before category routing
`check_human_requested()` scans the raw event text before the orchestrator checks the category. This means a high-confidence incident that also requests a human still routes to Tier 2 (`reason = "customer_requested_human"`). The order in `_route()` is: injection_flagged → human_requested → low_confidence → unknown_category → tier1.

### Injection-flagged events route to Tier 2
Events flagged by the Phase 2 injection guard (`InboundEvent.injection_flagged = True`) route to Tier 2 immediately, before classification. The sanitized body is preserved in the event; the orchestrator does not need to re-scan.

### Ticket creation only for incident and question
`follow_up` and `noise` stay Tier 1 but do not create tickets. `follow_up` ticket update (linking to an existing ticket) is deferred to a later phase when the ticket lookup strategy is defined.

### TicketManager is a thin service
`TicketManager` has one method (`create_for_event`) that delegates directly to `TicketRepository.create()`. It does not contain business logic — that lives in the orchestrator. The indirection exists to keep the orchestrator decoupled from the repository layer.

### Audit events use existing AuditRepository
No new audit logger service was introduced. The orchestrator calls `AuditRepository.append()` directly for the two Phase 3 events (`classification_completed`, `routing_decision`). The hash chain is maintained automatically by the repository.

### Config passed to orchestrator, not loaded inside it
`SupportOrchestrator.__init__` accepts `AppConfig` as a parameter. The orchestrator never calls `load_config()` itself. This keeps tests cheap (module-scoped config fixture loaded once) and preserves the fail-fast startup guarantee in `app/main.py`.

---

## 8. Known Issues and Unfinished Tasks

1. **`follow_up` ticket update not implemented** — For follow-up events the orchestrator routes Tier 1 but does not update any existing ticket (no lookup strategy defined yet).
2. **Knowledge base markdown files missing** — `config/knowledge/index.yaml` references `connectivity.md`, `auth_issues.md`, etc. These files will be created in Phase 4.

---

## 9. PRD Alignment Status (reviewed 2026-05-10)

PRD source: `docs/source/PRD.md` version 0.1, 2026-05-02.

**No contradictions found.** The prototype correctly scopes, defers, or stubs every PRD requirement. Key findings:

### Gaps added to RTM as new rows (F-24 through F-30, O-05 through O-08, S-07)

| New RTM row | PRD ref | Status |
|---|---|---|
| F-24 | FR-15 (notify engineer on duty) | Phase 5 — Not started |
| F-25 | FR-17 (notified vs engaged state) | Phase 5 — Not started |
| F-26 | FR-19 (escalation chain severity × component) | Phase 5 — Not started |
| F-27 | FR-20 (escalation events auditable) | Phase 5 — Not started |
| F-28 | FR-06, FR-07 (issue reporting guidance) | Prototype-deferred |
| F-29 | IR-01 full scope, IR-02, IR-03 (JIRA lifecycle) | Prototype-deferred |
| F-30 | FR-10 (attach diagnostics to JIRA ticket) | Prototype-deferred |
| O-05 | NFR-05, NFR-06 (audit logger service, Phase 6) | Phase 6 — Not started |
| O-06 | NFR-06 (/audit/verify API endpoint, Phase 6) | Phase 6 — Not started |
| O-07 | NFR-13 (graceful degradation) | Phase 4 — Not started |
| O-08 | NFR-07, NFR-14 (operational telemetry) | Phase 7 — Not started |
| S-07 | NFR-11 (no long-lived credentials in memory) | Design decision — Prototype-scoped |

### RTM fixes applied
- F-13, F-14, F-15 test references updated to include dedicated Phase 4 test files (`test_diagnostics_collector.py`, `test_knowledge_retriever.py`, `test_first_response_generator.py`).
- Duplicate O-01/O-02 IDs in the Phase 6 rows corrected: renamed to O-05 and O-06 (Phase 6 audit-service wrapper, distinct from the Phase 1C DB-layer rows that remain O-01 and O-02).

### PRD requirements correctly prototype-deferred (no implementation needed)
FR-06, FR-07, FR-10, IR-01 (full), IR-02, IR-03, IR-04, IR-08, IR-09, IR-10 — all require live external integrations outside prototype scope. Full details in `docs/requirements_traceability.md` → Prototype-Deferred Requirements table.

---

## 10. Exact Next Recommended Step

**Phase 4 — Diagnostics, Knowledge Retrieval, First Response:**

Verify baseline first:
```powershell
cd c:\modelyo-support-agents
.\.venv\Scripts\pytest.exe -v
```

Expected: 214/214 still pass. Then implement Phase 4 (approved separately):
- `app/agents/diagnostics_collector.py`
- `app/agents/knowledge_retriever.py`
- `app/agents/first_response_generator.py`
- Knowledge base markdown files under `config/knowledge/`
- Tests for all three components
- Orchestrator extended to call them (Tier 1 path only)
