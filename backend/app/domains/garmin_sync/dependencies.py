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
from typing import Any, Literal, Protocol

from app.domains.garmin_sync.contracts import (
    IngestResult,
    IngestStatus,
    RunningActivityIngestResult,
)

DownloadOutcome = Literal["downloaded", "skipped", "failed"]
ArchiveExtractor = Callable[[Path], int]
WatcherAction = Callable[[], None]
TodayProvider = Callable[[], date]
MonotonicClock = Callable[[], float]
AfterSuccessfulSync = Callable[[], object]


def noop_after_sync() -> None:
    """Do nothing; the default post-sync hook when no reaction is wired."""
    return None


class IngestGateway(Protocol):
    """Persistence write/read port for Garmin source ingestion."""

    def check_status(self, data_dir: Path) -> IngestStatus: ...

    def ingest_all(self, data_dir: Path) -> IngestResult: ...

    def ingest_dates(self, data_dir: Path, dates: list[str]) -> IngestResult: ...

    def ingest_running_activities(
        self, activities_dir: Path, force: bool = False
    ) -> RunningActivityIngestResult: ...


@dataclass(frozen=True)
class ActivityRef:
    """One Garmin Connect activity listed for a date, with its raw metadata."""

    activity_id: str
    metadata: dict[str, Any]


class GarminDownloadClient(Protocol):
    """Logged-in Garmin client for wellness archives and activity payloads."""

    def download_wellness_archive(self, day: date) -> bytes | None: ...

    def list_activities(self, day: date) -> list[ActivityRef]: ...

    def download_activity_original(self, activity_id: str) -> bytes | None: ...


class GarminClientFactory(Protocol):
    """Factory for creating Garmin download clients from runtime credentials."""

    def create(self) -> GarminDownloadClient: ...


class SyncFileStore(Protocol):
    """Filesystem port for the local YYYY-MM-DD.zip / YYYY-MM-DD layout."""

    def latest_zip_date(self, data_dir: Path) -> date | None: ...

    def zip_exists(self, data_dir: Path, day: date) -> bool: ...

    def install_archive(self, data_dir: Path, day: date, data: bytes) -> None:
        """Validate, extract, and replace one day without corrupting old state."""
        ...


class ActivityFileStore(Protocol):
    """Filesystem port for the data/garmin_activities day-directory tree."""

    def has_activity(self, activities_dir: Path, day: date, activity_id: str) -> bool: ...

    def store_activity(
        self,
        activities_dir: Path,
        day: date,
        activity_id: str,
        metadata: dict[str, Any],
        payload: bytes,
    ) -> None: ...


@dataclass(frozen=True)
class GarminSyncDependencies:
    """Dependency bundle passed from bootstrap into sync workflow functions.

    Watcher callbacks are explicit because bulk sync has two distinct states:
    suspension gates file events, while mark_watcher_synced records that a
    successful ingest already covered the current disk fingerprint.
    """

    data_dir: Path
    activities_dir: Path
    ingest: IngestGateway
    extract_archives: ArchiveExtractor
    suspend_watcher: WatcherAction
    resume_watcher: WatcherAction
    mark_watcher_synced: WatcherAction
    clients: GarminClientFactory
    files: SyncFileStore
    activity_files: ActivityFileStore
    today: TodayProvider
    monotonic: MonotonicClock
    after_successful_sync: AfterSuccessfulSync = noop_after_sync
