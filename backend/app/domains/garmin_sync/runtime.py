"""Runtime entrypoints for Garmin sync startup reconciliation."""

from __future__ import annotations

import logging
from pathlib import Path

from app.domains.garmin_sync.filesystem import extract_existing_archives
from app.domains.garmin_sync.sqlite_ingest import check_ingest_status, ingest_all

log = logging.getLogger(__name__)


def run_startup_ingest_if_needed(data_dir: Path) -> None:
    """Reconcile existing day archives and ingest when disk state changed."""
    extract_existing_archives(data_dir)
    status = check_ingest_status(data_dir)
    if not status.needs_ingest:
        log.info(
            "Startup data already in sync: %d days in DB, %d days on disk",
            status.days_in_db,
            status.days_on_disk,
        )
        return

    reason = "DB empty" if status.days_in_db == 0 else "Data directory changed"
    log.info("%s; running startup ingest", reason)
    result = ingest_all(data_dir)
    log.info(
        "Startup ingest complete: %d days in %d ms",
        result.days_ingested,
        result.duration_ms,
    )
