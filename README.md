# Modelyo Support Agents

Agentic Tier 1 / Tier 2 customer support system prototype for Modelyo Confidential Cloud enterprise customers.

> **Status:** Phase 1A — minimal skeleton. See the implementation plan in `docs/design_document.md`.

---

## Requirements

- Python 3.12
- pip

---

## Setup

```bash
# 1. Clone or unzip the project
cd modelyo-support-agents

# 2. Create a virtual environment
python -m venv .venv

# Windows (PowerShell)
.\.venv\Scripts\Activate.ps1

# macOS / Linux
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Copy environment config
cp .env.example .env
# Edit .env if needed (defaults are fine for local demo)
```

---

## Run the API

```bash
uvicorn app.main:app --reload
```

The API will be available at `http://127.0.0.1:8000`.

Interactive docs: `http://127.0.0.1:8000/docs`

---

## Test the health endpoint

```bash
# Using curl
curl http://127.0.0.1:8000/health

# Expected response
{"status":"ok","version":"0.1.0"}
```

---

## Run tests

```bash
pytest
```

---

## Project structure

```
app/                    Application source
docs/                   Design document and requirements traceability
audit_logs/             Exported demo audit log examples (not the source of truth)
config/                 YAML config files — tenants, SLA rules, escalation chains (Phase 1B+)
tests/                  Test suite
demo/                   Demo scenario scripts (Phase 7)
```

---

## Demo scenarios

> Added in Phase 7. See `demo/scenarios.py` and the demo section in `docs/design_document.md`.

---

## Configuration

> Added in Phase 1B. See `config/` and `docs/design_document.md`.
