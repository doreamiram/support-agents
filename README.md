# Modelyo Support Agents

Agentic Tier 1 / Tier 2 customer support prototype for Modelyo Confidential Cloud
enterprise customers.

> **Status:** Phase 10B complete — optional real LLM provider support added
> behind safe feature flags, with `MockLLMProvider` still the default fallback.
> Current Phase 10B baseline is 557/557 tests passing. See `docs/design_document.md`
> for architecture details, `docs/llm_integration_notes.md` for LLM readiness, and
> `docs/demo_guide.md` for CLI and optional visual demo instructions.

---

## What this project is

This prototype implements an AI-agent system that automates Tier 1 and Tier 2
customer support for Modelyo Confidential Cloud enterprise customers.  It handles
support requests arriving via JIRA Service Desk, Slack, and WhatsApp, and routes
them through a deterministic pipeline: intake → classify → diagnose → KB retrieval
→ first response → SLA tracking → escalation → human handoff.

## What problem it solves

Modelyo support engineers currently triage, diagnose, and draft responses to
every inbound request manually.  This prototype demonstrates how an agent system
can:

- Classify inbound messages and route to Tier 1 (automated) or Tier 2 (human)
- Extract structured diagnostics without executing any commands on customer infrastructure
- Generate grounded first responses referenced to internal KB articles
- Track SLA timers with severity-based deadlines and breach detection
- Escalate through a configurable on-call chain when SLA timers expire
- Build a structured HandoffPacket for the human engineer when Tier 2 is needed
- Maintain a tamper-evident per-tenant audit trail of every decision

## Current scope and prototype boundaries

This is a **functional prototype** — not a production deployment.  The following
are simulated / stubbed:

| What is simulated | Why |
|---|---|
| LLM responses | `MockLLMProvider` by default; optional `RealLLMProvider` is limited to safe demo summaries and falls back to mock on missing config, timeout, or failure |
| JIRA ticket write | Tickets stored in in-memory / local SQLite only |
| Slack outbound messages | No real Slack API calls |
| WhatsApp outbound messages | No real WhatsApp Business API calls |
| On-call notifications | Escalation engine returns `simulated=True` actions |
| Knowledge freshness | Static KB markdown files; no live ingestion pipeline |

What **is real**:

- **LLM provider layer** — `LLMProvider`, `MockLLMProvider`, and optional stdlib-only `RealLLMProvider` for controlled demo enrichment tasks; deterministic agents remain authoritative
- Full deterministic classification, diagnostics, and KB retrieval pipeline
- Tamper-evident audit hash chain (SHA-256) in SQLite
- SLA breach detection with configurable severity rules
- Communication policy with quiet hours, cooldown, and P1 critical override
- Data classification (PUBLIC / INTERNAL / CONFIDENTIAL / RESTRICTED) on all fields
- Webhook signature verification (HMAC-SHA256) and replay protection
- Prompt-injection guard and secret redaction

---

## Architecture overview

```
Inbound event (JIRA / Slack / WhatsApp webhook)
  |
  +-- Channel Adapter          normalize to InboundEvent
  +-- Signature Verifier       HMAC-SHA256 per tenant secret
  +-- Replay Guard             event_id dedup + timestamp window
  +-- Identity Resolver        contact verified against config
  +-- Injection Guard          pattern-scan; flags but does not reject
  |
  +-- Interaction Classifier   category / severity / component / confidence
  |
  +-- Support Orchestrator
        +-- Ticket Manager     create tenant-scoped ticket
        +-- SLA Tracker        initialize state machine, check breach
        +-- Diagnostics        extract structured fields from event text
        +-- Knowledge Retriever keyword + tag + component scoring
        +-- Comm Policy        quiet hours / cooldown gate
        +-- First Response Gen grounded response from KB article
        +-- Escalation Engine  on-call chain; simulated actions
        +-- Handoff Builder    structured packet for Tier 2 engineer
        +-- Audit Logger       every decision written to hash chain
        +-- LLM provider       Mock default + optional RealLLMProvider for safe demo text
```

See `docs/design_document.md` for a detailed description of each component.

---

## Requirements

- Python 3.12
- pip (for installing dependencies into a virtual environment)

---

## Local setup

```powershell
# 1. Clone or unzip the project
cd c:\modelyo-support-agents

# 2. Create and activate a virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 3. Install dependencies
pip install -r requirements.txt

# 4. Copy environment config (defaults work for local demo)
copy .env.example .env
```

---

## Run the API server

```powershell
uvicorn app.main:app --reload
```

Interactive docs: `http://127.0.0.1:8000/docs`

---

## Run tests

```powershell
# Full suite (557/557 tests)
.\.venv\Scripts\pytest.exe

# Quiet summary
.\.venv\Scripts\pytest.exe -q

# Specific module
.\.venv\Scripts\pytest.exe tests/test_demo_scenarios.py -v
```

---

## Run the demo

The demo runs all five end-to-end scenarios deterministically using in-memory
SQLite and FakeClock.  No real external integrations are needed.

```powershell
.\.venv\Scripts\python.exe -m demo.scenarios
```

Expected output: five scenario blocks each showing `[PASS]`, followed by a
`5/5 scenarios passed` summary.

See `docs/demo_guide.md` for a detailed walkthrough of each scenario and how
to present them to a reviewer.

---

## Visual Web Demo

The `web-demo/` folder is a no-build browser demo of the five scenarios (HTML,
CSS, JS, and `demo-data.json`). It loads the static snapshot by default and can
call the local FastAPI backend for a live run at `GET /api/demo/scenarios`.
The page shows LLM Provider Status, the safe demo summary, Tier 2 handoff
summaries, and the Tier 1 polished customer response when present. The static
snapshot remains available for hosted presentation fallback.

Start the backend:

```powershell
uvicorn app.main:app --reload
```

Start the static page:

```powershell
cd c:\modelyo-support-agents\web-demo
python -m http.server 8080
```

Then open `http://127.0.0.1:8080/` and use **Run Live Demo**. If the backend is
unavailable, the page keeps showing the static snapshot. For Vercel, set the
project **Root Directory** to `web-demo` — no `npm install`, no build step, and
no API keys. The executable pipeline and full regression coverage remain:

```powershell
.\.venv\Scripts\python.exe -m demo.scenarios
.\.venv\Scripts\pytest.exe -q
```

Real LLM inference is optional and disabled by default. No live Slack, JIRA,
WhatsApp, PagerDuty, or other external support integrations are used anywhere in
this repository.

### Optional RealLLMProvider

`MockLLMProvider` is selected unless `USE_REAL_LLM=true` and all required
settings are present:

```powershell
USE_REAL_LLM=false
LLM_PROVIDER=generic_http
LLM_API_BASE_URL=
LLM_API_KEY=
LLM_MODEL=
LLM_TIMEOUT_SECONDS=10
```

The real provider uses only stdlib HTTP, adds no SDK dependency, and is limited
to `demo_summary`, `handoff_summary`, and `customer_response_polish`. It never
drives routing, security, SLA, escalation, identity, classification, KB
confidence, or prompt-injection decisions. On missing config, timeout, HTTP
error, or malformed response, the demo falls back safely to `MockLLMProvider`.

## Key design choices

- **Deterministic orchestration** — the orchestrator and Tier 1/Tier 2 agents
  remain rule-based and reproducible; they are the **source of truth** for tests
  and safety. `MockLLMProvider` is the default LLM provider and safe fallback.
- **ClockProvider abstraction** — `FakeClock` enables SLA breach tests and demo
  time-travel without real delays.
- **Data classification on every field** — PUBLIC / INTERNAL / CONFIDENTIAL /
  RESTRICTED; CONFIDENTIAL/RESTRICTED values never appear in responses or
  HandoffPackets.
- **Tamper-evident audit trail** — SHA-256 hash chain; `/audit/verify` endpoint
  confirms integrity without exposing payload content.
- **Fail-fast config** — all YAML validated at startup; bad config aborts before
  the server accepts requests.

---

## Security and tenant-isolation notes

- Every repository method requires `tenant_id`; cross-tenant access raises
  `TenantAccessError`.
- Webhook payloads are verified with HMAC-SHA256 before parsing.
- Duplicate events are rejected via `event_id` deduplication.
- Injection-flagged messages are quarantined to Tier 2; the original channel
  payload is retained only for audit handling and is not exposed to LLM tasks.
- Credentials and secrets are redacted before any log sink or outbound message.

---

## What would be needed for production

1. **Production LLM hosting decision** — Phase 10B includes a generic optional
   HTTP provider for safe demo tasks only; production still needs an approved
   managed vs. self-hosted decision against Modelyo's confidential-computing
   posture (PRD T-02 / D-01). See `docs/llm_integration_notes.md`.
2. **JIRA Service Desk API** — ticket write, field update, comment threading.
3. **Real channel outbound** — Slack Bot API, WhatsApp Business API (with
   Meta-approved templates for out-of-session messages).
4. **Live on-call integration** — PagerDuty / Opsgenie for acknowledgement
   signals (FR-15 / IR-09, IR-10).
5. **Knowledge ingestion pipeline** — freshness guarantees, re-indexing on
   runbook updates (T-13).
6. **Persistent SLA state** — deadline columns on `Ticket` rows for crash
   recovery; current prototype holds deadlines in-memory.
7. **Production DB** — replace SQLite with PostgreSQL with row-level security.
8. **Secrets management** — rotate credentials from a vault; never held in
   agent memory (NFR-11).
9. **Latency budget** — agree and instrument per-channel response targets
   (NFR-12 / T-15).
10. **Evaluation harness** — labelled test corpus for classification accuracy
    and response groundedness regression gating (NFR-14 / NFR-15).

---

## Project structure

```
app/                Application source
  adapters/         JIRA, Slack, WhatsApp webhook handlers
  agents/           Classifier, Orchestrator, SLA, Escalation, Handoff Builder
  config/           Config loader + Pydantic models
  db/               SQLAlchemy models, repositories, session management
  schemas/          InboundEvent and webhook payload schemas
  services/         Ticket Manager, Identity, Audit Logger, Telemetry, etc.
  utils/            ClockProvider, redaction
config/             YAML config files and KB markdown articles
docs/               Design document, requirements traceability, demo guide, LLM integration notes
demo/               End-to-end demo scenarios (CLI and live web payload)
web-demo/           No-build browser demo with live button and static fallback
tests/              Full pytest suite
audit_logs/         Exported demo audit log examples (reference only)
```
