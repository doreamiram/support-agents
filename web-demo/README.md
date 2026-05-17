# Visual web demo

This directory is a no-build browser demo for the five end-to-end scenarios. It
loads `demo-data.json` as a static fallback and can call the local FastAPI
backend for a live run of the same scenario flow. Phase 10B also displays safe
LLM provider status and generated demo text when present.

## Live backend mode

Start the API from the repository root:

```powershell
cd c:\modelyo-support-agents
uvicorn app.main:app --reload
```

Then start the static page:

```powershell
cd c:\modelyo-support-agents\web-demo
python -m http.server 8080
```

Open `http://127.0.0.1:8080/` and click **Run Live Demo**. The browser calls
`http://127.0.0.1:8000/api/demo/scenarios`.

The live payload may include:

- `llm_provider_status` and `meta.llm_provider_mode`
- `llm_summary`
- `llm_handoff_summary` on Tier 2 scenario cards
- `llm_customer_response_polish` on the Tier 1 happy-path card

The page never renders provider credentials, endpoint URLs, prompts, provider
responses beyond the safe generated text, raw diagnostics, or raw errors.

## Static fallback mode

The page loads `demo-data.json` by default. If the backend is unavailable, it
keeps showing that static snapshot and displays a clear fallback message.
Because browsers often block `fetch()` from a `file://` URL, use the static
server command above rather than opening `index.html` directly.

```powershell
cd c:\modelyo-support-agents\web-demo
python -m http.server 8080
```

Then open `http://127.0.0.1:8080/` in a browser.

## Vercel (optional)

Create a Vercel project from this repository and set the **Root Directory** to
`web-demo`. No build command or npm install is required. Do not add API keys or
connect external services. Hosted presentation uses the static snapshot.

## Relationship to the real demo

| Surface | Command / location | What it does |
|---|---|---|
| Executable demo | `.\.venv\Scripts\python.exe -m demo.scenarios` | Runs orchestrator + scenarios |
| Live web endpoint | `GET /api/demo/scenarios` | Runs the existing scenario flow and returns safe JSON |
| Full tests | `.\.venv\Scripts\pytest.exe -q` | Validates all behaviour |
| This folder | Static files | Reviewer-friendly cards with live-run button and snapshot fallback |

## LLM provider mode

`MockLLMProvider` remains the default. Optional real LLM mode is configured only
through environment variables on the backend and is limited to
`demo_summary`, `handoff_summary`, and `customer_response_polish`. If real mode
is disabled, missing config, times out, or fails, the backend falls back to mock
output and reports that status safely in the payload.
