from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config.loader import ConfigLoadError, load_config
from app.db.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        app.state.config = load_config()
    except ConfigLoadError as exc:
        raise RuntimeError(
            f"Startup aborted — invalid configuration:\n\n{exc}"
        ) from exc
    init_db()
    yield


app = FastAPI(
    title="Modelyo Support Agents",
    description="Tier 1 / Tier 2 agentic support system for Modelyo Confidential Cloud.",
    version="0.2.0",
    lifespan=lifespan,
)

# ── Webhook intake routes ─────────────────────────────────────────────────────
from app.adapters.jira_adapter import router as jira_router          # noqa: E402
from app.adapters.slack_adapter import router as slack_router        # noqa: E402
from app.adapters.whatsapp_adapter import router as whatsapp_router  # noqa: E402

app.include_router(jira_router)
app.include_router(slack_router)
app.include_router(whatsapp_router)


@app.get("/health", tags=["system"])
def health_check() -> dict:
    return {"status": "ok", "version": app.version}
