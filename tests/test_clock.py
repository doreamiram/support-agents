"""Tests for ClockProvider, SystemClock, and FakeClock (app/utils/clock.py)."""

from datetime import datetime, timezone, timedelta

import pytest

from app.utils.clock import ClockProvider, FakeClock, SystemClock


# ── ClockProvider interface ───────────────────────────────────────────────────

class TestClockProviderInterface:
    def test_system_clock_is_clock_provider(self):
        assert isinstance(SystemClock(), ClockProvider)

    def test_fake_clock_is_clock_provider(self):
        assert isinstance(FakeClock(), ClockProvider)

    def test_clock_provider_has_now_method(self):
        for cls in (SystemClock, FakeClock):
            assert callable(getattr(cls, "now", None))


# ── SystemClock ───────────────────────────────────────────────────────────────

class TestSystemClock:
    def test_returns_datetime(self):
        now = SystemClock().now()
        assert isinstance(now, datetime)

    def test_returns_timezone_aware_datetime(self):
        now = SystemClock().now()
        assert now.tzinfo is not None

    def test_returns_utc_time(self):
        now = SystemClock().now()
        # UTC offset should be zero.
        assert now.utcoffset().total_seconds() == 0

    def test_two_calls_are_non_decreasing(self):
        clock = SystemClock()
        t1 = clock.now()
        t2 = clock.now()
        assert t2 >= t1


# ── FakeClock ─────────────────────────────────────────────────────────────────

class TestFakeClockStart:
    def test_default_start_is_deterministic(self):
        clock = FakeClock()
        expected = datetime(2026, 1, 1, 9, 0, 0, tzinfo=timezone.utc)
        assert clock.now() == expected

    def test_custom_start_is_returned(self):
        start = datetime(2026, 6, 15, 14, 30, 0, tzinfo=timezone.utc)
        clock = FakeClock(start=start)
        assert clock.now() == start

    def test_two_calls_without_advance_return_same_time(self):
        clock = FakeClock()
        assert clock.now() == clock.now()

    def test_returns_timezone_aware_datetime(self):
        assert FakeClock().now().tzinfo is not None


class TestFakeClockAdvance:
    def test_advance_minutes(self):
        clock = FakeClock()
        t0 = clock.now()
        clock.advance(minutes=30)
        assert clock.now() == t0 + timedelta(minutes=30)

    def test_advance_hours(self):
        clock = FakeClock()
        t0 = clock.now()
        clock.advance(hours=2)
        assert clock.now() == t0 + timedelta(hours=2)

    def test_advance_minutes_and_hours_combined(self):
        clock = FakeClock()
        t0 = clock.now()
        clock.advance(hours=1, minutes=15)
        assert clock.now() == t0 + timedelta(hours=1, minutes=15)

    def test_advance_accumulates(self):
        clock = FakeClock()
        t0 = clock.now()
        clock.advance(minutes=10)
        clock.advance(minutes=20)
        clock.advance(hours=1)
        assert clock.now() == t0 + timedelta(hours=1, minutes=30)

    def test_advance_zero_does_not_change_time(self):
        clock = FakeClock()
        t0 = clock.now()
        clock.advance(minutes=0, hours=0)
        assert clock.now() == t0

    def test_fake_clock_never_reads_real_time(self):
        """FakeClock is deterministic: repeated calls without advance stay equal."""
        clock = FakeClock()
        readings = [clock.now() for _ in range(5)]
        assert all(r == readings[0] for r in readings)
