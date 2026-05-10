import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


def _new_uuid() -> str:
    return str(uuid.uuid4())


# ── Enums ─────────────────────────────────────────────────────────────────────

class DataClassification(str, Enum):
    PUBLIC = "PUBLIC"
    INTERNAL = "INTERNAL"
    CONFIDENTIAL = "CONFIDENTIAL"
    RESTRICTED = "RESTRICTED"


class TicketStatus(str, Enum):
    OPEN = "OPEN"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    IN_PROGRESS = "IN_PROGRESS"
    RESOLVED = "RESOLVED"
    ESCALATED = "ESCALATED"


# ── Ticket ────────────────────────────────────────────────────────────────────

class Ticket(Base):
    __tablename__ = "tickets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    channel: Mapped[str] = mapped_column(String(32), nullable=False)
    severity: Mapped[str] = mapped_column(String(8), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=TicketStatus.OPEN.value
    )
    category: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    component: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    subject: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    sla_deadline_response: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    sla_deadline_resolution: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    sla_breached: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    diagnostics: Mapped[list["Diagnostic"]] = relationship(
        "Diagnostic", back_populates="ticket", cascade="all, delete-orphan"
    )
    sla_state: Mapped[Optional["SLAState"]] = relationship(
        "SLAState", back_populates="ticket", uselist=False, cascade="all, delete-orphan"
    )


# ── AuditEvent ────────────────────────────────────────────────────────────────
# Uses an auto-increment integer PK so the insertion order is unambiguous —
# the chain is verified by iterating events in ascending id order.

class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    actor: Mapped[str] = mapped_column(String(128), nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    previous_hash: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    current_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


# ── Contact ───────────────────────────────────────────────────────────────────

class Contact(Base):
    __tablename__ = "contacts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    channel: Mapped[str] = mapped_column(String(32), nullable=False)
    external_id: Mapped[str] = mapped_column(String(256), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    role: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    email: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)


# ── Diagnostic ────────────────────────────────────────────────────────────────

class Diagnostic(Base):
    __tablename__ = "diagnostics"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    ticket_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tickets.id"), nullable=False, index=True
    )
    field_name: Mapped[str] = mapped_column(String(128), nullable=False)
    field_value: Mapped[str] = mapped_column(Text, nullable=False)
    classification: Mapped[str] = mapped_column(
        String(32), nullable=False, default=DataClassification.INTERNAL.value
    )
    collected_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )

    ticket: Mapped["Ticket"] = relationship("Ticket", back_populates="diagnostics")


# ── SLAState ──────────────────────────────────────────────────────────────────

class SLAState(Base):
    __tablename__ = "sla_states"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    ticket_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tickets.id"), nullable=False, unique=True
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=TicketStatus.OPEN.value
    )
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    in_progress_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    breached: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    breached_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    ticket: Mapped["Ticket"] = relationship("Ticket", back_populates="sla_state")


# ── ReplayGuard ───────────────────────────────────────────────────────────────
# Stores event_id fingerprints for replay protection (Phase 2 logic, storage only here).

class ReplayGuard(Base):
    __tablename__ = "replay_guard"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    event_id: Mapped[str] = mapped_column(
        String(256), nullable=False, unique=True, index=True
    )
    received_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
