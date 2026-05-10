"""Production dependency wiring for Garmin sync workflows."""

from __future__ import annotations

import time
from datetime import date
from pathlib import Path

from app.core.config import AppConfig, get_app_config
from app.domains.garmin_sync.dependencies import GarminSyncDependencies
from app.domains.garmin_sync.infra.filesystem import (
    FilesystemSyncFileStore,
    extract_existing_archives,
)
from app.domains.garmin_sync.infra.garmin_connect import GarminConnectClientFactory
from app.domains.garmin_sync.infra.sqlite_ingest import DatabaseIngestGateway
from app.domains.garmin_sync.infra.watcher import resume_watcher, suspend_watcher


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
