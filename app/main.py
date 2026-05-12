import os
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Request
from sqlalchemy.orm import Session

from app.config.loader import ConfigLoadError, load_config
from app.db.database import get_db, init_db
from app.services.audit_logger import AuditLogger
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


# ── Audit endpoint ────────────────────────────────────────────────────────────

@app.get("/audit/verify", tags=["audit"])
def audit_verify(
    request: Request,
    tenant_id: Optional[str] = None,
    db: Session = Depends(get_db),
) -> dict:
    """
    Verify the tamper-evident audit chain.

    When tenant_id is supplied, verifies only that tenant's chain.
    When omitted, verifies all tenants known in config.

    Returns a JSON summary: valid, event_count, chain_breaks.
    Sensitive audit payload content is never included in the response.
    """
    logger = AuditLogger(db)
    config = request.app.state.config

    if tenant_id is not None:
        result = logger.verify_chain(tenant_id=tenant_id)
        return {
            "valid": result.valid,
            "event_count": result.event_count,
            "chain_breaks": result.chain_breaks,
            "tenants_verified": [tenant_id],
        }

    # Verify all tenants from config.
    tenant_ids = [t.id for t in config.tenants.tenants]
    all_valid = True
    total_events = 0
    all_breaks: list[str] = []

    for tid in tenant_ids:
        result = logger.verify_chain(tenant_id=tid)
        total_events += result.event_count
        if not result.valid:
            all_valid = False
            all_breaks.extend(result.chain_breaks)

    return {
        "valid": all_valid,
        "event_count": total_events,
        "chain_breaks": all_breaks,
        "tenants_verified": tenant_ids,
    }
