"""Garmin sync data-directory watcher runtime."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable, Collection
from pathlib import Path

from watchfiles import Change, awatch

from app.domains.garmin_sync.dependencies import IngestGateway

log = logging.getLogger(__name__)

ArchiveBatchExtractor = Callable[[list[Path]], None]
Broadcast = Callable[[str, str], Awaitable[None]]
ChangeBatch = Collection[tuple[Change, str]]
EnsureDataDir = Callable[[Path], None]
Fingerprint = Callable[[Path], str]
RefreshAfterIngest = Callable[[], int]


def _zip_filter(change: Change, path: str) -> bool:
    return path.endswith(".zip")


class DataDirectoryWatcher:
    """Stateful watcher for one Garmin data directory."""

    def __init__(
        self,
        *,
        data_dir: Path,
        ensure_data_dir: EnsureDataDir,
        fingerprint: Fingerprint,
        extract_archives: ArchiveBatchExtractor,
        ingest: IngestGateway,
        broadcast: Broadcast,
    ) -> None:
        self._data_dir = data_dir
        self._ensure_data_dir = ensure_data_dir
        self._fingerprint = fingerprint
        self._extract_archives = extract_archives
        self._ingest = ingest
        self._broadcast = broadcast
        self._last_fingerprint: str | None = None
        self._suspended = False

    def prime(self) -> None:
        self._ensure_data_dir(self._data_dir)
        self._last_fingerprint = self._fingerprint(self._data_dir)

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
        # Caller must have called prime() or watch() first to seed _last_fingerprint.
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

        fingerprint = self._fingerprint(self._data_dir)
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
