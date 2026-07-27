"""Tests for Garmin sync data-directory watcher runtime behavior."""

import asyncio
import sqlite3
from pathlib import Path

from watchfiles import Change

import app.domains.garmin_sync.infra.watcher as watcher_mod
from app.domains.garmin_sync.contracts import (
    IngestResult,
    IngestStatus,
    RunningActivityIngestResult,
)


class _FakeIngest:
    def __init__(self, error: Exception | None = None) -> None:
        self.calls: list[Path] = []
        self.error = error

    def check_status(self, data_dir: Path) -> IngestStatus:
        raise AssertionError("check_status should not be used by watcher")

    def ingest_all(self, data_dir: Path) -> IngestResult:
        self.calls.append(data_dir)
        if self.error is not None:
            raise self.error
        return IngestResult(days_ingested=3, duration_ms=25)

    def ingest_dates(self, data_dir: Path, dates: list[str]) -> IngestResult:
        raise AssertionError("ingest_dates should not be used by watcher")

    def ingest_running_activities(
        self, activities_dir: Path, force: bool = False
    ) -> RunningActivityIngestResult:
        raise AssertionError("ingest_running_activities should not be used by watcher")


def test_changed_archive_extracts_ingests_refreshes_and_broadcasts(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    zip_path = data_dir / "2026-03-14.zip"
    extract_calls: list[list[Path]] = []
    ensured: list[Path] = []
    broadcasts: list[tuple[str, str]] = []
    refresh_calls: list[str] = []
    ingest = _FakeIngest()

    def fake_extract(zips: list[Path]) -> None:
        extract_calls.append(zips)
        # Simulate the FIT files appearing on disk so the fingerprint changes.
        (data_dir / "2026-03-14.fit").write_bytes(b"fitdata")

    async def broadcast(event: str, data: str) -> None:
        broadcasts.append((event, data))

    watcher = watcher_mod.DataDirectoryWatcher(
        data_dir=data_dir,
        ensure_data_dir=ensured.append,
        extract_archives=fake_extract,
        ingest=ingest,
        broadcast=broadcast,
    )
    watcher.prime()

    asyncio.run(
        watcher.handle_changes(
            {(Change.added, str(zip_path))},
            refresh_after_ingest=lambda: refresh_calls.append("refresh") or 1,
        )
    )

    assert ensured == [data_dir]
    assert extract_calls == [[zip_path]]
    assert ingest.calls == [data_dir]
    assert refresh_calls == ["refresh"]
    assert broadcasts == [("data_updated", "new_data")]


def test_suspended_watcher_skips_archive_work(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    zip_path = data_dir / "2026-03-14.zip"
    extract_calls: list[list[Path]] = []
    ingest = _FakeIngest()

    async def broadcast(_event: str, _data: str) -> None:
        raise AssertionError("broadcast should not run while suspended")

    watcher = watcher_mod.DataDirectoryWatcher(
        data_dir=data_dir,
        ensure_data_dir=lambda _data_dir: None,
        extract_archives=extract_calls.append,
        ingest=ingest,
        broadcast=broadcast,
    )
    watcher.prime()
    watcher.suspend()

    asyncio.run(watcher.handle_changes({(Change.added, str(zip_path))}))

    assert extract_calls == []
    assert ingest.calls == []


def _watcher_over_growing_tree(tmp_path, ingest: _FakeIngest):
    """A watcher whose extraction adds one FIT file per batch, moving the
    fingerprint every time so each batch reaches the ingest step."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    extracted: list[list[Path]] = []
    broadcasts: list[tuple[str, str]] = []

    def fake_extract(zips: list[Path]) -> None:
        extracted.append(zips)
        (data_dir / f"{len(extracted)}.fit").write_bytes(b"fitdata")

    async def broadcast(event: str, data: str) -> None:
        broadcasts.append((event, data))

    watcher = watcher_mod.DataDirectoryWatcher(
        data_dir=data_dir,
        ensure_data_dir=lambda _data_dir: None,
        extract_archives=fake_extract,
        ingest=ingest,
        broadcast=broadcast,
    )
    watcher.prime()
    return watcher, data_dir, broadcasts


def test_unexpected_ingest_failure_does_not_kill_the_watch_loop(tmp_path):
    """An unhandled exception used to end the async loop until process restart,
    silently stopping every later auto-ingest."""
    ingest = _FakeIngest(error=sqlite3.OperationalError("database is locked"))
    watcher, data_dir, broadcasts = _watcher_over_growing_tree(tmp_path, ingest)

    asyncio.run(watcher.handle_changes({(Change.added, str(data_dir / "2026-03-14.zip"))}))
    asyncio.run(watcher.handle_changes({(Change.added, str(data_dir / "2026-03-15.zip"))}))

    assert ingest.calls == [data_dir, data_dir]
    assert broadcasts == []


def test_failed_ingest_is_retried_on_the_next_change(tmp_path):
    """The fingerprint must not advance past a batch that never got ingested."""
    ingest = _FakeIngest(error=ValueError("parser blew up"))
    watcher, data_dir, broadcasts = _watcher_over_growing_tree(tmp_path, ingest)

    asyncio.run(watcher.handle_changes({(Change.added, str(data_dir / "2026-03-14.zip"))}))
    ingest.error = None
    asyncio.run(watcher.handle_changes({(Change.added, str(data_dir / "2026-03-15.zip"))}))

    assert len(ingest.calls) == 2
    assert broadcasts == [("data_updated", "new_data")]


def test_extraction_failure_does_not_kill_loop_or_advance_fingerprint(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    ingest = _FakeIngest()
    broadcasts: list[tuple[str, str]] = []
    extraction_calls = 0

    def extract(zips: list[Path]) -> None:
        nonlocal extraction_calls
        extraction_calls += 1
        if extraction_calls == 1:
            raise OSError("temporary archive read failure")
        (data_dir / "recovered.fit").write_bytes(b"fitdata")

    async def broadcast(event: str, data: str) -> None:
        broadcasts.append((event, data))

    watcher = watcher_mod.DataDirectoryWatcher(
        data_dir=data_dir,
        ensure_data_dir=lambda _data_dir: None,
        extract_archives=extract,
        ingest=ingest,
        broadcast=broadcast,
    )
    watcher.prime()

    asyncio.run(watcher.handle_changes({(Change.added, str(data_dir / "2026-03-14.zip"))}))
    asyncio.run(watcher.handle_changes({(Change.modified, str(data_dir / "2026-03-14.zip"))}))

    assert extraction_calls == 2
    assert ingest.calls == [data_dir]
    assert broadcasts == [("data_updated", "new_data")]


def test_fingerprint_failure_does_not_kill_loop_or_mark_batch_synced(
    tmp_path, monkeypatch
):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    ingest = _FakeIngest()
    broadcasts: list[tuple[str, str]] = []
    extraction_calls = 0

    def extract(_zips: list[Path]) -> None:
        nonlocal extraction_calls
        extraction_calls += 1
        (data_dir / f"{extraction_calls}.fit").write_bytes(b"fitdata")

    async def broadcast(event: str, data: str) -> None:
        broadcasts.append((event, data))

    watcher = watcher_mod.DataDirectoryWatcher(
        data_dir=data_dir,
        ensure_data_dir=lambda _data_dir: None,
        extract_archives=extract,
        ingest=ingest,
        broadcast=broadcast,
    )
    watcher.prime()
    real_fingerprint = watcher_mod.compute_data_fingerprint
    fingerprint_calls = 0

    def flaky_fingerprint(path: Path) -> str:
        nonlocal fingerprint_calls
        fingerprint_calls += 1
        if fingerprint_calls == 1:
            raise PermissionError("temporary metadata read failure")
        return real_fingerprint(path)

    monkeypatch.setattr(watcher_mod, "compute_data_fingerprint", flaky_fingerprint)

    asyncio.run(watcher.handle_changes({(Change.added, str(data_dir / "2026-03-14.zip"))}))
    asyncio.run(watcher.handle_changes({(Change.modified, str(data_dir / "2026-03-14.zip"))}))

    assert fingerprint_calls == 2
    assert ingest.calls == [data_dir]
    assert broadcasts == [("data_updated", "new_data")]


def test_concurrent_ingest_is_skipped_without_broadcasting(tmp_path):
    ingest = _FakeIngest(error=RuntimeError("Ingest already in progress"))
    watcher, data_dir, broadcasts = _watcher_over_growing_tree(tmp_path, ingest)

    asyncio.run(watcher.handle_changes({(Change.added, str(data_dir / "2026-03-14.zip"))}))

    assert ingest.calls == [data_dir]
    assert broadcasts == []


def test_unchanged_fingerprint_skips_ingest_after_extraction(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    zip_path = data_dir / "2026-03-14.zip"
    extract_calls: list[list[Path]] = []
    ingest = _FakeIngest()

    async def broadcast(_event: str, _data: str) -> None:
        raise AssertionError("broadcast should not run when ingest is skipped")

    watcher = watcher_mod.DataDirectoryWatcher(
        data_dir=data_dir,
        ensure_data_dir=lambda _data_dir: None,
        # Extraction touches no FIT files, so fingerprint stays unchanged.
        extract_archives=extract_calls.append,
        ingest=ingest,
        broadcast=broadcast,
    )
    watcher.prime()

    asyncio.run(watcher.handle_changes({(Change.modified, str(zip_path))}))

    assert extract_calls == [[zip_path]]
    assert ingest.calls == []
