"""
File watcher — monitors data/ for new .zip archives, extracts them, and triggers auto-ingest.
"""

import asyncio
import logging
import zipfile
from pathlib import Path

from watchfiles import Change, awatch

from .database import compute_data_fingerprint, ingest_all
from .events import event_bus

log = logging.getLogger(__name__)

_last_fingerprint: str | None = None


def _zip_filter(change: Change, path: str) -> bool:
    """Only watch .zip files in the top-level data directory."""
    return path.endswith(".zip")


def _ensure_data_dir(data_dir: Path) -> None:
    """Create the watched data directory if it is missing."""
    if data_dir.exists():
        return
    data_dir.mkdir(parents=True, exist_ok=True)
    log.info("Created missing data directory at %s", data_dir)


def extract_existing_archives(data_dir: Path) -> int:
    """Extract all top-level day archives already present in data_dir."""
    _ensure_data_dir(data_dir)
    zips = sorted(path for path in data_dir.glob("*.zip") if path.is_file())
    if zips:
        log.info("Reconciling %d archive(s) already present in %s", len(zips), data_dir)
    _extract_all(zips)
    return len(zips)


def _extract_zip(zip_path: Path) -> Path:
    """Extract a YYYY-MM-DD.zip into a data/YYYY-MM-DD/ directory. Returns the output dir."""
    date_str = zip_path.stem  # e.g. "2026-01-15"
    out_dir = zip_path.parent / date_str
    out_dir.mkdir(exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as zf:
        _safe_extract_all(zf, out_dir)
    log.info("Extracted %s → %s/", zip_path.name, date_str)
    return out_dir


def _safe_extract_all(zf: zipfile.ZipFile, out_dir: Path) -> None:
    """Extract zip members while preventing path traversal (zip-slip)."""
    root = out_dir.resolve()
    for member in zf.infolist():
        destination = (out_dir / member.filename).resolve()
        if destination != root and root not in destination.parents:
            raise ValueError(f"Unsafe path in archive: {member.filename}")
        zf.extract(member, out_dir)


async def watch_data_directory(data_dir: Path) -> None:
    """Watch data_dir for .zip archives, extract them, ingest, and broadcast updates."""
    global _last_fingerprint
    _ensure_data_dir(data_dir)
    _last_fingerprint = compute_data_fingerprint(data_dir)

    log.info("File watcher started on %s", data_dir)
    async for changes in awatch(data_dir, watch_filter=_zip_filter, debounce=3000):
        new_zips = [
            Path(path)
            for change, path in changes
            if change in (Change.added, Change.modified) and path.endswith(".zip")
        ]
        if not new_zips:
            continue

        log.info("Detected %d new/modified .zip archive(s)", len(new_zips))

        # Extract all new zips
        await asyncio.to_thread(_extract_all, new_zips)

        fingerprint = compute_data_fingerprint(data_dir)
        if fingerprint == _last_fingerprint:
            log.debug("Fingerprint unchanged after extraction — skipping ingest")
            continue

        try:
            result = await asyncio.to_thread(ingest_all, data_dir)
            _last_fingerprint = fingerprint
            log.info(
                "Auto-ingest complete: %d days in %d ms",
                result.days_ingested,
                result.duration_ms,
            )
            await event_bus.broadcast("data_updated", "new_data")
        except RuntimeError:
            log.info("Ingest already in progress — skipping")


def _extract_all(zips: list[Path]) -> None:
    """Extract multiple zip archives (runs in thread)."""
    for zip_path in zips:
        try:
            _extract_zip(zip_path)
        except zipfile.BadZipFile:
            log.warning("Skipping invalid zip: %s", zip_path.name)
        except ValueError as exc:
            log.warning("Skipping unsafe zip %s: %s", zip_path.name, exc)


async def heartbeat_loop() -> None:
    """Send periodic heartbeat to keep SSE connections alive through proxies."""
    while True:
        await asyncio.sleep(30)
        await event_bus.broadcast("heartbeat", "")
