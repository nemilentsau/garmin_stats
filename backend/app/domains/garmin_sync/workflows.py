"""Garmin ingest and download sync workflows.

The manual sync workflow treats the latest local archive as mutable, safely
replaces it, downloads that day through today, and ingests only affected dates.
Filesystem, Garmin, clock, ingest, and watcher operations are injected so this
module stays policy-only.

Sync also sweeps a short activity window (the wellness range plus a lookback for
late uploads) to download any new Garmin Connect activity FIT files, then runs
the running-activity ingest immediately after that sweep so newly downloaded
sessions land in `running_activity_*` within the same sync call. The activities
tree is neither watched nor incrementally ingested by date, so both the sweep
and the ingest run outside watcher suspension and do not affect wellness ingest
counters.
"""

from __future__ import annotations

import logging
import zipfile
from dataclasses import dataclass
from datetime import date, timedelta

from .contracts import IngestResult, IngestStatus, SyncResult
from .data_change import notify_data_changed
from .dependencies import DownloadOutcome, GarminDownloadClient, GarminSyncDependencies

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class _SyncDatePlan:
    """Dates to inspect and the existing mutable day that must be refreshed."""

    refresh_latest: date | None
    dates: list[date]


def trigger_ingest(deps: GarminSyncDependencies) -> IngestResult:
    """Extract all known archives and re-ingest the configured data tree."""
    deps.extract_archives(deps.data_dir)
    result = deps.ingest.ingest_all(deps.data_dir)
    notify_data_changed(deps)
    return result


def get_ingest_status(deps: GarminSyncDependencies) -> IngestStatus:
    """Return whether the configured data tree differs from stored ingest state."""
    return deps.ingest.check_status(deps.data_dir)


def sync_garmin(deps: GarminSyncDependencies) -> SyncResult:
    """Refresh mutable Garmin archives and ingest the dates affected by sync.

    File watching is suspended while the workflow mutates the data directory.
    The watcher fingerprint is marked synced only after incremental ingest
    succeeds, so failed syncs still leave changed disk state detectable. The
    activity sweep runs after watcher resumption because the activities tree
    is neither watched nor ingested.
    """
    t0 = deps.monotonic()
    client = deps.clients.create()
    today = deps.today()

    latest = deps.files.latest_zip_date(deps.data_dir)
    plan = _plan_sync_dates(latest=latest, today=today)
    deps.suspend_watcher()
    try:
        downloaded = 0
        skipped = 0
        failed = 0
        affected_dates: list[str] = []

        for day in plan.dates:
            result = _download_day(
                deps,
                client,
                day,
                force_refresh=day == plan.refresh_latest,
            )
            if result == "downloaded":
                downloaded += 1
                affected_dates.append(day.isoformat())
            elif result == "skipped":
                skipped += 1
            else:
                failed += 1

        # Extraction also refreshes archives replaced outside the app, which the
        # download loop knows nothing about. Ingesting that union keeps the
        # whole-tree fingerprint stamped below truthful.
        extracted_dates = deps.extract_archives(deps.data_dir)
        unique_dates = sorted(set(affected_dates) | set(extracted_dates))
        ingest_result = deps.ingest.ingest_dates(deps.data_dir, unique_dates)
        deps.mark_watcher_synced()
    finally:
        deps.resume_watcher()

    activity_days = _plan_activity_dates(
        wellness_start=plan.dates[0] if plan.dates else today, today=today
    )
    activities_downloaded, activities_skipped, activities_failed = _sync_activities(
        deps, client, activity_days
    )
    runs_result = deps.ingest.ingest_running_activities(deps.activities_dir)
    notify_data_changed(deps)

    duration_ms = int((deps.monotonic() - t0) * 1000)
    return SyncResult(
        downloaded=downloaded,
        skipped=skipped,
        failed=failed,
        days_ingested=ingest_result.days_ingested,
        duration_ms=duration_ms,
        activities_downloaded=activities_downloaded,
        activities_skipped=activities_skipped,
        activities_failed=activities_failed,
        runs_ingested=runs_result.sessions_ingested,
        runs_ingest_failed=runs_result.files_failed,
    )


def _plan_sync_dates(*, latest: date | None, today: date) -> _SyncDatePlan:
    """Plan the smallest archive range that can refresh mutable Garmin data."""
    if latest is None:
        start_date = today - timedelta(days=1)
        refresh_latest = None
    else:
        start_date = latest
        refresh_latest = latest

    dates: list[date] = []
    current = start_date
    while current <= today:
        dates.append(current)
        current += timedelta(days=1)

    return _SyncDatePlan(
        refresh_latest=refresh_latest,
        dates=dates,
    )


def _download_day(
    deps: GarminSyncDependencies,
    client: GarminDownloadClient,
    day: date,
    *,
    force_refresh: bool = False,
) -> DownloadOutcome:
    """Download one archive unless a local zip already satisfies the plan."""
    date_str = day.isoformat()
    if not force_refresh and deps.files.zip_exists(deps.data_dir, day):
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

    try:
        deps.files.install_archive(deps.data_dir, day, data)
    except (OSError, ValueError, zipfile.BadZipFile):
        log.exception("  %s: archive installation failed", date_str)
        return "failed"
    log.info("  %s: OK (%d bytes)", date_str, len(data))
    return "downloaded"


_ACTIVITY_LOOKBACK_DAYS = 3


def _plan_activity_dates(*, wellness_start: date, today: date) -> list[date]:
    """Sweep the wellness window plus a short lookback for late activity uploads."""
    start = min(wellness_start, today - timedelta(days=_ACTIVITY_LOOKBACK_DAYS))
    days: list[date] = []
    current = start
    while current <= today:
        days.append(current)
        current += timedelta(days=1)
    return days


def _sync_activities(
    deps: GarminSyncDependencies,
    client: GarminDownloadClient,
    days: list[date],
) -> tuple[int, int, int]:
    """Download missing activity payloads.

    A listing failure skips that day; per-activity failures skip that
    activity; nothing aborts the sweep or the completed wellness sync.
    """
    downloaded = 0
    skipped = 0
    failed = 0
    for day in days:
        date_str = day.isoformat()
        try:
            refs = client.list_activities(day)
        except Exception:
            log.exception("  %s: activity listing failed", date_str)
            failed += 1
            continue
        for ref in refs:
            if deps.activity_files.has_activity(deps.activities_dir, day, ref.activity_id):
                skipped += 1
                continue
            try:
                payload = client.download_activity_original(ref.activity_id)
            except Exception:
                log.exception("  %s: activity %s download failed", date_str, ref.activity_id)
                failed += 1
                continue
            if payload is None:
                log.info("  %s: activity %s had no payload", date_str, ref.activity_id)
                failed += 1
                continue
            try:
                deps.activity_files.store_activity(
                    deps.activities_dir, day, ref.activity_id, ref.metadata, payload
                )
            except Exception:
                log.exception("  %s: activity %s payload unusable", date_str, ref.activity_id)
                failed += 1
                continue
            downloaded += 1
    return downloaded, skipped, failed
