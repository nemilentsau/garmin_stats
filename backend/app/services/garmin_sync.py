"""Download new Garmin data and ingest it.

Finds the latest day on disk, deletes that day's zip (likely partial),
then downloads from that date through today, extracts, and ingests.
"""

from __future__ import annotations

import logging
import os
import time
from datetime import date, timedelta
from pathlib import Path

from garminconnect import Garmin

from ..infra.database import DATA_DIR, ingest_all
from ..infra.watcher import extract_existing_archives, resume_watcher, suspend_watcher
from ..models import SyncResult

log = logging.getLogger(__name__)

TOKEN_DIR = os.environ.get("GARMINTOKENS", "~/.garminconnect")
DOWNLOAD_SERVICE_URL = "/download-service/files"


def _init_client() -> Garmin:
    token_path = os.path.expanduser(TOKEN_DIR)
    if not os.path.isdir(token_path):
        raise RuntimeError(
            f"No Garmin tokens found at {token_path}. "
            "Run `scripts/download_garmin.py --login` first."
        )
    client = Garmin()
    client.login(token_path)
    return client


def _latest_zip_date(data_dir: Path) -> date | None:
    """Find the most recent YYYY-MM-DD.zip on disk."""
    zips: list[str] = []
    if not data_dir.exists():
        return None
    for p in data_dir.iterdir():
        if p.suffix == ".zip" and len(p.stem) == 10:
            try:
                date.fromisoformat(p.stem)
                zips.append(p.stem)
            except ValueError:
                continue
    if not zips:
        return None
    return date.fromisoformat(max(zips))


def _download_day(client: Garmin, day: date, data_dir: Path, *, force: bool = False) -> str:
    """Download a single day's zip. Returns 'downloaded', 'skipped', or 'failed'."""
    date_str = day.isoformat()
    zip_path = data_dir / f"{date_str}.zip"

    if zip_path.exists() and not force:
        log.info("  %s: already exists, skipping", date_str)
        return "skipped"

    url = f"{DOWNLOAD_SERVICE_URL}/wellness/{date_str}"
    log.info("  %s: downloading...", date_str)

    try:
        data = client.download(url)
    except Exception:
        log.exception("  %s: download failed", date_str)
        return "failed"

    if not data or len(data) < 100:
        log.info("  %s: no data available", date_str)
        return "failed"

    data_dir.mkdir(parents=True, exist_ok=True)
    zip_path.write_bytes(data)
    log.info("  %s: OK (%d bytes)", date_str, len(data))
    return "downloaded"


def sync_garmin(data_dir: Path | None = None) -> SyncResult:
    """Download new data from Garmin and ingest.

    1. Find latest zip date on disk.
    2. Delete that zip + extracted dir (likely partial data).
    3. Download from that date through today.
    4. Extract and ingest.
    """
    if data_dir is None:
        data_dir = DATA_DIR

    t0 = time.monotonic()
    client = _init_client()

    latest = _latest_zip_date(data_dir)
    today = date.today()
    deleted_latest: str | None = None

    # Suspend the file watcher so it doesn't race with our downloads
    suspend_watcher()
    try:
        if latest is not None:
            # Delete latest day — it likely has partial data
            deleted_latest = latest.isoformat()
            zip_path = data_dir / f"{deleted_latest}.zip"
            dir_path = data_dir / deleted_latest
            if zip_path.exists():
                zip_path.unlink()
                log.info("Deleted partial zip: %s", zip_path)
            if dir_path.exists():
                import shutil
                shutil.rmtree(dir_path)
                log.info("Deleted partial dir: %s", dir_path)
            start_date = latest
        else:
            # No data at all — download yesterday as default
            start_date = today - timedelta(days=1)

        # Build date range
        dates: list[date] = []
        current = start_date
        while current <= today:
            dates.append(current)
            current += timedelta(days=1)

        downloaded = 0
        skipped = 0
        failed = 0

        for i, day in enumerate(dates):
            result = _download_day(client, day, data_dir)
            if result == "downloaded":
                downloaded += 1
            elif result == "skipped":
                skipped += 1
            else:
                failed += 1

            # Rate-limit Garmin API requests
            if i < len(dates) - 1:
                time.sleep(1)

        # Extract and ingest
        extract_existing_archives(data_dir)
        ingest_result = ingest_all(data_dir)
    finally:
        resume_watcher()

    duration_ms = int((time.monotonic() - t0) * 1000)

    return SyncResult(
        downloaded=downloaded,
        skipped=skipped,
        failed=failed,
        deleted_latest=deleted_latest,
        days_ingested=ingest_result.days_ingested,
        duration_ms=duration_ms,
    )
