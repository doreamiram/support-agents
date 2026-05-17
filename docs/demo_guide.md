# Modelyo Support Agents — Demo Guide

> **Audience:** Modelyo engineers reviewing the prototype.  
> **Goal:** Run and understand the five end-to-end demo scenarios in under 20 minutes.

---

## Prerequisites

Python 3.12 and the virtual environment must be set up.  See `README.md` for
setup instructions.  No real Slack, JIRA, WhatsApp, or LLM account is needed.

```powershell
# Activate the virtual environment (if not already active)
.\.venv\Scripts\Activate.ps1

# Verify the test suite is clean (549/549 tests, no failures)
.\.venv\Scripts\pytest.exe -q
```

Expected baseline: `549 passed` (`549/549`).

---

## Optional: Visual Web Demo

The `web-demo/` directory loads the static `demo-data.json` snapshot by default
and can call the local FastAPI backend for a live run of the same five scenarios.
The live endpoint is `GET /api/demo/scenarios`.

Start the backend in one PowerShell:

```powershell
uvicorn app.main:app --reload
```

Start the static page in another PowerShell:

```powershell
cd c:\modelyo-support-agents\web-demo
python -m http.server 8080
```

Open `http://127.0.0.1:8080/`. The page shows the static snapshot first. Click
**Run Live Demo** to call the backend and render live results. Each card shows
**status PASS**, **action**, **reason**, **key result**, **PRD capability**,
**simulated vs real** notes, and a safe high-level execution trace. If the
backend is unavailable, the page displays: `Live backend unavailable, showing
static snapshot.`

For static hosting, deploy `web-demo/` as the Vercel root with no build step.
Hosted mode uses the static snapshot fallback; no API keys or real external
integrations are needed.

**Visual demo vs CLI demo:** the CLI (`python -m demo.scenarios`) remains the
authoritative executable demo. The live web endpoint reuses the same scenario
runner and returns only browser-safe fields.

---

## Running the demo

```powershell
.\.venv\Scripts\python.exe -m demo.scenarios
```

Expected output: five scenario blocks each reporting `[PASS]`, followed by:

```
========================================================================
  Results: 5/5 scenarios passed
========================================================================
```

The demo exits with code `0` on success, `1` on any scenario failure.

---

## Recommended demo script

### Setup statement (30 seconds)

> "This prototype demonstrates a fully deterministic Tier 1 / Tier 2 support
> agent pipeline for Modelyo Confidential Cloud.  No real LLM, no real Slack,
> no real JIRA — every component uses a deterministic mock so you can run and
> verify the logic independently of live credentials."

---

### Scenario 1 — Happy-path Tier 1 incident

**What it demonstrates:**  
A storage-service incident with complete diagnostics is automatically resolved
at Tier 1 — no human handoff.

**Pipeline steps exercised:**  
classification → ticket creation → diagnostics (bucket_name + operation_type
extracted) → KB retrieval (storage-001, score 0.70) → comm policy (allowed,
business hours) → first response generated → SLA initialised (P2, 60-min
response deadline)

**Key output to point out:**
- `KB article: storage-001` — response is grounded in an authoritative article
- `SLA state: OPEN` — timer started; no breach yet
- `Handoff packet: none` — stays Tier 1, no engineer loop-in needed

**PRD coverage:** FR-05 (classify), FR-08, FR-09 (diagnostics), FR-12, FR-13
(first response), FR-16 (SLA timer), NFR-04 (data classification)

---

### Scenario 2 — Injection / unsafe input

**What it demonstrates:**  
A message containing a prompt-injection pattern is quarantined immediately.
No ticket is created; the orchestrator routes to Tier 2 and produces a
HandoffPacket with a "Do not auto-route" recommendation.

**Pipeline steps exercised:**  
injection guard (sets `injection_flagged=True`) → orchestrator routes to Tier 2
→ HandoffPacket built with `suggested_next_action`

**Key output to point out:**
- `Reason: injection_flagged`
- `Suggested: Review the message from alice.chen for potential prompt injection`

**Prototype note:** The injection flag is set directly in the demo to simulate
what the `InjectionGuard` would set after scanning the webhook body.

**PRD coverage:** NFR-09 (prompt-injection mitigation), FR-24, FR-25 (handoff
at any workflow point)

---

### Scenario 3 — No KB match

**What it demonstrates:**  
A network-service incident has complete diagnostics (IP address extracted) but
no KB article meets the 0.60 confidence threshold.  The system routes to Tier 2
with a HandoffPacket that includes all attempted steps.

**Pipeline steps exercised:**  
classification → ticket → SLA init → complete diagnostics (ip_address extracted)
→ KB retrieval (score 0.50 < 0.60 threshold) → no_kb_match → Tier 2 → HandoffPacket

**Key output to point out:**
- `Diagnostics complete: True` — the system did collect all required fields
- `KB no match reason: no_kb_match` — the retriever found no confident match
- `Attempted steps: [classification, diagnostics_collection, kb_retrieval, sla_initialized]`

**PRD coverage:** FR-14 (fallback when no confident KB answer), FR-24, FR-25
(handoff with full context), NFR-13 (graceful degradation)

---

### Scenario 4 — SLA breach + escalation

**What it demonstrates:**  
FakeClock time-travel shows P1 SLA breach detection and escalation without any
real sleep.  The clock is advanced 20 minutes past the 15-minute P1 response
deadline, breach is detected, and the configured three-tier on-call chain fires
simulated notifications.

**Pipeline steps exercised:**  
P1 incident → ticket → SLA init (deadline T+15) → check at T=0 (clean) →
`FakeClock.advance(minutes=20)` → `check_breach()` → response_breached=True →
`escalation_engine.escalate()` → 3 simulated contact actions

**Key output to point out:**
- `Severity: P1`
- `Breached at T=0: False` — no breach immediately after creation
- `Breached after +20 min: True` — FakeClock advanced 20 min deterministically
- `Escalation actions: 3` — ACME On-Call, Engineering Manager, VP Engineering

**How to explain FakeClock:**  
> "Real SLA testing would require waiting 15 minutes.  FakeClock replaces the
> system clock with a controllable, deterministic source.  We advance it 20
> minutes in code — no real wait, fully reproducible."

**PRD coverage:** FR-16 (SLA timer), FR-17 (notified vs. engaged state), FR-18
(escalation on breach), FR-19 (configurable chain), FR-20 (escalation audit),
O-03 (FakeClock for test enablement)

---

### Scenario 5 — Audit chain verification

**What it demonstrates:**  
Every orchestrator decision is written to a per-tenant tamper-evident hash chain.
`AuditLogger.verify_chain()` walks the chain and confirms integrity.

**Pipeline steps exercised:**  
auth-service incident → orchestrator writes `classification_completed` audit event
→ orchestrator writes `routing_decision` audit event → `AuditLogger.verify_chain()`
→ `valid=True`, `event_count=2`, `chain_breaks=[]`

**Key output to point out:**
- `Audit chain valid: True`
- `Events verified: 2`
- `Chain breaks: 0`

**How to explain the chain:**  
> "Every event stores a SHA-256 hash of the previous event's hash concatenated
> with its own content.  Tampering with any record breaks the chain.  The
> `/audit/verify` endpoint exposes this check over HTTP without returning any
> raw payload content."

**PRD coverage:** NFR-05 (audit trail), NFR-06 (tamper-evident, immutable),
O-05 (AuditLogger service), O-06 (/audit/verify endpoint)

---

## How to explain prototype limitations professionally

When reviewers ask about real integrations:

> "This prototype intentionally uses deterministic stubs everywhere a real
> integration would require credentials, a live API, or a network call.  The
> design is wired to accept a real LLM, real JIRA write API, and real Slack Bot
> token as drop-in replacements — the interfaces and data contracts are defined.
> Production deployment is a separate engagement; the goal here was to validate
> the architecture and workflow logic independently of live systems."

When reviewers ask about the database:

> "SQLite works for the prototype because it gives us full SQL semantics and
> tenant isolation without a running server.  The SQLAlchemy ORM layer means
> switching to PostgreSQL is a configuration change, not an architecture change."

When reviewers ask about the LLM:

> "The FirstResponseGenerator uses a deterministic KB-grounded template.  In
> production this call is replaced by an LLM prompt that cites the same KB
> article — the grounding constraint (FR-13: every claim must be traceable to
> an authoritative source) is enforced at the retrieval layer, not the generation
> layer, so it holds regardless of which LLM is used."

---

## Full command reference

```powershell
# Run the demo
.\.venv\Scripts\python.exe -m demo.scenarios

# Run all tests
.\.venv\Scripts\pytest.exe -q

# Run demo tests only
.\.venv\Scripts\pytest.exe tests/test_demo_scenarios.py -v

# Run the API server
uvicorn app.main:app --reload

# Verify audit chain via HTTP (server must be running)
# curl http://127.0.0.1:8000/audit/verify
# curl http://127.0.0.1:8000/audit/verify?tenant_id=acme-corp

# Advance the demo clock via HTTP (requires DEMO_MODE=true)
# $env:DEMO_MODE="true"; uvicorn app.main:app --reload
# curl -X POST "http://127.0.0.1:8000/demo/advance-time?minutes=30"
```

---

## Mapping scenarios to PRD requirements

| Scenario | PRD requirements demonstrated |
|---|---|
| 1 — Tier 1 happy path | FR-05, FR-08, FR-09, FR-11, FR-12, FR-13, FR-16, FR-21–FR-23, NFR-01, NFR-04 |
| 2 — Injection / Tier 2 | NFR-09, FR-24, FR-25 |
| 3 — No KB match | FR-14, FR-24, FR-25, NFR-13 |
| 4 — SLA escalation | FR-16, FR-17, FR-18, FR-19, FR-20, O-03 |
| 5 — Audit verification | NFR-05, NFR-06, O-05, O-06 |

For the full requirements traceability matrix see
`docs/requirements_traceability.md`.
