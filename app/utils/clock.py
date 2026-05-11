from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone


class ClockProvider(ABC):
    """Abstract time source. Inject SystemClock in production, FakeClock in tests/demo."""

    @abstractmethod
    def now(self) -> datetime: ...


class SystemClock(ClockProvider):
    """Returns the real wall-clock time in UTC."""

    def now(self) -> datetime:
        return datetime.now(timezone.utc)


class FakeClock(ClockProvider):
    """
    Deterministic clock for tests and demo mode. Never reads real system time.

    Start time defaults to 2026-01-01T09:00:00Z when not provided.
    Use advance() to move time forward without sleeping.
    """

    def __init__(self, start: datetime | None = None) -> None:
        self._now: datetime = start or datetime(2026, 1, 1, 9, 0, 0, tzinfo=timezone.utc)

    def now(self) -> datetime:
        return self._now

    def advance(self, *, minutes: int = 0, hours: int = 0) -> None:
        """Move the fake clock forward by the given duration."""
        self._now += timedelta(minutes=minutes, hours=hours)
