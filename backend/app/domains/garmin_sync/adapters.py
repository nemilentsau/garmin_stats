"""Infrastructure adapters for Garmin sync workflows."""

from __future__ import annotations

import logging
import os
import shutil
import time
from datetime import date
from pathlib import Path

from garminconnect import Garmin

from app.domains.garmin_sync.contracts import IngestResult, IngestStatus
from app.domains.garmin_sync.dependencies import (
    GarminDownloadClient,
    GarminSyncDependencies,
)
from app.infra.database import DATA_DIR, check_ingest_status, ingest_all, ingest_dates
from app.infra.watcher import extract_existing_archives, resume_watcher, suspend_watcher

log = logging.getLogger(__name__)


class DatabaseIngestGateway:
    def check_status(self, data_dir: Path) -> IngestStatus:
        return check_ingest_status(data_dir)

    def ingest_all(self, data_dir: Path) -> IngestResult:
        return ingest_all(data_dir)

    def ingest_dates(self, data_dir: Path, dates: list[str]) -> IngestResult:
        return ingest_dates(data_dir, dates)


class GarminConnectClientFactory:
    def __init__(self, token_dir: str | None = None) -> None:
        self._token_dir = token_dir

    def create(self) -> GarminDownloadClient:
        token_dir = self._token_dir or os.environ.get("GARMINTOKENS", "~/.garminconnect")
        token_path = os.path.expanduser(token_dir)
        if not os.path.isdir(token_path):
            raise RuntimeError(
                f"No Garmin tokens found at {token_path}. "
                "Run `scripts/download_garmin.py --login` first."
            )
        client = Garmin()
        client.login(token_path)
        return client


class FilesystemSyncFileStore:
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


def build_garmin_sync_dependencies(data_dir: Path = DATA_DIR) -> GarminSyncDependencies:
    return GarminSyncDependencies(
        data_dir=data_dir,
        ingest=DatabaseIngestGateway(),
        extract_archives=extract_existing_archives,
        suspend_watcher=suspend_watcher,
        resume_watcher=resume_watcher,
        clients=GarminConnectClientFactory(),
        files=FilesystemSyncFileStore(),
        today=date.today,
        monotonic=time.monotonic,
        sleep=time.sleep,
    )
