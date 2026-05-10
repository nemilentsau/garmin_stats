"""Garmin ingest and download sync workflows.

The manual sync workflow treats the latest local archive as possibly partial,
deletes it, downloads that day through today, extracts archives, and ingests only
affected dates. Filesystem, Garmin, clock, ingest, and watcher operations are
injected so this module stays policy-only.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, timedelta

from .contracts import IngestResult, IngestStatus, SyncResult
from .dependencies import DownloadOutcome, GarminDownloadClient, GarminSyncDependencies

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class _SyncDatePlan:
    """Dates to inspect plus dates already affected before downloads begin."""

    deleted_latest: date | None
    dates: list[date]
    initial_affected_dates: list[str]


def trigger_ingest(deps: GarminSyncDependencies) -> IngestResult:
    """Extract all known archives and re-ingest the configured data tree."""
    deps.extract_archives(deps.data_dir)
    return deps.ingest.ingest_all(deps.data_dir)


def get_ingest_status(deps: GarminSyncDependencies) -> IngestStatus:
    """Return whether the configured data tree differs from stored ingest state."""
    return deps.ingest.check_status(deps.data_dir)


def sync_garmin(deps: GarminSyncDependencies) -> SyncResult:
    """Refresh mutable Garmin archives and ingest the dates affected by sync.

    File watching is suspended while the workflow mutates the data directory.
    The watcher fingerprint is marked synced only after incremental ingest
    succeeds, so failed syncs still leave changed disk state detectable.
    """
    t0 = deps.monotonic()
    client = deps.clients.create()

    latest = deps.files.latest_zip_date(deps.data_dir)
    plan = _plan_sync_dates(latest=latest, today=deps.today())
    deleted_latest = plan.deleted_latest.isoformat() if plan.deleted_latest else None

    deps.suspend_watcher()
    try:
        if plan.deleted_latest is not None:
            deps.files.remove_day(deps.data_dir, plan.deleted_latest)

        downloaded = 0
        skipped = 0
        failed = 0
        affected_dates = list(plan.initial_affected_dates)

        for day in plan.dates:
            result = _download_day(deps, client, day)
            if result == "downloaded":
                downloaded += 1
                affected_dates.append(day.isoformat())
            elif result == "skipped":
                skipped += 1
            else:
                failed += 1

        deps.extract_archives(deps.data_dir)
        unique_dates = sorted(set(affected_dates))
        ingest_result = deps.ingest.ingest_dates(deps.data_dir, unique_dates)
        deps.mark_watcher_synced()
    finally:
        deps.resume_watcher()

    duration_ms = int((deps.monotonic() - t0) * 1000)
    return SyncResult(
        downloaded=downloaded,
        skipped=skipped,
        failed=failed,
        deleted_latest=deleted_latest,
        days_ingested=ingest_result.days_ingested,
        duration_ms=duration_ms,
    )


def _plan_sync_dates(*, latest: date | None, today: date) -> _SyncDatePlan:
    """Plan the smallest archive range that can refresh mutable Garmin data."""
    if latest is None:
        start_date = today - timedelta(days=1)
        deleted_latest = None
        initial_affected_dates: list[str] = []
    else:
        start_date = latest
        deleted_latest = latest
        initial_affected_dates = [latest.isoformat()]

    dates: list[date] = []
    current = start_date
    while current <= today:
        dates.append(current)
        current += timedelta(days=1)

    return _SyncDatePlan(
        deleted_latest=deleted_latest,
        dates=dates,
        initial_affected_dates=initial_affected_dates,
    )


def _download_day(
    deps: GarminSyncDependencies,
    client: GarminDownloadClient,
    day: date,
) -> DownloadOutcome:
    """Download one archive unless a local zip already satisfies the plan."""
    date_str = day.isoformat()
    if deps.files.zip_exists(deps.data_dir, day):
        log.info("  %s: already exists, skipping", date_str)
        return "skipped"

    log.info("  %s: downloading...", date_str)
    try:
        data = client.download_wellness_archive(day)
    except Exception:
        log.exception("  %s: download failed", date_str)
        return "failed"

    if data is None:
        log.info("  %s: no data available", date_str)
        return "failed"

    deps.files.write_zip(deps.data_dir, day, data)
    log.info("  %s: OK (%d bytes)", date_str, len(data))
    return "downloaded"
