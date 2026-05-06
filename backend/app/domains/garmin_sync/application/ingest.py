"""Garmin ingest and download sync use cases."""

from __future__ import annotations

import logging
from datetime import date

from app.models import IngestResult, IngestStatus, SyncResult

from .ports import DownloadOutcome, GarminDownloadClient, GarminSyncDependencies
from .sync_plan import plan_sync_dates

log = logging.getLogger(__name__)

DOWNLOAD_SERVICE_URL = "/download-service/files"
MIN_DOWNLOAD_BYTES = 100


def trigger_ingest(deps: GarminSyncDependencies) -> IngestResult:
    """Extract all known archives and re-ingest the configured data tree."""
    deps.archives.extract_existing_archives(deps.data_dir)
    return deps.ingest.ingest_all(deps.data_dir)


def get_ingest_status(deps: GarminSyncDependencies) -> IngestStatus:
    """Return whether the configured data tree differs from stored ingest state."""
    return deps.ingest.check_status(deps.data_dir)


def sync_garmin(deps: GarminSyncDependencies) -> SyncResult:
    """Download Garmin wellness archives for changed dates and ingest them."""
    t0 = deps.clock.monotonic()
    client = deps.clients.create()

    latest = deps.files.latest_zip_date(deps.data_dir)
    plan = plan_sync_dates(latest=latest, today=deps.clock.today())
    deleted_latest = plan.deleted_latest.isoformat() if plan.deleted_latest else None

    deps.watcher.suspend()
    try:
        if plan.deleted_latest is not None:
            deps.files.remove_day(deps.data_dir, plan.deleted_latest)

        downloaded = 0
        skipped = 0
        failed = 0
        affected_dates = list(plan.initial_affected_dates)

        for index, day in enumerate(plan.dates):
            result = _download_day(deps, client, day)
            if result == "downloaded":
                downloaded += 1
                affected_dates.append(day.isoformat())
            elif result == "skipped":
                skipped += 1
            else:
                failed += 1

            if index < len(plan.dates) - 1:
                deps.sleeper.sleep(1)

        deps.archives.extract_existing_archives(deps.data_dir)
        unique_dates = sorted(set(affected_dates))
        ingest_result = deps.ingest.ingest_dates(deps.data_dir, unique_dates)
    finally:
        deps.watcher.resume()

    duration_ms = int((deps.clock.monotonic() - t0) * 1000)
    return SyncResult(
        downloaded=downloaded,
        skipped=skipped,
        failed=failed,
        deleted_latest=deleted_latest,
        days_ingested=ingest_result.days_ingested,
        duration_ms=duration_ms,
    )


def _download_day(
    deps: GarminSyncDependencies,
    client: GarminDownloadClient,
    day: date,
) -> DownloadOutcome:
    date_str = day.isoformat()
    if deps.files.zip_exists(deps.data_dir, day):
        log.info("  %s: already exists, skipping", date_str)
        return "skipped"

    url = f"{DOWNLOAD_SERVICE_URL}/wellness/{date_str}"
    log.info("  %s: downloading...", date_str)
    try:
        data = client.download(url)
    except Exception:
        log.exception("  %s: download failed", date_str)
        return "failed"

    if not data or len(data) < MIN_DOWNLOAD_BYTES:
        log.info("  %s: no data available", date_str)
        return "failed"

    payload = bytes(data)
    deps.files.write_zip(deps.data_dir, day, payload)
    log.info("  %s: OK (%d bytes)", date_str, len(payload))
    return "downloaded"
