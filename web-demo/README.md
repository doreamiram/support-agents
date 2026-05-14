# Static visual web demo

This directory is a **read-only presentation layer** for the five end-to-end
demo scenarios. It mirrors the **shape** of the CLI demo (`python -m demo.scenarios`)
using static JSON — it does **not** execute the FastAPI app or orchestrator.

## View locally

Because browsers often block `fetch()` to local JSON from a `file://` URL, use a
tiny static server from this directory:

```powershell
cd c:\modelyo-support-agents\web-demo
python -m http.server 8080
```

Then open `http://127.0.0.1:8080/` in a browser.

## Vercel (optional)

Create a Vercel project from this repository and set the **Root Directory** to
`web-demo`. No build command or npm install is required. Do not add API keys or
connect external services — this site is static HTML/CSS/JS only.

## Relationship to the real demo

| Surface | Command / location | What it does |
|---|---|---|
| Executable demo | `.\.venv\Scripts\python.exe -m demo.scenarios` | Runs orchestrator + scenarios |
| Full tests | `.\.venv\Scripts\pytest.exe -q` | Validates all behaviour |
| This folder | Static files | Reviewer-friendly cards only |
