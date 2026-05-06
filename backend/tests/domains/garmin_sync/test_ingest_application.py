"""Tests for Garmin sync ingest application use cases."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from app.domains.garmin_sync.application.ingest import (
    GarminSyncDependencies,
    get_ingest_status,
    sync_garmin,
    trigger_ingest,
)
from app.models import IngestResult, IngestStatus


class FakeIngestGateway:
    def __init__(self) -> None:
        self.status = IngestStatus(
            needs_ingest=False,
            last_ingest_time="2026-03-15T00:00:00Z",
            days_in_db=2,
            days_on_disk=2,
        )
        self.ingest_all_result = IngestResult(days_ingested=2, duration_ms=50)
        self.ingest_dates_result = IngestResult(days_ingested=1, duration_ms=25)
        self.ingest_dates_error: RuntimeError | None = None
        self.calls: list[tuple[str, Path, list[str] | None]] = []

    def check_status(self, data_dir: Path) -> IngestStatus:
        self.calls.append(("status", data_dir, None))
        return self.status

    def ingest_all(self, data_dir: Path) -> IngestResult:
        self.calls.append(("ingest_all", data_dir, None))
        return self.ingest_all_result

    def ingest_dates(self, data_dir: Path, dates: list[str]) -> IngestResult:
        self.calls.append(("ingest_dates", data_dir, dates))
        if self.ingest_dates_error is not None:
            raise self.ingest_dates_error
        return self.ingest_dates_result


class FakeArchiveExtractor:
    def __init__(self) -> None:
        self.calls: list[Path] = []

    def extract_existing_archives(self, data_dir: Path) -> int:
        self.calls.append(data_dir)
        return 2


class FakeWatcherController:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def suspend(self) -> None:
        self.calls.append("suspend")

    def resume(self) -> None:
        self.calls.append("resume")


class FakeGarminClient:
    def __init__(self, responses: dict[str, bytes]) -> None:
        self.responses = responses
        self.urls: list[str] = []

    def download(self, path: str) -> bytes:
        self.urls.append(path)
        day = path.rsplit("/", maxsplit=1)[-1]
        return self.responses[day]


class FakeGarminClientFactory:
    def __init__(self, client: FakeGarminClient) -> None:
        self.client = client
        self.calls = 0

    def create(self) -> FakeGarminClient:
        self.calls += 1
        return self.client


class FakeSyncFileStore:
    def __init__(self, *, latest: date | None, existing: set[date]) -> None:
        self.latest = latest
        self.existing = existing
        self.deleted: list[tuple[Path, date]] = []
        self.written: list[tuple[Path, date, bytes]] = []

    def latest_zip_date(self, data_dir: Path) -> date | None:
        return self.latest

    def remove_day(self, data_dir: Path, day: date) -> None:
        self.deleted.append((data_dir, day))
        self.existing.discard(day)

    def zip_exists(self, data_dir: Path, day: date) -> bool:
        return day in self.existing

    def write_zip(self, data_dir: Path, day: date, data: bytes) -> None:
        self.written.append((data_dir, day, data))
        self.existing.add(day)


class FakeClock:
    def __init__(self, *, today: date) -> None:
        self._today = today
        self.monotonic_values = [10.0, 11.25]

    def today(self) -> date:
        return self._today

    def monotonic(self) -> float:
        return self.monotonic_values.pop(0)


class FakeSleeper:
    def __init__(self) -> None:
        self.calls: list[float] = []

    def sleep(self, seconds: float) -> None:
        self.calls.append(seconds)


def _deps(
    tmp_path: Path,
    *,
    latest: date | None = date(2026, 3, 14),
    existing: set[date] | None = None,
    responses: dict[str, bytes] | None = None,
) -> tuple[
    GarminSyncDependencies,
    FakeIngestGateway,
    FakeArchiveExtractor,
    FakeWatcherController,
    FakeGarminClient,
    FakeSyncFileStore,
    FakeSleeper,
]:
    ingest = FakeIngestGateway()
    archives = FakeArchiveExtractor()
    watcher = FakeWatcherController()
    client = FakeGarminClient(
        responses
        or {
            "2026-03-14": b"x" * 101,
            "2026-03-15": b"y" * 101,
        }
    )
    files = FakeSyncFileStore(
        latest=latest,
        existing=existing if existing is not None else {date(2026, 3, 15)},
    )
    sleeper = FakeSleeper()
    deps = GarminSyncDependencies(
        data_dir=tmp_path,
        ingest=ingest,
        archives=archives,
        watcher=watcher,
        clients=FakeGarminClientFactory(client),
        files=files,
        clock=FakeClock(today=date(2026, 3, 15)),
        sleeper=sleeper,
    )
    return deps, ingest, archives, watcher, client, files, sleeper


def test_trigger_ingest_reconciles_archives_before_ingesting(tmp_path: Path):
    deps, ingest, archives, *_ = _deps(tmp_path)

    result = trigger_ingest(deps)

    assert result == IngestResult(days_ingested=2, duration_ms=50)
    assert archives.calls == [tmp_path]
    assert ingest.calls == [("ingest_all", tmp_path, None)]


def test_get_ingest_status_reads_current_data_root_status(tmp_path: Path):
    deps, ingest, *_ = _deps(tmp_path)

    assert get_ingest_status(deps) == ingest.status
    assert ingest.calls == [("status", tmp_path, None)]


def test_sync_deletes_latest_day_downloads_range_and_ingests_affected_dates(
    tmp_path: Path,
):
    deps, ingest, archives, watcher, client, files, sleeper = _deps(tmp_path)

    result = sync_garmin(deps)

    assert result.downloaded == 1
    assert result.skipped == 1
    assert result.failed == 0
    assert result.deleted_latest == "2026-03-14"
    assert result.days_ingested == 1
    assert result.duration_ms == 1250
    assert files.deleted == [(tmp_path, date(2026, 3, 14))]
    assert files.written == [(tmp_path, date(2026, 3, 14), b"x" * 101)]
    assert client.urls == [
        "/download-service/files/wellness/2026-03-14",
    ]
    assert archives.calls == [tmp_path]
    assert ingest.calls == [("ingest_dates", tmp_path, ["2026-03-14"])]
    assert watcher.calls == ["suspend", "resume"]
    assert sleeper.calls == [1]


def test_sync_starts_with_yesterday_when_no_archives_exist(tmp_path: Path):
    deps, ingest, _archives, watcher, client, files, _sleeper = _deps(
        tmp_path,
        latest=None,
        existing=set(),
    )

    result = sync_garmin(deps)

    assert result.downloaded == 2
    assert result.deleted_latest is None
    assert files.deleted == []
    assert client.urls == [
        "/download-service/files/wellness/2026-03-14",
        "/download-service/files/wellness/2026-03-15",
    ]
    assert ingest.calls == [
        ("ingest_dates", tmp_path, ["2026-03-14", "2026-03-15"]),
    ]
    assert watcher.calls == ["suspend", "resume"]


def test_sync_resumes_watcher_when_ingest_fails(tmp_path: Path):
    deps, ingest, _archives, watcher, _client, _files, _sleeper = _deps(tmp_path)
    ingest.ingest_dates_error = RuntimeError("Ingest already in progress")

    with pytest.raises(RuntimeError, match="Ingest already in progress"):
        sync_garmin(deps)

    assert watcher.calls == ["suspend", "resume"]
