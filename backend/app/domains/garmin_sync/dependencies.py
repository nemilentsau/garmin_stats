"""Ports consumed by Garmin sync workflows.

Sync workflows download wellness archives, mutate the local data tree, and kick
off ingest through these protocols. Concrete Garmin Connect, filesystem,
watcher, clock, and SQLite details belong in the infra package.
"""

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
    """Persistence write/read port for Garmin source ingestion."""

    def check_status(self, data_dir: Path) -> IngestStatus: ...

    def ingest_all(self, data_dir: Path) -> IngestResult: ...

    def ingest_dates(self, data_dir: Path, dates: list[str]) -> IngestResult: ...


class GarminDownloadClient(Protocol):
    """Logged-in Garmin client capable of downloading one wellness archive."""

    def download_wellness_archive(self, day: date) -> bytes | None: ...


class GarminClientFactory(Protocol):
    """Factory for creating Garmin download clients from runtime credentials."""

    def create(self) -> GarminDownloadClient: ...


class SyncFileStore(Protocol):
    """Filesystem port for the local YYYY-MM-DD.zip / YYYY-MM-DD layout."""

    def latest_zip_date(self, data_dir: Path) -> date | None: ...

    def remove_day(self, data_dir: Path, day: date) -> None: ...

    def zip_exists(self, data_dir: Path, day: date) -> bool: ...

    def write_zip(self, data_dir: Path, day: date, data: bytes) -> None: ...


@dataclass(frozen=True)
class GarminSyncDependencies:
    """Dependency bundle passed from bootstrap into sync workflow functions.

    Watcher callbacks are explicit because bulk sync has two distinct states:
    suspension gates file events, while mark_watcher_synced records that a
    successful ingest already covered the current disk fingerprint.
    """

    data_dir: Path
    ingest: IngestGateway
    extract_archives: ArchiveExtractor
    suspend_watcher: WatcherAction
    resume_watcher: WatcherAction
    mark_watcher_synced: WatcherAction
    clients: GarminClientFactory
    files: SyncFileStore
    today: TodayProvider
    monotonic: MonotonicClock
