# Modelyo Support Agents — Requirements Traceability Matrix

> Updated after each implementation phase. Every row maps one requirement to the phase that implements it, the file(s), and the test(s) that verify it.
>
> **PRD alignment note (added 2026-05-10):** PRD requirement IDs (FR-xx, NFR-xx, IR-xx) are noted inline in descriptions where relevant. Rows marked **Prototype-deferred** cover requirements the PRD mandates but that cannot be verified without real external integrations (live JIRA write, on-call API, WhatsApp Business outbound). They are documented here so no PRD requirement is silently dropped.

---

## Legend

| Column | Meaning |
|---|---|
| Req ID | Unique requirement identifier |
| Category | Functional (F), Security (S), Operational (O), Quality (Q) |
| Description | What must be true |
| Phase | Implementation phase (or "Prototype-deferred") |
| File(s) | Source files that satisfy this requirement |
| Test(s) | Test functions or files that verify this requirement |
| Status | Not started / In progress / Done / Deferred |

---

## Matrix

| Req ID | Category | Description | Phase | File(s) | Test(s) | Status |
|---|---|---|---|---|---|---|
| F-01 | F | System exposes a /health endpoint that returns {"status": "ok"} | 1A | app/main.py | tests/test_api_endpoints.py::test_health | Done |
| F-02 | F | All YAML config loaded and validated with Pydantic at startup | 1B | app/config/loader.py, app/config/models.py | tests/test_config.py::TestLoadConfig | Done |
| F-02a | F | App startup fails fast with clear error if any config file is missing | 1B | app/config/loader.py, app/main.py | tests/test_config.py::test_config_load_error_on_missing_directory | Done |
| F-02b | F | Tenants config includes id, name, timezone, webhook_secret, and contacts | 1B | config/tenants.yaml, app/config/models.py | tests/test_config.py::TestTenantModel | Done |
| F-02c | F | quiet_hours.yaml is scoped per tenant with cooldown and critical_override | 1B | config/quiet_hours.yaml, app/config/models.py | tests/test_config.py::TestQuietHoursModel | Done |
| F-02d | F | critical_override: true allows P1 messages to bypass quiet hours (config contract) | 1B | config/quiet_hours.yaml, app/config/models.py | tests/test_config.py::test_critical_override_true_stored_correctly | Done |
| F-02e | F | Escalation chains require tenant_id, severity, and component (FR-19 config foundation) | 1B | config/escalation_chains.yaml, app/config/models.py | tests/test_config.py::TestEscalationChainModel | Done |
| F-02f | F | KB article min_confidence is validated as float in [0.0, 1.0] | 1B | config/knowledge/index.yaml, app/config/models.py | tests/test_config.py::TestKBArticleModel | Done |
| F-03 | F | SQLite DB initialized with all required tables on startup | 1C | app/db/database.py, app/db/models.py | tests/test_db_init.py::TestDBInit | Done |
| F-03a | F | init_db() is idempotent (CREATE TABLE IF NOT EXISTS) | 1C | app/db/database.py | tests/test_db_init.py::test_init_db_is_idempotent | Done |
| F-03b | F | All tenant-scoped tables include tenant_id column | 1C | app/db/models.py | tests/test_db_init.py::test_*_has_tenant_id_column | Done |
| F-03c | F | AuditEvent table includes previous_hash and current_hash columns | 1C | app/db/models.py | tests/test_db_init.py::test_audit_events_has_hash_chain_columns | Done |
| F-03d | F | Diagnostic table includes classification column (DataClassification) | 1C | app/db/models.py | tests/test_db_init.py::test_diagnostics_has_classification_column | Done |
| F-04 | F | Tenant-scoped repositories require tenant_id on every method (NFR-01, NFR-02) | 1C | app/db/repositories/ | tests/test_tenant_isolation.py::TestTicketIsolation | Done |
| F-05 | F | Cross-tenant data access raises TenantAccessError (NFR-01) | 1C | app/db/repositories/, app/db/exceptions.py | tests/test_tenant_isolation.py::TestTenantAccessError | Done |
| F-05a | F | Tenant A cannot read Tenant B tickets via get_by_id | 1C | app/db/repositories/ticket_repository.py | tests/test_tenant_isolation.py::test_tenant_b_cannot_read_tenant_a_ticket | Done |
| F-05b | F | Tenant A cannot read Tenant B diagnostics via get_by_id | 1C | app/db/repositories/diagnostic_repository.py | tests/test_tenant_isolation.py::test_tenant_b_cannot_read_tenant_a_diagnostic | Done |
| F-05c | F | Tenant A cannot read Tenant B audit events via get_by_id | 1C | app/db/repositories/audit_repository.py | tests/test_tenant_isolation.py::test_tenant_b_cannot_read_tenant_a_audit_event | Done |
| F-05d | F | List methods filter strictly by tenant_id (no cross-tenant leakage) | 1C | app/db/repositories/ | tests/test_tenant_isolation.py::test_*_list_excludes_* | Done |
| O-01 | O | Audit events stored in SQLite with previous_hash/current_hash chain (NFR-05, NFR-06) | 1C | app/db/models.py, app/db/repositories/audit_repository.py | tests/test_tenant_isolation.py::TestAuditHashChain | Done |
| O-02 | O | Tampered audit record detected by chain verification (NFR-06) | 1C | app/db/repositories/audit_repository.py | tests/test_tenant_isolation.py::test_tampered_*_detected | Done |
| F-06 | F | JIRA webhook normalizes payload to canonical InboundEvent (FR-01, IR-01 new-ticket path) | 2 | app/adapters/jira_adapter.py, app/schemas/events.py | tests/test_adapters.py::TestJiraNormalization, tests/test_webhook_endpoints.py::TestJiraWebhookEndpoint | Done |
| F-07 | F | Slack webhook normalizes payload to canonical InboundEvent (FR-02, IR-05) | 2 | app/adapters/slack_adapter.py, app/schemas/events.py | tests/test_adapters.py::TestSlackNormalization, tests/test_webhook_endpoints.py::TestSlackWebhookEndpoint | Done |
| F-08 | F | WhatsApp webhook normalizes payload to canonical InboundEvent (FR-03, IR-07) | 2 | app/adapters/whatsapp_adapter.py, app/schemas/events.py | tests/test_adapters.py::TestWhatsAppNormalization, tests/test_webhook_endpoints.py::TestWhatsAppWebhookEndpoint | Done |
| F-09 | F | Unverified contacts are rejected (403) by identity resolver (FR-04, IR-06) | 2 | app/services/identity_resolver.py | tests/test_identity_resolver.py, tests/test_webhook_endpoints.py::test_unknown_*_returns_403 | Done |
| F-10 | F | Inbound events are classified by category, severity, component, confidence (FR-05) | 3 | app/agents/classifier.py | tests/test_classifier.py | Done |
| F-11 | F | Low-confidence classifications route to Tier 2 (FR-05) | 3 | app/agents/orchestrator.py | tests/test_orchestrator.py::TestTier2Routing::test_low_confidence_routes_to_tier2 | Done |
| F-12 | F | Tickets are created, updated, and closed via tenant-isolated ticket manager | 3 | app/services/ticket_manager.py, app/agents/orchestrator.py | tests/test_orchestrator.py::TestTier1Routing::test_incident_creates_ticket | Done |
| F-13 | F | Diagnostic fields extracted from inbound events and tagged with DataClassification; missing required fields identified; no commands executed against customer infrastructure (FR-08, FR-09, FR-11) | 4 | app/agents/diagnostics_collector.py | tests/test_diagnostics_collector.py, tests/test_orchestrator.py | Done |
| F-14 | F | Knowledge retrieval keyword- and tag-based; returns NoMatchResult when below threshold; respects tenant boundaries; live signals excluded (FR-26, FR-27, FR-28) | 4 | app/agents/knowledge_retriever.py, config/knowledge/ | tests/test_knowledge_retriever.py, tests/test_orchestrator.py | Done |
| F-15 | F | First response grounded in KB article; safe fallback when no KB match; secrets redacted; CONFIDENTIAL/RESTRICTED fields excluded from response text (FR-12, FR-13, FR-14) | 4 | app/agents/first_response_generator.py | tests/test_first_response_generator.py, tests/test_orchestrator.py | Done |
| F-16 | F | SLA state machine tracks OPEN → ACKNOWLEDGED → IN_PROGRESS → RESOLVED/BREACHED (FR-16) | 5 | app/agents/sla_tracker.py | tests/test_sla_tracker.py | Not started |
| F-17 | F | SLA breach detection uses ClockProvider, not system time directly (FR-16) | 5 | app/agents/sla_tracker.py, app/utils/clock.py | tests/test_sla_tracker.py | Not started |
| F-18 | F | Escalation chain fires in configured order on SLA breach (FR-18) | 5 | app/agents/escalation_engine.py | tests/test_escalation_engine.py | Not started |
| F-19 | F | Quiet hours suppress non-critical outbound messages (FR-23) | 5 | app/services/communication_policy.py | tests/test_communication_policy.py | Not started |
| F-20 | F | Sev-1 critical_override bypasses quiet hours when configured (FR-23) | 5 | app/services/communication_policy.py | tests/test_communication_policy.py | Not started |
| F-21 | F | Outbound messages sent only on meaningful state changes (FR-21, FR-22) | 5 | app/services/communication_policy.py | tests/test_communication_policy.py | Not started |
| F-22 | F | Human handoff packet contains all required fields: customer goal, attempts, diagnostics, SLA state, suggested next action (FR-24) | 6 | app/agents/handoff_builder.py | tests/test_orchestrator.py | Not started |
| F-23 | F | Tier 2 triggered by: low confidence, injection flagged, customer requests human (Phase 3); no KB match, runbook exhausted, dependency failure (Phase 4+) (FR-25) | 3 | app/agents/orchestrator.py | tests/test_orchestrator.py::TestTier2Routing | Done |
| F-24 | F | Engineer on duty notified when a new incident ticket is logged (FR-15) | 5 | app/agents/escalation_engine.py | tests/test_escalation_engine.py | Not started |
| F-25 | F | SLA state distinguishes engineer-notified from engineer-engaged (acknowledgement received) (FR-17) | 5 | app/agents/sla_tracker.py | tests/test_sla_tracker.py | Not started |
| F-26 | F | Escalation chain configurable by severity and component; component-specific chains checked before wildcard (FR-19) | 5 | config/escalation_chains.yaml, app/agents/escalation_engine.py | tests/test_escalation_engine.py | Not started |
| F-27 | F | Every escalation event recorded in audit trail: who contacted, when, why, outcome (FR-20) | 5 | app/agents/escalation_engine.py, app/db/repositories/audit_repository.py | tests/test_escalation_engine.py | Not started |
| F-28 | F | Customer guided through opening a well-formed JIRA ticket when contacting via Slack or WhatsApp (FR-06, FR-07) | Prototype-deferred | — requires real JIRA write and outbound channel messaging | — | Deferred |
| F-29 | F | JIRA ticket lifecycle events beyond new-ticket creation (comment, status-changed, resolved) handled by the agent (IR-01 full scope, IR-02, IR-03) | Prototype-deferred | — requires live JIRA Service Desk integration | — | Deferred |
| F-30 | F | Collected diagnostics attached to the corresponding JIRA Service Desk ticket (FR-10) | Prototype-deferred | — SQLite only in prototype; JIRA attachment deferred | — | Deferred |
| S-01 | S | Webhook signature (HMAC-SHA256) verified per tenant before processing (NFR-08) | 2 | app/services/signature_verifier.py, app/adapters/ | tests/test_security.py::TestSignatureVerifier, tests/test_webhook_endpoints.py::test_invalid_signature_returns_403 | Done |
| S-02 | S | Duplicate event_id or out-of-window timestamp rejected (replay protection) (NFR-08) | 2 | app/services/replay_guard.py, app/db/repositories/replay_guard_repository.py | tests/test_security.py::TestReplayGuardService, tests/test_webhook_endpoints.py::test_duplicate_event_id_returns_409, test_stale_timestamp_returns_400 | Done |
| S-03 | S | Inbound message text scanned for prompt injection patterns (NFR-09) | 2 | app/services/injection_guard.py | tests/test_security.py::TestInjectionGuard, tests/test_webhook_endpoints.py::test_injection_in_*_flagged_not_rejected | Done |
| S-04 | S | Secrets redacted from all log output and customer-facing messages (NFR-10) | 2 | app/utils/redaction.py | tests/test_security.py::TestRedaction | Done |
| S-05 | S | DataClassification enum (PUBLIC/INTERNAL/CONFIDENTIAL/RESTRICTED) applied to all customer data fields (NFR-04) | 1C | app/db/models.py | tests/test_db_init.py::test_diagnostics_has_classification_column | Done |
| S-06 | S | CONFIDENTIAL/RESTRICTED diagnostic fields never appear in outbound customer-facing response text (NFR-10) | 4 | app/agents/first_response_generator.py | tests/test_first_response_generator.py, tests/test_security.py | Done |
| S-07 | S | Credentials sourced from config/environment only; no long-lived credentials held in agent memory or prompts (NFR-11) | Design decision | config/tenants.yaml, .env | — | Prototype-scoped |
| O-03 | O | FakeClock.advance() allows SLA breach testing without real-time wait (NFR-12 test enabler) | 5 | app/utils/clock.py | tests/test_sla_tracker.py | Not started |
| O-04 | O | Demo endpoint POST /demo/advance-time available in DEMO_MODE=true | 5 | app/main.py | tests/test_api_endpoints.py | Not started |
| O-05 | O | Audit logger service (app/services/audit_logger.py) wraps the Phase 1C repository layer and exposes a /audit/verify API endpoint (NFR-05, NFR-06 — Phase 6 service wrapper) | 6 | app/services/audit_logger.py | tests/test_audit_logger.py | Not started |
| O-06 | O | /audit/verify endpoint detects tampered audit records and reports the first chain break (NFR-06 — Phase 6 API surface) | 6 | app/services/audit_logger.py | tests/test_audit_logger.py | Not started |
| O-07 | O | System degrades gracefully when KB is unavailable or returns no match: falls back to human-review route and never fails silently (NFR-13) | 4 | app/agents/first_response_generator.py, app/agents/knowledge_retriever.py | tests/test_first_response_generator.py, tests/test_orchestrator.py | Done |
| O-08 | O | Operational telemetry captured in demo/evaluation layer: classification accuracy, response groundedness, escalation correctness, SLA breach rates (NFR-07, NFR-14) | 7 | demo/scenarios.py | tests/ | Not started |
| Q-01 | Q | All 5 required demo scenarios pass end-to-end (NFR-15) | 7 | demo/scenarios.py | tests/ | Not started |
| Q-02 | Q | pytest suite covers all core behaviors with no skipped tests (NFR-15) | 7 | tests/ | — | Not started |

---

## Prototype-Deferred Requirements

The following PRD requirements cannot be verified in this prototype without live external integrations. They are documented above as **Deferred** rows (F-28, F-29, F-30) and are not in scope for Phases 1–7 of the prototype.

| PRD Ref | Requirement | Reason deferred |
|---|---|---|
| FR-06, FR-07 | Guide non-JIRA contacts through opening a well-formed JIRA ticket | Requires real outbound JIRA ticket creation; no JIRA write in prototype |
| FR-10 | Attach collected diagnostics to the JIRA Service Desk ticket | Requires JIRA write API; prototype stores diagnostics in SQLite only |
| IR-01 (full scope) | Handle JIRA ticket lifecycle events: comment, status-changed, resolved | Prototype handles new-ticket webhooks only |
| IR-02, IR-03 | Read and write JIRA fields; thread comments identifying system as automated agent | Requires live JIRA Service Desk integration |
| IR-04 | JIRA permissions scoped per customer | Simulated by SQLite tenant isolation; real JIRA permission model deferred |
| IR-08 | Outbound WhatsApp messages comply with WhatsApp Business session-window policies | Requires live WhatsApp Business API and Meta-approved message templates |
| IR-09, IR-10 | Consume on-call schedule; notifications must be acknowledgeable | Simulated by escalation_chains.yaml config; real on-call API deferred |
