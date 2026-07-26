"""Filesystem adapters for Garmin sync archive and FIT source state."""

from __future__ import annotations

import hashlib
import logging
import shutil
import zipfile
import zlib
from datetime import date
from pathlib import Path

log = logging.getLogger(__name__)

_ARCHIVE_STAMP_NAME = ".archive-source"


def compute_data_fingerprint(data_dir: Path) -> str:
    """SHA-256 of FIT file paths, sizes, and modified times."""
    if not data_dir.exists():
        return hashlib.sha256(b"").hexdigest()

    parts: list[str] = []
    for fit_file in sorted(data_dir.rglob("*.fit")):
        try:
            stat = fit_file.stat()
        except FileNotFoundError:
            # Extraction swaps whole day directories underneath this scan, so a
            # listed file can be gone before it is stat'd. Treat it as absent;
            # the change lands in the next fingerprint. Other OSErrors (transient
            # EIO, persistent PermissionError) should not silently drop files, so
            # they are not caught here.
            continue
        rel = fit_file.relative_to(data_dir)
        parts.append(f"{rel}:{stat.st_size}:{stat.st_mtime_ns}")
    return hashlib.sha256("\n".join(parts).encode()).hexdigest()


def compute_activity_source_fingerprint(fit_file: Path, activities_dir: Path) -> str:
    """Versioned hash of one activity FIT plus optional-sidecar metadata.

    The version is part of the persisted signature so changes to parser-owned
    identity semantics can deliberately trigger one complete reingest.
    """
    parts = [str(fit_file.relative_to(activities_dir))]
    for source in (fit_file, fit_file.with_suffix(".json")):
        if source.exists():
            stat = source.stat()
            parts.append(
                f"{source.suffix}:{stat.st_size}:{stat.st_mtime_ns}"
            )
        else:
            parts.append(f"{source.suffix}:missing")
    return f"v2:{hashlib.sha256('\n'.join(parts).encode()).hexdigest()}"


def compute_activity_tree_fingerprint(
    activities_dir: Path,
    fit_files: list[Path],
) -> str:
    """Hash the discovered running FIT sources including optional JSON sidecars."""
    parts = [
        f"{fit_file.relative_to(activities_dir)}:"
        f"{compute_activity_source_fingerprint(fit_file, activities_dir)}"
        for fit_file in fit_files
    ]
    return hashlib.sha256("\n".join(parts).encode()).hexdigest()


def ensure_data_dir(data_dir: Path) -> None:
    """Create the watched data directory if it is missing."""
    created = not data_dir.exists()
    data_dir.mkdir(parents=True, exist_ok=True)
    if created:
        log.info("Created missing data directory at %s", data_dir)


def extract_existing_archives(data_dir: Path) -> list[str]:
    """Extract missing/stale top-level day archives; return the dates refreshed.

    Callers need the dates, not a count: an archive replaced outside the app is
    reconciled here but is invisible to a caller that only knows what it
    downloaded itself, and incremental ingest would skip it while still
    stamping a whole-tree fingerprint over it.
    """
    ensure_data_dir(data_dir)
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
    return [zip_path.stem for zip_path in extract_archives(zips_to_extract)]


def extract_archives(zips: list[Path]) -> list[Path]:
    """Extract multiple zip archives; return the ones that actually extracted."""
    extracted: list[Path] = []
    for zip_path in zips:
        try:
            _extract_zip(zip_path)
        except zipfile.BadZipFile:
            log.warning("Skipping invalid zip: %s", zip_path.name)
        except ValueError as exc:
            log.warning("Skipping unsafe zip %s: %s", zip_path.name, exc)
        else:
            extracted.append(zip_path)
    return extracted


def _extract_zip(zip_path: Path) -> Path:
    """Extract a YYYY-MM-DD.zip into a sibling YYYY-MM-DD directory."""
    date_str = zip_path.stem
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
    log.info("Extracted %s to %s/", zip_path.name, date_str)
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

    # Upgrade path for directories created before archive stamps existed.
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
        file_path.relative_to(out_dir).as_posix(): (
            file_path.stat().st_size,
            _file_crc32(file_path),
        )
        for file_path in out_dir.rglob("*")
        if file_path.is_file() and file_path.name != _ARCHIVE_STAMP_NAME
    }
    if not extracted_members:
        return False

    with zipfile.ZipFile(zip_path, "r") as zf:
        archived_members = {
            Path(member.filename).as_posix(): (member.file_size, member.CRC)
            for member in zf.infolist()
            if not member.is_dir()
        }

    return extracted_members == archived_members


def _file_crc32(path: Path) -> int:
    checksum = 0
    with path.open("rb") as handle:
        while chunk := handle.read(65536):
            checksum = zlib.crc32(chunk, checksum)
    return checksum & 0xFFFFFFFF


def _safe_extract_all(zf: zipfile.ZipFile, out_dir: Path) -> None:
    """Extract zip members while preventing path traversal."""
    root = out_dir.resolve()
    for member in zf.infolist():
        destination = (out_dir / member.filename).resolve()
        if destination != root and root not in destination.parents:
            raise ValueError(f"Unsafe path in archive: {member.filename}")
        zf.extract(member, out_dir)


class FilesystemSyncFileStore:
    """Read and mutate the local YYYY-MM-DD.zip / YYYY-MM-DD archive layout."""

    def latest_zip_date(self, data_dir: Path) -> date | None:
        zips: list[str] = []
        if not data_dir.exists():
            return None
        for path in data_dir.iterdir():
            if path.suffix != ".zip" or len(path.stem) != 10:
                continue
            try:
                date.fromisoformat(path.stem)
            except ValueError:
                continue
            zips.append(path.stem)
        if not zips:
            return None
        return date.fromisoformat(max(zips))

    def zip_exists(self, data_dir: Path, day: date) -> bool:
        return (data_dir / f"{day.isoformat()}.zip").exists()

    def install_archive(self, data_dir: Path, day: date, data: bytes) -> None:
        """Stage and extract a replacement before mutating the current day."""
        ensure_data_dir(data_dir)
        date_str = day.isoformat()
        zip_path = data_dir / f"{date_str}.zip"
        out_dir = data_dir / date_str
        temp_zip = data_dir / f".{date_str}.zip.tmp"
        temp_out = data_dir / f".{date_str}.install.tmp"
        backup_out = data_dir / f".{date_str}.backup.tmp"

        if backup_out.exists():
            if out_dir.exists():
                shutil.rmtree(backup_out)
            else:
                backup_out.rename(out_dir)
        if temp_zip.exists():
            temp_zip.unlink()
        if temp_out.exists():
            shutil.rmtree(temp_out)

        try:
            temp_zip.write_bytes(data)
            temp_out.mkdir()
            with zipfile.ZipFile(temp_zip, "r") as zf:
                _safe_extract_all(zf, temp_out)
            _write_archive_stamp(temp_out, temp_zip)

            temp_zip.replace(zip_path)
            if out_dir.exists():
                out_dir.rename(backup_out)
            try:
                temp_out.rename(out_dir)
            except Exception:
                if backup_out.exists() and not out_dir.exists():
                    backup_out.rename(out_dir)
                raise
            if backup_out.exists():
                shutil.rmtree(backup_out)
        finally:
            if temp_zip.exists():
                temp_zip.unlink()
            if temp_out.exists():
                shutil.rmtree(temp_out)
