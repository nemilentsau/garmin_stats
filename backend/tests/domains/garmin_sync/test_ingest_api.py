"""Tests for Garmin sync HTTP routes."""

import pytest
from fastapi import HTTPException

import app.domains.garmin_sync.routes as ingest_mod
from app.domains.garmin_sync.contracts import IngestResult, IngestStatus, SyncResult


class _Container:
    garmin_sync = object()


class TestIngestRoutes:
    def test_trigger_ingest_uses_container_dependencies(self, monkeypatch):
        expected = IngestResult(days_ingested=45, duration_ms=987)

        monkeypatch.setattr(ingest_mod, "build_container", lambda: _Container())

        def fake_run_ingest(deps):
            assert deps is _Container.garmin_sync
            return expected

        monkeypatch.setattr(ingest_mod.workflows, "trigger_ingest", fake_run_ingest)

        assert ingest_mod.trigger_ingest() == expected

    def test_trigger_ingest_returns_409_when_ingest_busy(self, monkeypatch):
        monkeypatch.setattr(ingest_mod, "build_container", lambda: _Container())
        monkeypatch.setattr(
            ingest_mod.workflows,
            "trigger_ingest",
            lambda _deps: (_ for _ in ()).throw(RuntimeError("Ingest already in progress")),
        )

        with pytest.raises(HTTPException, match="Ingest already in progress") as exc_info:
            ingest_mod.trigger_ingest()

        assert exc_info.value.status_code == 409

    def test_get_ingest_status_uses_container_dependencies(self, monkeypatch):
        expected = IngestStatus(
            needs_ingest=True,
            last_ingest_time="2026-03-15T00:00:00Z",
            days_in_db=58,
            days_on_disk=72,
        )

        monkeypatch.setattr(ingest_mod, "build_container", lambda: _Container())

        def fake_read_ingest_status(deps):
            assert deps is _Container.garmin_sync
            return expected

        monkeypatch.setattr(
            ingest_mod.workflows,
            "get_ingest_status",
            fake_read_ingest_status,
        )

        assert ingest_mod.get_ingest_status() == expected

    def test_trigger_sync_uses_container_dependencies(self, monkeypatch):
        expected = SyncResult(
            downloaded=1,
            skipped=2,
            failed=0,
            days_ingested=1,
            duration_ms=123,
            activities_downloaded=3,
            activities_skipped=1,
            activities_failed=0,
        )

        monkeypatch.setattr(ingest_mod, "build_container", lambda: _Container())

        def fake_sync_garmin(deps):
            assert deps is _Container.garmin_sync
            return expected

        monkeypatch.setattr(ingest_mod.workflows, "sync_garmin", fake_sync_garmin)

        assert ingest_mod.trigger_sync() == expected

    def test_trigger_sync_returns_409_when_sync_cannot_start(self, monkeypatch):
        monkeypatch.setattr(ingest_mod, "build_container", lambda: _Container())
        monkeypatch.setattr(
            ingest_mod.workflows,
            "sync_garmin",
            lambda _deps: (_ for _ in ()).throw(RuntimeError("No Garmin tokens found")),
        )

        with pytest.raises(HTTPException, match="No Garmin tokens found") as exc_info:
            ingest_mod.trigger_sync()

        assert exc_info.value.status_code == 409
