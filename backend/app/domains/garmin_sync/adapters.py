"""Infrastructure adapters for Garmin sync workflows.

Adapters translate workflow ports into SQLite ingest helpers, archive watcher
functions, the local archive layout, system clocks, and Garmin Connect client calls.
Garmin protocol constants stay private here because they are adapter details.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Protocol

from garminconnect import Garmin

from app.core.config import AppConfig, get_app_config
from app.domains.garmin_sync.dependencies import (
    GarminDownloadClient,
    GarminSyncDependencies,
)
from app.domains.garmin_sync.filesystem import (
    FilesystemSyncFileStore,
    extract_existing_archives,
)
from app.domains.garmin_sync.sqlite_ingest import DatabaseIngestGateway
from app.domains.garmin_sync.watcher import resume_watcher, suspend_watcher

_WELLNESS_ARCHIVE_PATH_PREFIX = "/download-service/files/wellness"
_MINIMUM_ARCHIVE_BYTES = 100
_REQUEST_SPACING_SECONDS = 1.0


class _RawGarminClient(Protocol):
    def download(self, path: str) -> bytes | bytearray | None: ...


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
