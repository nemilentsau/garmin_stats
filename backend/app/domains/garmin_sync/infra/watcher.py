"""Garmin sync data-directory watcher runtime.

The watcher owns process-local state for one data directory: whether file events
are suspended and which FIT-file fingerprint has already been ingested. Workflow
code controls it through explicit callbacks so resume and successful ingest stay
separate states.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable, Collection
from pathlib import Path

from watchfiles import Change, awatch

from app.domains.garmin_sync.dependencies import IngestGateway
from app.domains.garmin_sync.infra.filesystem import compute_data_fingerprint

log = logging.getLogger(__name__)

# The extractor reports which archives it managed to extract; the watcher
# re-fingerprints the tree instead, so it ignores the return value.
ArchiveBatchExtractor = Callable[[list[Path]], object]
Broadcast = Callable[[str, str], Awaitable[None]]
ChangeBatch = Collection[tuple[Change, str]]
EnsureDataDir = Callable[[Path], None]
RefreshAfterIngest = Callable[[], int]


def _zip_filter(change: Change, path: str) -> bool:
    return path.endswith(".zip")


class DataDirectoryWatcher:
    """Extract changed archives, ingest fresh FIT data, and broadcast updates."""

    def __init__(
        self,
        *,
        data_dir: Path,
        ensure_data_dir: EnsureDataDir,
        extract_archives: ArchiveBatchExtractor,
        ingest: IngestGateway,
        broadcast: Broadcast,
    ) -> None:
        self._data_dir = data_dir
        self._ensure_data_dir = ensure_data_dir
        self._extract_archives = extract_archives
        self._ingest = ingest
        self._broadcast = broadcast
        self._last_fingerprint: str | None = None
        self._suspended = False

    def prime(self) -> None:
        self._ensure_data_dir(self._data_dir)
        self._last_fingerprint = compute_data_fingerprint(self._data_dir)

    def mark_synced(self) -> None:
        """Record the current disk fingerprint after an external successful ingest."""
        self.prime()

    def suspend(self) -> None:
        self._suspended = True
        log.info("File watcher suspended")

    def resume(self) -> None:
        self._suspended = False
        log.info("File watcher resumed")

    async def watch(
        self,
        *,
        refresh_after_ingest: RefreshAfterIngest | None = None,
    ) -> None:
        self.prime()
        log.info("File watcher started on %s", self._data_dir)
        async for changes in awatch(self._data_dir, watch_filter=_zip_filter, debounce=3000):
            await self.handle_changes(
                changes,
                refresh_after_ingest=refresh_after_ingest,
            )

    async def handle_changes(
        self,
        changes: ChangeBatch,
        *,
        refresh_after_ingest: RefreshAfterIngest | None = None,
    ) -> None:
        # prime() seeds the fingerprint before watch-loop events are processed.
        if self._suspended:
            log.debug("Watcher suspended; skipping %d change(s)", len(changes))
            return

        new_zips = [
            Path(path)
            for change, path in changes
            if change in (Change.added, Change.modified) and path.endswith(".zip")
        ]
        if not new_zips:
            return

        log.info("Detected %d new/modified .zip archive(s)", len(new_zips))
        await asyncio.to_thread(self._extract_archives, new_zips)

        fingerprint = compute_data_fingerprint(self._data_dir)
        if fingerprint == self._last_fingerprint:
            log.debug("Fingerprint unchanged after extraction; skipping ingest")
            return

        try:
            result = await asyncio.to_thread(self._ingest.ingest_all, self._data_dir)
            self._last_fingerprint = fingerprint
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

            await self._broadcast("data_updated", "new_data")
        except RuntimeError:
            log.info("Ingest already in progress; skipping")
