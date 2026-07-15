"""Canonical Coach lifecycle timestamp formatting."""

from __future__ import annotations

from datetime import UTC, date, datetime

from app.domains.coach import time as coach_time
from app.domains.coach.time import local_today_iso, utc_cutoff_iso


def test_utc_now_uses_fixed_width_microseconds_at_exact_second(monkeypatch):
    class FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            assert tz is UTC
            return cls(2026, 7, 20, tzinfo=UTC)

    monkeypatch.setattr(coach_time, "datetime", FrozenDatetime)

    assert coach_time.utc_now_iso() == "2026-07-20T00:00:00.000000Z"


def test_utc_cutoff_normalizes_exact_second_to_fixed_width_microseconds():
    assert utc_cutoff_iso("2026-07-20T00:00:00Z") == (
        "2026-07-20T00:00:00.000000Z"
    )


def test_utc_cutoff_pads_fractional_timestamp_to_fixed_width_microseconds():
    assert utc_cutoff_iso("2026-07-20T00:00:00.5Z") == (
        "2026-07-20T00:00:00.500000Z"
    )


def test_local_today_returns_ten_character_local_calendar_date():
    result = local_today_iso()

    assert len(result) == 10
    assert date.fromisoformat(result) is not None
