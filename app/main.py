import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException

from app.config.loader import ConfigLoadError, load_config
from app.db.database import init_db
from app.utils.clock import FakeClock

# Module-level demo clock — advances deterministically via POST /demo/advance-time.
# Only meaningful when DEMO_MODE=true; always created but unused in production.
_demo_clock = FakeClock()


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


# ── Demo endpoint ─────────────────────────────────────────────────────────────

@app.post("/demo/advance-time", tags=["demo"])
def demo_advance_time(minutes: int = 0, hours: int = 0) -> dict:
    """
    Advance the demo clock forward by the given duration.

    Only available when the DEMO_MODE environment variable is set to "true".
    Returns the new simulated timestamp and the amount advanced.
    This endpoint never affects the system clock or real SLA timers.
    """
    if os.getenv("DEMO_MODE", "false").lower() != "true":
        raise HTTPException(
            status_code=404,
            detail="Demo endpoint not available. Set DEMO_MODE=true to enable.",
        )
    _demo_clock.advance(minutes=minutes, hours=hours)
    return {
        "now": _demo_clock.now().isoformat(),
        "advanced_minutes": minutes,
        "advanced_hours": hours,
    }
