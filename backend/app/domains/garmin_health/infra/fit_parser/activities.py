"""Running-activity FIT parsing: discovery, decode, and composition.

Owns the file-level workflow for ``data/garmin_activities`` running files:
find ``*_running_*.fit`` pairs, decode via the shared SDK adapter, hand the
messages to the pure extractors, and assemble ``RunningActivityData``.
Single-file parsing raises on corrupt input; garmin_sync owns the tolerant
per-file ingest loop. Reads the activities tree only; acquisition and
persistence belong to garmin_sync.
"""

import json
import logging
import re
from pathlib import Path

from app.domains.garmin_health.contracts import RunningActivityData, RunningActivitySeries
from app.domains.garmin_health.infra.fit_parser.activity_extractors import (
    _extract_run_laps,
    _extract_run_series,
    _extract_run_session,
)
from app.domains.garmin_health.infra.fit_parser.decode import decode_fit_file

log = logging.getLogger(__name__)
_GENERATED_PART_PATTERN = re.compile(r"_part\d+\.fit$")


def _stamina_scalars(series: RunningActivitySeries) -> tuple[int | None, int | None, int | None]:
    """Derive the Connect Stats-panel Stamina fields from the record series.

    Beginning/Ending Potential are the first/last non-null stamina-potential
    samples; Min Stamina is the minimum non-null stamina sample (stamina dips
    below potential during the run, matching Connect's semantics). None-safe:
    old watch firmware without stamina channels yields (None, None, None).
    """
    potential = [v for v in series.stamina_potential_pct if v is not None]
    stamina = [v for v in series.stamina_pct if v is not None]
    beginning = potential[0] if potential else None
    ending = potential[-1] if potential else None
    minimum = min(stamina) if stamina else None
    return beginning, ending, minimum


def discover_running_activity_files(activities_dir: Path) -> list[Path]:
    """Primary running FIT files across day directories, sorted by relative path.

    Garmin ZIP payloads may contain ancillary FIT members stored with the
    reserved ``_partN`` suffix. They belong to the primary activity bundle and
    must not be parsed as independent sessions.
    """
    if not activities_dir.exists():
        return []
    return sorted(
        path
        for path in activities_dir.glob("*/*_running_*.fit")
        if _GENERATED_PART_PATTERN.search(path.name) is None
    )


def _load_sidecar(fit_path: Path) -> dict | None:
    """Load optional activity JSON sidecar; return None if missing or unreadable."""
    sidecar_path = fit_path.with_suffix(".json")
    if not sidecar_path.exists():
        return None
    try:
        return json.loads(sidecar_path.read_text())
    except (OSError, json.JSONDecodeError) as e:
        log.warning("Unreadable activity sidecar %s: %s", sidecar_path, e)
        return None


def parse_running_activity(fit_path: Path, activities_dir: Path) -> RunningActivityData:
    """Parse one running FIT+sidecar pair into session + laps + series."""
    messages = decode_fit_file(fit_path)
    sidecar = _load_sidecar(fit_path)
    source_file = str(fit_path.relative_to(activities_dir))
    session = _extract_run_session(messages, sidecar, source_file)
    laps = _extract_run_laps(messages)
    series = _extract_run_series(messages)
    session.lap_count = len(laps)
    # record_count relies on the extractor's 1:1 record↔row alignment: every
    # column in series is appended once per record (positional nulls, never
    # dropped rows), so any one column's length is the true record count.
    session.record_count = len(series.elapsed_s)
    session.has_gps_trace = any(v is not None for v in series.lat)
    (
        session.stamina_beginning_potential_pct,
        session.stamina_ending_potential_pct,
        session.stamina_min_pct,
    ) = _stamina_scalars(series)
    return RunningActivityData(session=session, laps=laps, series=series)
