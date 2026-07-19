"""Durable activity-sync coverage behavior."""

from datetime import date

from app.domains.garmin_sync.infra.activity_coverage import SqliteActivitySyncCoverage


def test_coverage_round_trip_and_incomplete_transition_are_idempotent():
    coverage = SqliteActivitySyncCoverage()
    day = date(2026, 7, 16)

    assert not coverage.is_covered(day.isoformat())

    coverage.mark_covered(day)
    coverage.mark_covered(day)
    assert coverage.is_covered(day.isoformat())

    coverage.mark_incomplete(day)
    coverage.mark_incomplete(day)
    assert not coverage.is_covered(day.isoformat())
