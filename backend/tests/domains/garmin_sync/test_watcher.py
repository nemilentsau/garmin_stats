"""Tests for Garmin sync data-directory watcher runtime behavior."""

import asyncio
from pathlib import Path

from watchfiles import Change

import app.domains.garmin_sync.infra.watcher as watcher_mod
from app.domains.garmin_sync.contracts import IngestResult, IngestStatus


class _FakeIngest:
    def __init__(self) -> None:
        self.calls: list[Path] = []

    def check_status(self, data_dir: Path) -> IngestStatus:
        raise AssertionError("check_status should not be used by watcher")

    def ingest_all(self, data_dir: Path) -> IngestResult:
        self.calls.append(data_dir)
        return IngestResult(days_ingested=3, duration_ms=25)

    def ingest_dates(self, data_dir: Path, dates: list[str]) -> IngestResult:
        raise AssertionError("ingest_dates should not be used by watcher")


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
