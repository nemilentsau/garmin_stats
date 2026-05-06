"""Dependency protocols for Garmin sync workflows."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Literal, Protocol

from app.models import IngestResult, IngestStatus

DownloadOutcome = Literal["downloaded", "skipped", "failed"]


class IngestGateway(Protocol):
    def check_status(self, data_dir: Path) -> IngestStatus: ...

    def ingest_all(self, data_dir: Path) -> IngestResult: ...

    def ingest_dates(self, data_dir: Path, dates: list[str]) -> IngestResult: ...


class ArchiveExtractor(Protocol):
    def extract_existing_archives(self, data_dir: Path) -> int: ...


class WatcherControl(Protocol):
    def suspend(self) -> None: ...

    def resume(self) -> None: ...


class GarminDownloadClient(Protocol):
    def download(self, path: str) -> bytes | bytearray | None: ...


class GarminClientFactory(Protocol):
    def create(self) -> GarminDownloadClient: ...


class SyncFileStore(Protocol):
    def latest_zip_date(self, data_dir: Path) -> date | None: ...

    def remove_day(self, data_dir: Path, day: date) -> None: ...

    def zip_exists(self, data_dir: Path, day: date) -> bool: ...

    def write_zip(self, data_dir: Path, day: date, data: bytes) -> None: ...


class Clock(Protocol):
    def today(self) -> date: ...

    def monotonic(self) -> float: ...


class Sleeper(Protocol):
    def sleep(self, seconds: float) -> None: ...


@dataclass(frozen=True)
class GarminSyncDependencies:
    data_dir: Path
    ingest: IngestGateway
    archives: ArchiveExtractor
    watcher: WatcherControl
    clients: GarminClientFactory
    files: SyncFileStore
    clock: Clock
    sleeper: Sleeper
