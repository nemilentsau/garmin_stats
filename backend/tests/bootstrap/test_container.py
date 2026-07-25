"""Tests for Coach/Garmin container independence."""

from __future__ import annotations

from app.bootstrap.container import build_container


def test_garmin_sync_has_no_coach_reaction_or_coverage_dependency(monkeypatch):
    monkeypatch.setenv("GARMIN_COACH_WORKER_ENABLED", "true")
    build_container.cache_clear()
    try:
        container = build_container()

        assert not hasattr(container.garmin_sync, "after_successful_sync")
        assert not hasattr(container.garmin_sync, "activity_coverage")
        assert not hasattr(container.coach_jobs, "activity_date_covered")
    finally:
        build_container.cache_clear()
