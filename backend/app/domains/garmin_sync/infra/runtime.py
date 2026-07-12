"""Runtime entrypoints for Garmin sync startup reconciliation."""

from __future__ import annotations

import logging

from app.domains.garmin_sync.dependencies import GarminSyncDependencies

log = logging.getLogger(__name__)


def run_startup_ingest_if_needed(deps: GarminSyncDependencies) -> None:
    """Reconcile wellness archives, then run running-activity ingest.

    The wellness block below is short-circuited when the disk fingerprint
    already matches the database. The running-activity ingest call is
    unconditional: it always runs after the wellness block, on both branches,
    because the engine is itself fingerprint-gated and is a cheap no-op when
    the activities tree is unchanged.
    """
    data_dir = deps.data_dir
    deps.extract_archives(data_dir)
    status = deps.ingest.check_status(data_dir)
    if not status.needs_ingest:
        log.info(
            "Startup data already in sync: %d days in DB, %d days on disk",
            status.days_in_db,
            status.days_on_disk,
        )
    else:
        reason = "DB empty" if status.days_in_db == 0 else "Data directory changed"
        log.info("%s; running startup ingest", reason)
        result = deps.ingest.ingest_all(data_dir)
        log.info(
            "Startup ingest complete: %d days in %d ms",
            result.days_ingested,
            result.duration_ms,
        )

    deps.ingest.ingest_running_activities(deps.activities_dir)
