import os
from datetime import datetime, timezone

from app.db.repositories.replay_guard_repository import ReplayGuardRepository

_TOLERANCE_SECONDS: int = int(os.getenv("REPLAY_TOLERANCE_SECONDS", "300"))


class ReplayRejectedError(Exception):
    """Raised when an event is rejected as a replay or has a stale timestamp."""


class ReplayGuardService:
    """Stateful replay-protection service backed by the ReplayGuard repository."""

    def __init__(self, repo: ReplayGuardRepository) -> None:
        self.repo = repo

    def check_and_record(self, *, event_id: str, timestamp: datetime) -> None:
        """
        Validate and record an inbound event.

        Raises ``ReplayRejectedError`` when:
        - The timestamp is outside the configured tolerance window.
        - The event_id has already been seen.

        On success the event_id is recorded so future duplicates are rejected.
        """
        ts_naive = self._to_utc_naive(timestamp)
        now = datetime.utcnow()
        delta = abs((now - ts_naive).total_seconds())

        if delta > _TOLERANCE_SECONDS:
            raise ReplayRejectedError(
                f"Event timestamp is outside the {_TOLERANCE_SECONDS}s tolerance "
                f"window (delta={delta:.0f}s). Check clock skew or event staleness."
            )

        if self.repo.exists(event_id=event_id):
            raise ReplayRejectedError(
                f"Duplicate event_id rejected: {event_id!r}"
            )

        self.repo.record(event_id=event_id)

    @staticmethod
    def _to_utc_naive(dt: datetime) -> datetime:
        """Normalise a potentially timezone-aware datetime to a naive UTC datetime."""
        if dt.tzinfo is not None:
            return dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt
