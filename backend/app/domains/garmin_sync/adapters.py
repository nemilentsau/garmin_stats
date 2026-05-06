"""Infrastructure adapters for Garmin sync workflows.

Adapters translate workflow ports into SQLite ingest helpers, archive watcher
functions, the local archive layout, system clocks, and Garmin Connect client calls.
Garmin protocol constants stay private here because they are adapter details.
"""

from __future__ import annotations

import logging
import shutil
import time
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Protocol

from garminconnect import Garmin

from app.core.config import AppConfig, get_app_config
from app.domains.garmin_sync.contracts import IngestResult, IngestStatus
from app.domains.garmin_sync.dependencies import (
    GarminDownloadClient,
    GarminSyncDependencies,
)
from app.infra.database import check_ingest_status, ingest_all, ingest_dates
from app.infra.watcher import extract_existing_archives, resume_watcher, suspend_watcher

log = logging.getLogger(__name__)

_WELLNESS_ARCHIVE_PATH_PREFIX = "/download-service/files/wellness"
_MINIMUM_ARCHIVE_BYTES = 100
_REQUEST_SPACING_SECONDS = 1.0


class _RawGarminClient(Protocol):
    def download(self, path: str) -> bytes | bytearray | None: ...


class DatabaseIngestGateway:
    """Adapt existing database ingest functions to the workflow ingest port."""

    def check_status(self, data_dir: Path) -> IngestStatus:
        return check_ingest_status(data_dir)

    def ingest_all(self, data_dir: Path) -> IngestResult:
        return ingest_all(data_dir)

    def ingest_dates(self, data_dir: Path, dates: list[str]) -> IngestResult:
        return ingest_dates(data_dir, dates)


class GarminConnectWellnessClient:
    """Download daily wellness archives through the logged-in Garmin Connect client."""

    def __init__(
        self,
        client: _RawGarminClient,
        *,
        sleep: Callable[[float], None],
        request_spacing_seconds: float = _REQUEST_SPACING_SECONDS,
    ) -> None:
        self._client = client
        self._sleep = sleep
        self._request_spacing_seconds = request_spacing_seconds
        self._has_requested = False

    def download_wellness_archive(self, day: date) -> bytes | None:
        if self._has_requested:
            self._sleep(self._request_spacing_seconds)
        self._has_requested = True

        data = self._client.download(f"{_WELLNESS_ARCHIVE_PATH_PREFIX}/{day.isoformat()}")
        if not data or len(data) < _MINIMUM_ARCHIVE_BYTES:
            return None
        return bytes(data)


class GarminConnectClientFactory:
    """Create Garmin wellness download clients from saved token-directory login state."""

    def __init__(self, token_dir: Path) -> None:
        self._token_dir = token_dir

    def create(self) -> GarminDownloadClient:
        token_path = self._token_dir
        if not token_path.is_dir():
            raise RuntimeError(
                f"No Garmin tokens found at {token_path}. "
                "Run `scripts/download_garmin.py --login` first."
            )
        client = Garmin()
        client.login(str(token_path))
        return GarminConnectWellnessClient(client, sleep=time.sleep)


class FilesystemSyncFileStore:
    """Read and mutate the local YYYY-MM-DD.zip / YYYY-MM-DD archive layout."""

    def latest_zip_date(self, data_dir: Path) -> date | None:
        zips: list[str] = []
        if not data_dir.exists():
            return None
        for path in data_dir.iterdir():
            if path.suffix != ".zip" or len(path.stem) != 10:
                continue
            try:
                date.fromisoformat(path.stem)
            except ValueError:
                continue
            zips.append(path.stem)
        if not zips:
            return None
        return date.fromisoformat(max(zips))

    def remove_day(self, data_dir: Path, day: date) -> None:
        date_str = day.isoformat()
        zip_path = data_dir / f"{date_str}.zip"
        dir_path = data_dir / date_str
        if zip_path.exists():
            zip_path.unlink()
            log.info("Deleted partial zip: %s", zip_path)
        if dir_path.exists():
            shutil.rmtree(dir_path)
            log.info("Deleted partial dir: %s", dir_path)

    def zip_exists(self, data_dir: Path, day: date) -> bool:
        return (data_dir / f"{day.isoformat()}.zip").exists()

    def write_zip(self, data_dir: Path, day: date, data: bytes) -> None:
        data_dir.mkdir(parents=True, exist_ok=True)
        (data_dir / f"{day.isoformat()}.zip").write_bytes(data)


def build_garmin_sync_dependencies(
    config: AppConfig | None = None,
    data_dir: Path | None = None,
) -> GarminSyncDependencies:
    """Wire production implementations for the Garmin sync workflow."""

    app_config = get_app_config() if config is None else config
    sync_data_dir = app_config.data_dir if data_dir is None else data_dir
    return GarminSyncDependencies(
        data_dir=sync_data_dir,
        ingest=DatabaseIngestGateway(),
        extract_archives=extract_existing_archives,
        suspend_watcher=suspend_watcher,
        resume_watcher=resume_watcher,
        clients=GarminConnectClientFactory(app_config.garmin_token_dir),
        files=FilesystemSyncFileStore(),
        today=date.today,
        monotonic=time.monotonic,
    )
