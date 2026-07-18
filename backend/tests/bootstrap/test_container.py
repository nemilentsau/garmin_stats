"""Tests for the post-sync coach reconcile hook wired into the container.

`build_container` is process-cached (`lru_cache`); each test clears the cache
before and after so the flag-driven wiring under test does not leak into
other tests that build the container against real env defaults.
"""

from __future__ import annotations

from app.bootstrap.container import build_container
from app.domains.coach.application.jobs import CoachJobs
from app.domains.garmin_sync.dependencies import noop_after_sync


def test_disabled_coach_worker_wires_noop_post_sync_hook(monkeypatch):
    monkeypatch.setenv("GARMIN_COACH_WORKER_ENABLED", "false")
    build_container.cache_clear()
    try:
        container = build_container()

        assert container.garmin_sync.after_successful_sync is noop_after_sync
    finally:
        build_container.cache_clear()


def test_enabled_coach_worker_wires_reconcile_pending_as_post_sync_hook(monkeypatch):
    monkeypatch.setenv("GARMIN_COACH_WORKER_ENABLED", "true")
    build_container.cache_clear()
    try:
        container = build_container()
        hook = container.garmin_sync.after_successful_sync

        assert getattr(hook, "__func__", None) is CoachJobs.reconcile_pending
        assert getattr(hook, "__self__", None) is container.coach_jobs
        coverage_reader = container.coach_jobs.activity_date_covered
        assert getattr(coverage_reader, "__self__", None) is container.garmin_sync.activity_coverage
    finally:
        build_container.cache_clear()
