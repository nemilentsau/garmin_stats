"""Filesystem layout for downloaded Garmin activity FIT files.

Owns the ``data/garmin_activities/YYYY-MM-DD`` tree: extracting Garmin's
original activity payloads (bare FIT or ZIP of FITs), deriving readable
filename stems from local start time plus decoded FIT sport/sub_sport,
writing JSON metadata sidecars, and answering activity-id idempotence
lookups from those sidecars. Consumed by sync workflows through the
``ActivityFileStore`` port and by ``scripts/download_garmin.py`` backfills.
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime
from io import BytesIO
from pathlib import Path
from typing import Any
from zipfile import BadZipFile, ZipFile

from garmin_fit_sdk import Decoder, Stream

_SAFE_FILENAME_PATTERN = re.compile(r"[^a-z0-9_-]+")


def existing_activity_stem(day_dir: Path, activity_id: str) -> str | None:
    """Find an already-downloaded activity's file stem by Garmin activity id."""
    if not day_dir.exists():
        return None
    for metadata_path in sorted(day_dir.glob("*.json")):
        if _metadata_matches_activity(metadata_path, activity_id):
            return metadata_path.stem
    return None


def store_activity_payload(
    day_dir: Path,
    activity_id: str,
    metadata: dict[str, Any],
    payload: bytes,
) -> list[Path]:
    """Extract one activity payload into ``day_dir`` and write its sidecar.

    Raises ``ValueError`` when the payload is not a usable FIT/ZIP-of-FITs or
    the first FIT cannot be decoded for naming; extracted files are removed on
    failure so a bad payload leaves no partial state behind.
    """
    day_dir.mkdir(parents=True, exist_ok=True)
    download_stem = f"download-{activity_id}"
    extracted = _extract_activity_payload(payload, download_stem, day_dir)
    try:
        final_stem = _activity_file_stem_from_fit(day_dir, activity_id, metadata, extracted)
    except ValueError:
        for path in extracted:
            path.unlink(missing_ok=True)
        raise
    extracted = _rename_activity_outputs(day_dir, download_stem, final_stem, extracted)
    metadata_path = day_dir / f"{final_stem}.json"
    metadata_path.write_text(
        json.dumps(metadata, indent=2, sort_keys=True, default=str),
        encoding="utf-8",
    )
    return extracted


def remove_activity_outputs(day_dir: Path, file_stem: str) -> None:
    """Delete the FIT files and sidecar for one stored activity stem."""
    for path in day_dir.glob(f"{file_stem}*.fit"):
        path.unlink(missing_ok=True)
    (day_dir / f"{file_stem}.json").unlink(missing_ok=True)


class FilesystemActivityStore:
    """ActivityFileStore adapter over the garmin_activities day-directory tree."""

    def has_activity(self, activities_dir: Path, day: date, activity_id: str) -> bool:
        """Return whether this activity id already has a sidecar under the day directory."""
        return existing_activity_stem(activities_dir / day.isoformat(), activity_id) is not None

    def store_activity(
        self,
        activities_dir: Path,
        day: date,
        activity_id: str,
        metadata: dict[str, Any],
        payload: bytes,
    ) -> None:
        """Extract and persist one activity payload under the day directory."""
        store_activity_payload(activities_dir / day.isoformat(), activity_id, metadata, payload)


def _activity_file_stem_from_fit(
    day_dir: Path,
    activity_id: str,
    metadata: dict[str, Any],
    fit_paths: list[Path],
) -> str:
    """Build a readable, stable stem from decoded FIT session data.

    On a stem collision with a different activity's sidecar, the Garmin
    activity id is appended so two same-second activities never overwrite
    each other.
    """
    base_stem = _activity_base_stem(metadata, _activity_kind_from_fit(fit_paths[0]))
    metadata_path = day_dir / f"{base_stem}.json"
    if not metadata_path.exists() or _metadata_matches_activity(metadata_path, activity_id):
        return base_stem
    return f"{base_stem}_{activity_id}"


def _activity_base_stem(metadata: dict[str, Any], activity_kind: str) -> str:
    started_at = _activity_start_time(metadata)
    time_part = started_at.strftime("%H%M%S") if started_at else "unknown-time"
    return f"{time_part}_{_safe_filename_part(activity_kind)}"


def _activity_kind_from_fit(fit_path: Path) -> str:
    messages, errors = Decoder(Stream.from_file(str(fit_path))).read()
    if errors:
        raise ValueError(f"{fit_path.name} decoded with errors: {errors}")

    session = (messages.get("session_mesgs") or [{}])[0]
    sport = _safe_filename_part(str(session.get("sport") or "activity"))
    sub_sport = _safe_filename_part(str(session.get("sub_sport") or "generic"))
    return f"{sport}_{sub_sport}"


def _activity_start_time(metadata: dict[str, Any]) -> datetime | None:
    for key in ("startTimeLocal", "startTimeGMT"):
        raw = metadata.get(key)
        if not raw:
            continue
        try:
            return datetime.strptime(str(raw), "%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
    return None


def _safe_filename_part(value: str) -> str:
    safe = _SAFE_FILENAME_PATTERN.sub("-", value.strip().lower()).strip("-_")
    return safe or "activity"


def _metadata_matches_activity(metadata_path: Path, activity_id: str) -> bool:
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return str(metadata.get("activityId")) == activity_id


def _rename_activity_outputs(
    day_dir: Path,
    source_stem: str,
    target_stem: str,
    fit_paths: list[Path],
) -> list[Path]:
    if source_stem == target_stem:
        return fit_paths

    renamed: list[Path] = []
    for index, fit_path in enumerate(fit_paths):
        suffix = "" if index == 0 else f"_part{index + 1}"
        target_path = day_dir / f"{target_stem}{suffix}.fit"
        fit_path.replace(target_path)
        renamed.append(target_path)
    return renamed


def _extract_activity_payload(payload: bytes, file_stem: str, day_dir: Path) -> list[Path]:
    """Extract Garmin's original activity payload into activity FIT files."""
    if not payload.startswith(b"PK"):
        fit_path = day_dir / f"{file_stem}.fit"
        fit_path.write_bytes(payload)
        return [fit_path]

    try:
        with ZipFile(BytesIO(payload)) as archive:
            fit_members = [
                member for member in archive.namelist() if member.lower().endswith(".fit")
            ]
            if not fit_members:
                raise ValueError("activity ZIP contained no FIT files")

            extracted: list[Path] = []
            for index, member in enumerate(fit_members):
                suffix = "" if index == 0 else f"_part{index + 1}"
                target_path = day_dir / f"{file_stem}{suffix}.fit"
                target_path.write_bytes(archive.read(member))
                extracted.append(target_path)
            return extracted
    except BadZipFile as e:
        raise ValueError("activity payload was not a valid ZIP") from e
