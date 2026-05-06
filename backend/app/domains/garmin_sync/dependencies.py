"""Dependency protocols for Garmin sync workflows."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Literal, Protocol

from app.domains.garmin_sync.contracts import IngestResult, IngestStatus

DownloadOutcome = Literal["downloaded", "skipped", "failed"]
ArchiveExtractor = Callable[[Path], int]
WatcherAction = Callable[[], None]
TodayProvider = Callable[[], date]
MonotonicClock = Callable[[], float]


class IngestGateway(Protocol):
    def check_status(self, data_dir: Path) -> IngestStatus: ...

    def ingest_all(self, data_dir: Path) -> IngestResult: ...

    def ingest_dates(self, data_dir: Path, dates: list[str]) -> IngestResult: ...


class GarminDownloadClient(Protocol):
    def download_wellness_archive(self, day: date) -> bytes | None: ...


class GarminClientFactory(Protocol):
    def create(self) -> GarminDownloadClient: ...


class SyncFileStore(Protocol):
    def latest_zip_date(self, data_dir: Path) -> date | None: ...

    def remove_day(self, data_dir: Path, day: date) -> None: ...

    def zip_exists(self, data_dir: Path, day: date) -> bool: ...

    def write_zip(self, data_dir: Path, day: date, data: bytes) -> None: ...


@dataclass(frozen=True)
class GarminSyncDependencies:
    data_dir: Path
    ingest: IngestGateway
    extract_archives: ArchiveExtractor
    suspend_watcher: WatcherAction
    resume_watcher: WatcherAction
    clients: GarminClientFactory
    files: SyncFileStore
    today: TodayProvider
    monotonic: MonotonicClock
