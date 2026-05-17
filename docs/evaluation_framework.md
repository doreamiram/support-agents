# Modelyo Support Agents — Evaluation Framework

> **Purpose:** Provide Modelyo with a structured checklist for evaluating this
> prototype against the PRD requirements (version 0.1, 2026-05-02).
>
> **Scope:** Phase 1 through Phase 10B of the prototype implementation.  
> **Current Phase 10B baseline:** 557/557 tests passing.

---

## 1. PRD Coverage Summary

### Functional Requirements

| PRD Ref | Description | Status |
|---|---|---|
| FR-01 | Monitor JIRA Service Desk for new tickets | Simulated via webhook adapter |
| FR-02 | Monitor Slack channels for customer messages | Simulated via webhook adapter |
| FR-03 | Handle inbound WhatsApp messages | Simulated via webhook adapter |
| FR-04 | Verify identity of every inbound contact | Done — IdentityResolver (config-based) |
| FR-05 | Classify interactions; low-confidence defers to human | Done — InteractionClassifier |
| FR-06 | Guide non-JIRA contacts through opening a JIRA ticket | Prototype-deferred (real JIRA write required) |
| FR-07 | Validate customer-provided ticket fields | Prototype-deferred |
| FR-08 | Guide customer through diagnostic steps from runbooks | Done — DiagnosticsCollector |
| FR-09 | Validate diagnostic completeness; request missing items | Done — DiagnosticsCollector |
| FR-10 | Attach collected diagnostics to JIRA ticket | Prototype-deferred (JIRA write required) |
| FR-11 | Never execute commands against customer infrastructure | Done — DiagnosticsCollector (guide only) |
| FR-12 | Generate first response: acknowledgement + KB + next steps | Done — FirstResponseGenerator |
| FR-13 | Every claim traceable to authoritative source | Done — KB-grounded responses only |
| FR-14 | Fallback when no confident answer; indicate engineer engaged | Done — FirstResponseGenerator |
| FR-15 | Notify engineer on duty when incident logged | Simulated — EscalationEngine |
| FR-16 | Track SLA timer per incident; severity-based targets | Done — SLATracker + sla_rules.yaml |
| FR-17 | Distinguish engineer-notified from engineer-engaged | Done — SLATracker state machine |
| FR-18 | Escalate when SLA timer expires | Done — EscalationEngine on breach |
| FR-19 | Configurable escalation chain by severity × component | Done — escalation_chains.yaml |
| FR-20 | Every escalation event auditable | Done — audit event per escalation call |
| FR-21 | Inform customer on meaningful state changes only | Done — CommunicationPolicy |
| FR-22 | No unsolicited customer messages | Done — CommunicationPolicy |
| FR-23 | Quiet hours, cooldown, Sev-1 override | Done — quiet_hours.yaml + CommunicationPolicy |
| FR-24 | Structured handoff packet: goal, attempts, diagnostics, SLA, next action | Done — HandoffBuilder |
| FR-25 | Handoff at any workflow point | Done — Orchestrator Tier 2 routing |
| FR-26 | Use internal runbooks/KB as authoritative source | Done — KnowledgeRetriever |
| FR-27 | Live system signals excluded from v1 knowledge | Done — static KB only |
| FR-28 | KB retrieval respects tenant boundaries | Done — runbooks are PUBLIC/INTERNAL scope |

### Non-Functional Requirements

| PRD Ref | Description | Status |
|---|---|---|
| NFR-01 | Customer data isolated across tenants | Done — repository-layer enforcement |
| NFR-02 | Tenant scoping at storage layer, not only application layer | Done — all queries filter by tenant_id |
| NFR-03 | Respect Modelyo confidential-computing posture | Done — data classification + CONFIDENTIAL/RESTRICTED exclusion |
| NFR-04 | Data classification scheme and handling rules defined | Done — DataClassification enum |
| NFR-05 | Every action recorded in audit trail | Done — AuditRepository + AuditLogger |
| NFR-06 | Tamper-evident, immutable, per-tenant audit trail | Done — SHA-256 hash chain, /audit/verify |
| NFR-07 | Operational telemetry for monitoring and quality | Done — Telemetry service (prototype scope) |
| NFR-08 | Webhook signature verification and replay protection | Done — SignatureVerifier + ReplayGuardService |
| NFR-09 | Prompt-injection mitigation | Done — InjectionGuard |
| NFR-10 | No credentials in messages, logs, or agent context | Done — redact() utility |
| NFR-11 | No long-lived credentials in agent memory | Prototype-scoped — config-based only |
| NFR-12 | Latency targets | Not specified (to be agreed; T-15) |
| NFR-13 | Graceful degradation on dependency failure | Done — KB miss → Tier 2 fallback |
| NFR-14 | System behaviour measurable | Done — Telemetry events (prototype) |
| NFR-15 | Regressions detectable before deployment | Done — 537-test suite with coverage of all core behaviours |

### Integration Requirements

| PRD Ref | Description | Status |
|---|---|---|
| IR-01 | Subscribe to JIRA ticket lifecycle events | New-ticket path done; update/resolved deferred |
| IR-02, IR-03 | Read/write JIRA fields; thread comments | Prototype-deferred |
| IR-04 | JIRA permissions scoped per customer | Simulated via SQLite tenant isolation |
| IR-05 | Monitor designated Slack channels | Simulated via webhook adapter |
| IR-06 | Do not act on unverified Slack senders | Done — IdentityResolver |
| IR-07 | Handle WhatsApp inbound from registered numbers | Simulated via webhook adapter |
| IR-08 | WhatsApp outbound compliance | Prototype-deferred (Meta approval required) |
| IR-09 | Consume existing on-call schedule | Simulated via escalation_chains.yaml |
| IR-10 | Notifications acknowledgeable | Simulated — no real ack signal in prototype |
| IR-11 | Ingest runbooks/KB with freshness guarantees | Static KB in prototype; freshness deferred |

---

## 2. Functional Checklist

| Behaviour | Test file | Result |
|---|---|---|
| /health endpoint | test_api_endpoints.py | Pass |
| YAML config loaded and validated at startup | test_config.py | Pass |
| JIRA / Slack / WhatsApp webhook normalization | test_adapters.py, test_webhook_endpoints.py | Pass |
| Signature verification and replay protection | test_security.py, test_webhook_endpoints.py | Pass |
| Prompt-injection guard flags but does not reject | test_security.py | Pass |
| Identity resolver rejects unverified contacts | test_identity_resolver.py | Pass |
| Classifier assigns category / severity / component | test_classifier.py | Pass |
| Orchestrator Tier 1 / Tier 2 routing | test_orchestrator.py | Pass |
| Diagnostics extraction and follow-up questions | test_diagnostics_collector.py | Pass |
| KB retrieval returns match or NoMatchResult | test_knowledge_retriever.py | Pass |
| First response grounded in KB; fallback when no match | test_first_response_generator.py | Pass |
| SLA state machine: OPEN → BREACHED | test_sla_tracker.py | Pass |
| FakeClock.advance() enables SLA breach testing | test_clock.py, test_sla_tracker.py | Pass |
| Escalation chain fires in configured order | test_escalation_engine.py | Pass |
| Communication policy quiet hours + cooldown + override | test_communication_policy.py | Pass |
| HandoffPacket built for all Tier 2 outcomes | test_handoff_builder.py, test_orchestrator.py | Pass |
| AuditLogger verify_chain detects tampering | test_audit_logger.py | Pass |
| /audit/verify endpoint returns structured result | test_api_endpoints.py | Pass |
| All five demo scenarios pass end-to-end | test_demo_scenarios.py | Pass |
| Telemetry records only safe high-level events | test_telemetry.py | Pass |
| LLM provider layer: mock default, optional real provider, fallback, task validation, sanitization | test_llm_provider.py | Pass |
| Static web-demo files and safe demo-data snapshot | test_web_demo_static.py | Pass |

---

## 3. Security Checklist

| Control | File | Test |
|---|---|---|
| Webhook HMAC-SHA256 verification per tenant | app/services/signature_verifier.py | test_security.py::TestSignatureVerifier |
| Replay protection: event_id dedup + timestamp window | app/services/replay_guard.py | test_security.py::TestReplayGuardService |
| Prompt-injection pattern scan; sanitized body only | app/services/injection_guard.py | test_security.py::TestInjectionGuard |
| Secret redaction in logs and outbound text | app/utils/redaction.py | test_security.py::TestRedaction |
| DataClassification on all customer data fields | app/db/models.py | test_db_init.py |
| CONFIDENTIAL/RESTRICTED excluded from first response | app/agents/first_response_generator.py | test_first_response_generator.py |
| CONFIDENTIAL/RESTRICTED excluded from HandoffPacket | app/agents/handoff_builder.py | test_handoff_builder.py::TestHandoffDataClassification |
| Cross-tenant access raises TenantAccessError | app/db/repositories/ | test_tenant_isolation.py |
| /audit/verify never returns raw payload content | app/main.py | test_api_endpoints.py::TestAuditVerify |
| Telemetry records no sensitive payloads | app/services/telemetry.py | test_telemetry.py::TestTelemetrySafety |
| LLMRequest rejects unsupported tasks; no sensitive diagnostics in sanitizer output; real provider payload is sanitized | app/services/llm_provider.py, app/services/real_llm_provider.py | test_llm_provider.py |

---

## 4. Test Coverage Summary

| Phase | New tests | Cumulative | Focus |
|---|---|---|---|
| 1A | 1 | 1 | /health endpoint |
| 1B | 40 | 41 | Config loader, Pydantic models, YAML validation |
| 1C | 35 | 76 | DB init, tenant isolation, audit hash chain |
| 2 | 76 | 152 | Channel adapters, identity resolver, security guards, webhook endpoints |
| 3 | 62 | 214 | Classifier, orchestrator routing, ticket creation |
| 4 | 83 | 297 | Diagnostics, knowledge retriever, first response generator |
| 5 | 85 | 382 | SLA tracker, FakeClock, escalation engine, communication policy |
| 6 | 76 | 458 | HandoffBuilder, AuditLogger, /audit/verify endpoint |
| **7** | **54 net** | **512** | **Demo scenarios, telemetry, documentation presence** |
| **8** | **17 net** | **529** | **LLM provider contract, MockLLMProvider, sanitization, integration notes** |
| **9** | **8 net** | **537** | **Static web-demo (presentation only), regression tests** |
| **10A** | **12 net** | **549** | **Live backend-driven web demo endpoint, local-only CORS, static fallback tests** |
| **10B** | **8 net** | **557** | **Optional RealLLMProvider, safe fallback, demo LLM tasks, provider status UI** |

**557 / 557 tests passing.  No skipped tests.**

### Phase 10A and 10B — Live backend-driven web demo

`web-demo/` remains HTML/CSS/JS with `demo-data.json` as a static fallback, and
now includes a **Run Live Demo** button. The button calls
`GET /api/demo/scenarios` on the local FastAPI backend and renders live scenario
results with safe high-level execution traces. Phase 10B adds `llm_summary`,
safe provider status metadata, Tier 2 `llm_handoff_summary`, and Tier 1
`llm_customer_response_polish` fields.

`tests/test_api_endpoints.py` verifies the endpoint exists, returns five PASS
scenarios, includes allow-listed trace steps, excludes sensitive terms, and only
allows local static-demo CORS origins. `tests/test_web_demo_static.py` verifies
the button, backend URL config, static fallback messaging, trace rendering, LLM
Provider Status panel, safe generated-content rendering, and the continued
absence of `package.json`.

---

## 5. Known Prototype Limitations

The following limitations are intentional for prototype scope and are documented
as deferred requirements in `docs/requirements_traceability.md`.

| Limitation | Impact | Mitigation in prototype |
|---|---|---|
| Optional real LLM limited to demo text | `MockLLMProvider` remains default; deterministic agents and orchestrator unchanged | `RealLLMProvider` is feature-flagged, sanitized, timeout-bound, and fallback-protected |
| No real JIRA write | Tickets stored in SQLite only | Full ticket model defined; JIRA write is a drop-in adapter |
| No real Slack/WhatsApp outbound | Escalation and first response are not delivered | CommunicationPolicy gate + EscalationEngine are fully wired; outbound is a stub |
| SLA deadlines not persisted to Ticket columns | Lost on process restart | SLATracker._states is in-memory (same request lifecycle); production would persist to DB |
| Demo clock disconnected from Orchestrator clock | /demo/advance-time does not affect SLA tracking | Demo scenarios wire FakeClock directly to the Orchestrator |
| DST not modelled in CommunicationPolicy | Fixed UTC offsets for IANA timezones | Acceptable for prototype; IANA tzdata or pytz would fix this in production |
| Knowledge freshness | Static KB files; no ingestion pipeline | Architecture supports adding a freshness layer above KnowledgeRetriever |
| follow_up events do not update existing tickets | Ticket continuity not tracked across interactions | Deferred; requires ticket-thread linkage |
| affected_endpoint and affected_instance not extractable | Diagnostics incomplete for api-gateway and compute-engine | Follow-up questions generated; human engineer provides the missing fields |

---

## 6. Suggested Production Next Steps

Listed in approximate priority order for a production engagement:

1. **Agree LLM hosting model** (PRD T-02 / D-01) — managed API vs. self-hosted
   against Modelyo's confidential-computing trust boundary.

2. **JIRA Service Desk integration** — ticket write, field update, comment
   threading (FR-06, FR-07, FR-10, IR-01–IR-04).

3. **Real channel outbound** — Slack Bot API, WhatsApp Business API with
   Meta-approved templates (IR-05, IR-07, IR-08).

4. **Live on-call integration** — PagerDuty / Opsgenie for real escalation
   delivery and acknowledgement signals (FR-15, IR-09, IR-10).

5. **Knowledge ingestion pipeline** — automated freshness refresh, re-indexing
   on runbook updates, tenant-scoped ticket history retrieval (FR-26–FR-28,
   T-13).

6. **Persistent SLA state** — deadline columns on Ticket rows, crash recovery,
   distributed-clock handling (T-09).

7. **Production database** — PostgreSQL with row-level security; replace SQLite
   ORM configuration only (no schema changes needed).

8. **Secrets management** — vault integration; no credentials in config YAML or
   environment files in production (NFR-11).

9. **Latency targets and performance testing** — agree per-channel response
   time budgets (NFR-12, T-15); instrument with real traces.

10. **Evaluation harness** — labelled test corpus, classification accuracy
    metrics, response groundedness scoring, regression gate on CI (NFR-14,
    NFR-15, T-15).

11. **Acceptance criteria sign-off** (PRD D-07) — structured review of each
    PRD requirement against this prototype's implementation before production
    kickoff.
