"""Tests for Garmin sync runtime startup reconciliation."""

from datetime import date
from pathlib import Path

import app.domains.garmin_sync.infra.runtime as runtime_mod
from app.domains.garmin_sync.contracts import IngestResult, IngestStatus
from app.domains.garmin_sync.dependencies import GarminSyncDependencies


class _FakeIngest:
    def __init__(self, statuses: list[IngestStatus]) -> None:
        self._statuses = iter(statuses)
        self.calls: list[tuple[str, Path]] = []

    def check_status(self, data_dir: Path) -> IngestStatus:
        self.calls.append(("status", data_dir))
        return next(self._statuses)

    def ingest_all(self, data_dir: Path) -> IngestResult:
        self.calls.append(("ingest_all", data_dir))
        return IngestResult(days_ingested=72, duration_ms=321)

    def ingest_dates(self, data_dir: Path, dates: list[str]) -> IngestResult:
        self.calls.append(("ingest_dates", data_dir))
        return IngestResult(days_ingested=len(dates), duration_ms=321)


class _UnusedClientFactory:
    def create(self):
        raise AssertionError("client factory should not be used")


class _UnusedFileStore:
    def latest_zip_date(self, data_dir: Path):
        raise AssertionError("file store should not be used")

    def remove_day(self, data_dir: Path, day):
        raise AssertionError("file store should not be used")

    def zip_exists(self, data_dir: Path, day):
        raise AssertionError("file store should not be used")

    def write_zip(self, data_dir: Path, day, data: bytes):
        raise AssertionError("file store should not be used")


def _make_deps(
    *,
    data_dir: Path,
    ingest: _FakeIngest,
    extract_archives,
) -> GarminSyncDependencies:
    return GarminSyncDependencies(
        data_dir=data_dir,
        ingest=ingest,
        extract_archives=extract_archives,
        suspend_watcher=lambda: None,
        resume_watcher=lambda: None,
        mark_watcher_synced=lambda: None,
        clients=_UnusedClientFactory(),
        files=_UnusedFileStore(),
        today=lambda: date(2026, 3, 15),
        monotonic=lambda: 0.0,
    )


class TestStartupIngest:
    def test_runs_ingest_after_reconciling_existing_archives(self):
        order: list[str] = []
        data_dir = Path("data")
        ingest = _FakeIngest([
            IngestStatus(
                needs_ingest=True,
                last_ingest_time="2026-03-15T00:00:00Z",
                days_in_db=58,
                days_on_disk=72,
            )
        ])

        def fake_extract_existing_archives(_data_dir):
            assert _data_dir == data_dir
            order.append("extract")
            return 3

        deps = _make_deps(
            data_dir=data_dir,
            ingest=ingest,
            extract_archives=fake_extract_existing_archives,
        )

        runtime_mod.run_startup_ingest_if_needed(deps)

        assert order == ["extract"]
        assert ingest.calls == [("status", data_dir), ("ingest_all", data_dir)]

    def test_skips_ingest_when_disk_state_matches_database(self):
        data_dir = Path("data")
        ingest = _FakeIngest([
            IngestStatus(
                needs_ingest=False,
                last_ingest_time="2026-03-15T00:00:00Z",
                days_in_db=72,
                days_on_disk=72,
            )
        ])
        deps = _make_deps(
            data_dir=data_dir,
            ingest=ingest,
            extract_archives=lambda _data_dir: 0,
        )

        runtime_mod.run_startup_ingest_if_needed(deps)

        assert ingest.calls == [("status", data_dir)]

    def test_second_startup_run_is_a_no_op_after_initial_ingest(self):
        data_dir = Path("data")
        order: list[str] = []
        ingest = _FakeIngest([
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
        ])

        def fake_extract_existing_archives(_data_dir):
            order.append("extract")
            return 0

        deps = _make_deps(
            data_dir=data_dir,
            ingest=ingest,
            extract_archives=fake_extract_existing_archives,
        )

        runtime_mod.run_startup_ingest_if_needed(deps)
        runtime_mod.run_startup_ingest_if_needed(deps)

        assert order == ["extract", "extract"]
        assert ingest.calls == [
            ("status", data_dir),
            ("ingest_all", data_dir),
            ("status", data_dir),
        ]
