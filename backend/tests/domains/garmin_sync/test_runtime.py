"""Tests for Garmin sync runtime startup reconciliation.

Startup owns archive reconciliation and full ingest decisions, but it should not
touch Garmin download clients, file-store mutation, or watcher state callbacks.
"""

from collections.abc import Callable
from dataclasses import replace
from datetime import date
from pathlib import Path

import app.domains.garmin_sync.infra.runtime as runtime_mod
from app.domains.garmin_sync.contracts import (
    IngestResult,
    IngestStatus,
    RunningActivityIngestResult,
)
from app.domains.garmin_sync.dependencies import GarminSyncDependencies
from app.domains.garmin_sync.infra.filesystem import extract_existing_archives


class _FakeIngest:
    def __init__(self, statuses: list[IngestStatus]) -> None:
        self._statuses = iter(statuses)
        self.calls: list[tuple[str, Path]] = []
        self.running_result = RunningActivityIngestResult(sessions_ingested=1)

    def check_status(self, data_dir: Path) -> IngestStatus:
        self.calls.append(("status", data_dir))
        return next(self._statuses)

    def ingest_all(self, data_dir: Path) -> IngestResult:
        self.calls.append(("ingest_all", data_dir))
        return IngestResult(days_ingested=72, duration_ms=321)

    def ingest_dates(self, data_dir: Path, dates: list[str]) -> IngestResult:
        self.calls.append(("ingest_dates", data_dir))
        return IngestResult(days_ingested=len(dates), duration_ms=321)

    def ingest_running_activities(
        self, activities_dir: Path, force: bool = False
    ) -> RunningActivityIngestResult:
        self.calls.append(("ingest_running_activities", activities_dir))
        return self.running_result


class _UnusedClientFactory:
    def create(self):
        raise AssertionError("client factory should not be used")


class _UnusedFileStore:
    def latest_zip_date(self, data_dir: Path):
        raise AssertionError("file store should not be used")

    def zip_exists(self, data_dir: Path, day):
        raise AssertionError("file store should not be used")

    def install_archive(self, data_dir: Path, day, data: bytes):
        raise AssertionError("file store should not be used")


class _UnusedActivityFileStore:
    def has_activity(self, activities_dir: Path, day, activity_id: str):
        raise AssertionError("activity file store should not be used")

    def store_activity(self, activities_dir: Path, day, activity_id: str, metadata, payload: bytes):
        raise AssertionError("activity file store should not be used")


def _make_deps(
    *,
    data_dir: Path,
    ingest: _FakeIngest,
    extract_archives: Callable[[Path], list[str]],
) -> GarminSyncDependencies:
    return GarminSyncDependencies(
        data_dir=data_dir,
        activities_dir=data_dir / "garmin_activities",
        ingest=ingest,
        extract_archives=extract_archives,
        suspend_watcher=lambda: None,
        resume_watcher=lambda: None,
        mark_watcher_synced=lambda: None,
        clients=_UnusedClientFactory(),
        files=_UnusedFileStore(),
        activity_files=_UnusedActivityFileStore(),
        today=lambda: date(2026, 3, 15),
        monotonic=lambda: 0.0,
    )


class TestStartupIngest:
    def test_refreshes_data_dependents_after_startup_changes(self):
        data_dir = Path("data")
        ingest = _FakeIngest([
            IngestStatus(
                needs_ingest=True,
                last_ingest_time=None,
                days_in_db=0,
                days_on_disk=72,
            )
        ])
        deps = _make_deps(
            data_dir=data_dir,
            ingest=ingest,
            extract_archives=lambda _data_dir: [],
        )
        refreshes: list[str] = []
        deps = replace(
            deps,
            after_data_change=lambda: refreshes.append("experiments") or 1,
        )

        runtime_mod.run_startup_ingest_if_needed(deps)

        assert refreshes == ["experiments"]

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
            return ["2026-03-13", "2026-03-14", "2026-03-15"]

        deps = _make_deps(
            data_dir=data_dir,
            ingest=ingest,
            extract_archives=fake_extract_existing_archives,
        )

        runtime_mod.run_startup_ingest_if_needed(deps)

        assert order == ["extract"]
        assert ingest.calls == [
            ("status", data_dir),
            ("ingest_all", data_dir),
            ("ingest_running_activities", data_dir / "garmin_activities"),
        ]

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
            extract_archives=lambda _data_dir: [],
        )

        runtime_mod.run_startup_ingest_if_needed(deps)

        assert ingest.calls == [
            ("status", data_dir),
            ("ingest_running_activities", data_dir / "garmin_activities"),
        ]

    def test_creates_missing_data_dir_and_skips_ingest_when_empty(self, tmp_path):
        data_dir = tmp_path / "fresh-data"
        assert not data_dir.exists()

        ingest = _FakeIngest([
            IngestStatus(
                needs_ingest=False,
                last_ingest_time=None,
                days_in_db=0,
                days_on_disk=0,
            )
        ])
        deps = _make_deps(
            data_dir=data_dir,
            ingest=ingest,
            extract_archives=extract_existing_archives,
        )

        runtime_mod.run_startup_ingest_if_needed(deps)

        assert data_dir.is_dir()
        assert ingest.calls == [
            ("status", data_dir),
            ("ingest_running_activities", data_dir / "garmin_activities"),
        ]

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
            return []

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
            ("ingest_running_activities", data_dir / "garmin_activities"),
            ("status", data_dir),
            ("ingest_running_activities", data_dir / "garmin_activities"),
        ]

    def test_startup_runs_activity_ingest_after_wellness_even_when_in_sync(self):
        """The activity-ingest call is unconditional: it runs after the wellness
        block on both the ingest-needed and already-in-sync branches, relying on
        the engine's own fingerprint gate to make a clean tree a no-op."""
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
            extract_archives=lambda _data_dir: [],
        )

        runtime_mod.run_startup_ingest_if_needed(deps)

        assert ("ingest_running_activities", data_dir / "garmin_activities") in ingest.calls
        assert "ingest_all" not in [call[0] for call in ingest.calls]
