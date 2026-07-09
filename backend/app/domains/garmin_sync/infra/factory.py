"""Production dependency wiring for Garmin sync workflows.

The factory builds one watcher and exposes it twice: as runtime background work
and as workflow callbacks for bulk sync. Sharing the instance keeps suspension
and fingerprint state consistent across startup, manual ingest, and Garmin sync.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from app.core.config import AppConfig, get_app_config
from app.domains.garmin_sync.dependencies import GarminSyncDependencies
from app.domains.garmin_sync.infra.activity_files import FilesystemActivityStore
from app.domains.garmin_sync.infra.filesystem import (
    FilesystemSyncFileStore,
    ensure_data_dir,
    extract_archives,
    extract_existing_archives,
)
from app.domains.garmin_sync.infra.garmin_connect import GarminConnectClientFactory
from app.domains.garmin_sync.infra.sqlite_ingest import DatabaseIngestGateway
from app.domains.garmin_sync.infra.watcher import DataDirectoryWatcher
from app.realtime.events import event_bus


@dataclass(frozen=True)
class GarminSyncInfra:
    """Concrete workflow dependencies plus the watcher used by process runtime."""

    dependencies: GarminSyncDependencies
    watcher: DataDirectoryWatcher


def build_garmin_sync_infra(
    config: AppConfig | None = None,
    data_dir: Path | None = None,
) -> GarminSyncInfra:
    """Wire Garmin sync ports to SQLite, filesystem, Garmin Connect, and SSE."""

    app_config = get_app_config() if config is None else config
    sync_data_dir = app_config.data_dir if data_dir is None else data_dir
    ingest = DatabaseIngestGateway()
    watcher = DataDirectoryWatcher(
        data_dir=sync_data_dir,
        ensure_data_dir=ensure_data_dir,
        extract_archives=extract_archives,
        ingest=ingest,
        broadcast=event_bus.broadcast,
    )
    dependencies = GarminSyncDependencies(
        data_dir=sync_data_dir,
        activities_dir=app_config.activities_dir,
        ingest=ingest,
        extract_archives=extract_existing_archives,
        suspend_watcher=watcher.suspend,
        resume_watcher=watcher.resume,
        mark_watcher_synced=watcher.mark_synced,
        clients=GarminConnectClientFactory(app_config.garmin_token_dir),
        files=FilesystemSyncFileStore(),
        activity_files=FilesystemActivityStore(),
        today=date.today,
        monotonic=time.monotonic,
    )
    return GarminSyncInfra(dependencies=dependencies, watcher=watcher)
