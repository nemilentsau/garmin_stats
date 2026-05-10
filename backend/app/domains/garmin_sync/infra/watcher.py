"""Garmin sync data-directory watcher."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from pathlib import Path

from watchfiles import Change, awatch

from app.domains.garmin_sync.infra.filesystem import (
    compute_data_fingerprint,
    ensure_data_dir,
    extract_archives,
)
from app.domains.garmin_sync.infra.sqlite_ingest import ingest_all
from app.infra.events import event_bus

log = logging.getLogger(__name__)

_last_fingerprint: str | None = None
_suspended = False
RefreshAfterIngest = Callable[[], int]


def suspend_watcher() -> None:
    """Temporarily suspend the file watcher during bulk sync operations."""
    global _suspended
    _suspended = True
    log.info("File watcher suspended")


def resume_watcher() -> None:
    """Resume the file watcher after suspension."""
    global _suspended
    _suspended = False
    log.info("File watcher resumed")


def _zip_filter(change: Change, path: str) -> bool:
    """Only watch .zip files in the top-level data directory."""
    return path.endswith(".zip")


async def watch_data_directory(
    data_dir: Path,
    *,
    refresh_after_ingest: RefreshAfterIngest | None = None,
) -> None:
    """Watch data_dir for archives, extract them, ingest, and broadcast updates."""
    global _last_fingerprint
    ensure_data_dir(data_dir)
    _last_fingerprint = compute_data_fingerprint(data_dir)

    log.info("File watcher started on %s", data_dir)
    async for changes in awatch(data_dir, watch_filter=_zip_filter, debounce=3000):
        if _suspended:
            log.debug("Watcher suspended; skipping %d change(s)", len(changes))
            continue
        new_zips = [
            Path(path)
            for change, path in changes
            if change in (Change.added, Change.modified) and path.endswith(".zip")
        ]
        if not new_zips:
            continue

        log.info("Detected %d new/modified .zip archive(s)", len(new_zips))
        await asyncio.to_thread(extract_archives, new_zips)

        fingerprint = compute_data_fingerprint(data_dir)
        if fingerprint == _last_fingerprint:
            log.debug("Fingerprint unchanged after extraction; skipping ingest")
            continue

        try:
            result = await asyncio.to_thread(ingest_all, data_dir)
            _last_fingerprint = fingerprint
            log.info(
                "Auto-ingest complete: %d days in %d ms",
                result.days_ingested,
                result.duration_ms,
            )
            if refresh_after_ingest is not None:
                try:
                    refreshed = await asyncio.to_thread(refresh_after_ingest)
                    if refreshed:
                        log.info("Post-ingest refresh completed for %d item(s)", refreshed)
                except Exception:
                    log.exception("Post-ingest refresh failed")

            await event_bus.broadcast("data_updated", "new_data")
        except RuntimeError:
            log.info("Ingest already in progress; skipping")
