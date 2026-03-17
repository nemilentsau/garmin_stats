"""
File watcher — monitors the configured Garmin data directory for new archives.
"""

import asyncio
import logging
import shutil
import zipfile
from pathlib import Path

from watchfiles import Change, awatch

from .database import compute_data_fingerprint, ingest_all
from .events import event_bus

log = logging.getLogger(__name__)

_last_fingerprint: str | None = None
_ARCHIVE_STAMP_NAME = ".archive-source"


def _zip_filter(change: Change, path: str) -> bool:
    """Only watch .zip files in the top-level data directory."""
    return path.endswith(".zip")


def _ensure_data_dir(data_dir: Path) -> None:
    """Create the watched data directory if it is missing."""
    created = not data_dir.exists()
    data_dir.mkdir(parents=True, exist_ok=True)
    if created:
        log.info("Created missing data directory at %s", data_dir)


def extract_existing_archives(data_dir: Path) -> int:
    """Extract all top-level day archives already present in data_dir."""
    _ensure_data_dir(data_dir)
    zips = sorted(path for path in data_dir.glob("*.zip") if path.is_file())
    zips_to_extract: list[Path] = []
    for zip_path in zips:
        try:
            if _archive_needs_extraction(zip_path):
                zips_to_extract.append(zip_path)
        except zipfile.BadZipFile:
            log.warning("Skipping invalid zip: %s", zip_path.name)

    if zips_to_extract:
        log.info(
            "Reconciling %d missing/stale archive(s) already present in %s",
            len(zips_to_extract),
            data_dir,
        )
    _extract_all(zips_to_extract)
    return len(zips_to_extract)


def _extract_zip(zip_path: Path) -> Path:
    """Extract a YYYY-MM-DD.zip into a sibling YYYY-MM-DD/ directory. Returns the output dir."""
    date_str = zip_path.stem  # e.g. "2026-01-15"
    out_dir = zip_path.parent / date_str
    temp_out_dir = zip_path.parent / f".{date_str}.tmp"
    if temp_out_dir.exists():
        shutil.rmtree(temp_out_dir)
    temp_out_dir.mkdir()
    with zipfile.ZipFile(zip_path, "r") as zf:
        _safe_extract_all(zf, temp_out_dir)
    _write_archive_stamp(temp_out_dir, zip_path)
    if out_dir.exists():
        shutil.rmtree(out_dir)
    temp_out_dir.rename(out_dir)
    log.info("Extracted %s → %s/", zip_path.name, date_str)
    return out_dir


def _archive_needs_extraction(zip_path: Path) -> bool:
    """Return True when a day archive is missing extracted output or looks stale."""
    out_dir = zip_path.parent / zip_path.stem
    if not out_dir.exists():
        return True

    stamp = _read_archive_stamp(out_dir)
    signature = _archive_signature(zip_path)
    if stamp is not None:
        return stamp != signature

    # Upgrade path: an extracted directory created before archive stamps existed.
    # If the extracted file tree matches the archive contents, record the stamp once
    # and skip the expensive re-extraction on every startup.
    if _matches_archive_members(zip_path, out_dir):
        _write_archive_stamp(out_dir, zip_path)
        return False

    return True


def _archive_signature(zip_path: Path) -> str:
    stat = zip_path.stat()
    return f"{stat.st_size}:{stat.st_mtime_ns}"


def _archive_stamp_path(out_dir: Path) -> Path:
    return out_dir / _ARCHIVE_STAMP_NAME


def _read_archive_stamp(out_dir: Path) -> str | None:
    stamp_path = _archive_stamp_path(out_dir)
    if not stamp_path.exists():
        return None
    return stamp_path.read_text(encoding="ascii").strip() or None


def _write_archive_stamp(out_dir: Path, zip_path: Path) -> None:
    _archive_stamp_path(out_dir).write_text(_archive_signature(zip_path), encoding="ascii")


def _matches_archive_members(zip_path: Path, out_dir: Path) -> bool:
    if not out_dir.is_dir():
        return False

    extracted_members = {
        file_path.relative_to(out_dir).as_posix(): file_path.stat().st_size
        for file_path in out_dir.rglob("*")
        if file_path.is_file() and file_path.name != _ARCHIVE_STAMP_NAME
    }
    if not extracted_members:
        return False

    with zipfile.ZipFile(zip_path, "r") as zf:
        archived_members = {
            Path(member.filename).as_posix(): member.file_size
            for member in zf.infolist()
            if not member.is_dir()
        }

    return extracted_members == archived_members


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
