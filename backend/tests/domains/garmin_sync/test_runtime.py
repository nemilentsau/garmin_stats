"""Tests for Garmin sync runtime startup reconciliation."""

from pathlib import Path

import app.domains.garmin_sync.infra.runtime as runtime_mod
from app.domains.garmin_sync.contracts import IngestResult, IngestStatus


class TestStartupIngest:
    def test_runs_ingest_after_reconciling_existing_archives(self, monkeypatch):
        order: list[str] = []

        def fake_extract_existing_archives(_data_dir):
            order.append("extract")
            return 3

        def fake_check_ingest_status(_data_dir):
            assert order == ["extract"]
            return IngestStatus(
                needs_ingest=True,
                last_ingest_time="2026-03-15T00:00:00Z",
                days_in_db=58,
                days_on_disk=72,
            )

        expected = IngestResult(days_ingested=72, duration_ms=321)

        def fake_ingest_all(_data_dir):
            order.append("ingest")
            return expected

        monkeypatch.setattr(
            runtime_mod,
            "extract_existing_archives",
            fake_extract_existing_archives,
        )
        monkeypatch.setattr(runtime_mod, "check_ingest_status", fake_check_ingest_status)
        monkeypatch.setattr(runtime_mod, "ingest_all", fake_ingest_all)

        runtime_mod.run_startup_ingest_if_needed(Path("data"))

        assert order == ["extract", "ingest"]

    def test_skips_ingest_when_disk_state_matches_database(self, monkeypatch):
        monkeypatch.setattr(runtime_mod, "extract_existing_archives", lambda _data_dir: 0)
        monkeypatch.setattr(
            runtime_mod,
            "check_ingest_status",
            lambda _data_dir: IngestStatus(
                needs_ingest=False,
                last_ingest_time="2026-03-15T00:00:00Z",
                days_in_db=72,
                days_on_disk=72,
            ),
        )
        monkeypatch.setattr(
            runtime_mod,
            "ingest_all",
            lambda _data_dir: (_ for _ in ()).throw(
                AssertionError("ingest_all should not run")
            ),
        )

        runtime_mod.run_startup_ingest_if_needed(Path("data"))

    def test_second_startup_run_is_a_no_op_after_initial_ingest(self, monkeypatch):
        order: list[str] = []
        statuses = iter(
            [
                IngestStatus(
                    needs_ingest=True,
                    last_ingest_time="2026-03-15T00:00:00Z",
                    days_in_db=0,
                    days_on_disk=72,
                ),
                IngestStatus(
                    needs_ingest=False,
                    last_ingest_time="2026-03-15T00:05:21Z",
                    days_in_db=72,
                    days_on_disk=72,
                ),
            ]
        )

        def fake_extract_existing_archives(_data_dir):
            order.append("extract")
            return 0

        def fake_check_ingest_status(_data_dir):
            order.append("status")
            return next(statuses)

        def fake_ingest_all(_data_dir):
            order.append("ingest")
            return IngestResult(days_ingested=72, duration_ms=321)

        monkeypatch.setattr(
            runtime_mod,
            "extract_existing_archives",
            fake_extract_existing_archives,
        )
        monkeypatch.setattr(runtime_mod, "check_ingest_status", fake_check_ingest_status)
        monkeypatch.setattr(runtime_mod, "ingest_all", fake_ingest_all)

        data_dir = Path("data")
        runtime_mod.run_startup_ingest_if_needed(data_dir)
        runtime_mod.run_startup_ingest_if_needed(data_dir)

        assert order == ["extract", "status", "ingest", "extract", "status"]
