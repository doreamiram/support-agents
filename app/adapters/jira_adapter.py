from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from app.config.models import AppConfig
from app.db.database import get_db
from app.db.repositories.replay_guard_repository import ReplayGuardRepository
from app.schemas.events import Channel, InboundEvent, JiraWebhookPayload, WebhookResponse
from app.services.identity_resolver import ContactNotVerifiedError, IdentityResolver
from app.services.injection_guard import InjectionGuard
from app.services.replay_guard import ReplayGuardService, ReplayRejectedError
from app.services.signature_verifier import SignatureVerificationError, SignatureVerifier

router = APIRouter(tags=["webhooks"])

_sig_verifier = SignatureVerifier()
_injection_guard = InjectionGuard()
_identity_resolver = IdentityResolver()


def normalize_jira_payload(
    payload: JiraWebhookPayload,
    *,
    tenant_id: str,
    contact_id: str,
    injection_flagged: bool,
    sanitized_body: str,
) -> InboundEvent:
    """Pure normalization — no side effects. Exported for unit testing."""
    return InboundEvent(
        event_id=payload.event_id,
        tenant_id=tenant_id,
        contact_id=contact_id,
        channel=Channel.JIRA,
        external_id=payload.reporter_email,
        timestamp=payload.timestamp,
        subject=payload.summary,
        body=sanitized_body,
        raw_payload=payload.model_dump(mode="json"),
        injection_flagged=injection_flagged,
    )


def _get_tenant(tenant_id: str, config: AppConfig):
    for t in config.tenants.tenants:
        if t.id == tenant_id:
            return t
    return None


@router.post("/webhooks/jira", summary="Simulated JIRA Service Desk webhook")
async def jira_webhook(
    request: Request,
    x_tenant_id: Annotated[str, Header()],
    x_webhook_signature: Annotated[str, Header()],
    db: Session = Depends(get_db),
) -> WebhookResponse:
    config: AppConfig = request.app.state.config
    body_bytes = await request.body()

    # 1. Resolve tenant
    tenant = _get_tenant(x_tenant_id, config)
    if tenant is None:
        raise HTTPException(status_code=403, detail=f"Unknown tenant: {x_tenant_id!r}")

    # 2. Verify signature
    try:
        _sig_verifier.verify(
            tenant_secret=tenant.webhook_secret,
            payload_bytes=body_bytes,
            signature_header=x_webhook_signature,
        )
    except SignatureVerificationError as exc:
        raise HTTPException(status_code=403, detail=str(exc))

    # 3. Parse payload
    try:
        payload = JiraWebhookPayload.model_validate_json(body_bytes)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid payload: {exc}")

    # 4. Replay protection
    replay_svc = ReplayGuardService(ReplayGuardRepository(db))
    try:
        replay_svc.check_and_record(event_id=payload.event_id, timestamp=payload.timestamp)
    except ReplayRejectedError as exc:
        code = 409 if "Duplicate" in str(exc) else 400
        raise HTTPException(status_code=code, detail=str(exc))

    # 5. Identity resolution
    try:
        tenant_cfg, contact_cfg = _identity_resolver.resolve(
            channel="jira",
            external_id=payload.reporter_email,
            config=config,
        )
    except ContactNotVerifiedError:
        raise HTTPException(
            status_code=403,
            detail="Contact not verified or not registered for this channel",
        )

    # 6. Injection guard (runs on the freetext description)
    injection = _injection_guard.scan(payload.description)

    # 7. Normalize → canonical InboundEvent
    event = normalize_jira_payload(
        payload,
        tenant_id=tenant_cfg.id,
        contact_id=contact_cfg.id,
        injection_flagged=injection.flagged,
        sanitized_body=injection.sanitized_text,
    )

    return WebhookResponse(
        status="accepted",
        event_id=event.event_id,
        tenant_id=event.tenant_id,
        contact_id=event.contact_id,
        channel=event.channel.value,
        injection_flagged=event.injection_flagged,
    )
