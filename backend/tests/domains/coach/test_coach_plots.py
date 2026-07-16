"""Cache, channel-selection, and rendering tests for coach run plots."""

from __future__ import annotations

import os
from math import isnan
from pathlib import Path

from app.domains.coach.infra.paths import library_panel_path
from app.domains.coach.infra.plots import (
    PANEL_SPEC_VERSION,
    available_current_channels,
    break_elapsed_gaps,
    render_current_run_stack,
    render_library_panel,
    run_content_fingerprint,
)
from app.domains.garmin_analytics.contracts import (
    RunDetailResponse,
    RunDisplayStats,
    RunSeriesResponse,
    RunZoneDisplayRow,
)
from app.domains.garmin_analytics.domain.run_heart_rate import heart_rate_evidence
from app.domains.garmin_health.contracts import (
    RunningActivityLap,
    RunningActivitySeries,
    RunningActivitySession,
    RunWalkSpan,
)


def _detail(*, with_lap: bool = False) -> RunDetailResponse:
    return RunDetailResponse(
        session=RunningActivitySession(
            id="run-1",
            source_file="run-1.fit",
            session_date="2026-07-11",
            start_time_local="2026-07-11T06:00:00",
            activity_name="Morning Run",
        ),
        laps=[RunningActivityLap(lap_index=1, start_s=60)] if with_lap else [],
        display=RunDisplayStats(
            distance_mi=1.0,
            pace_min_per_mi=8.0,
            heart_rate_zones=[
                RunZoneDisplayRow(
                    zone=1,
                    label="Z1 · 100–119 bpm",
                    lower_bound=100,
                    upper_bound=119,
                ),
                RunZoneDisplayRow(
                    zone=2,
                    label="Z2 · 120–139 bpm",
                    lower_bound=120,
                    upper_bound=139,
                ),
                RunZoneDisplayRow(
                    zone=3,
                    label="Z3 · ≥140 bpm",
                    lower_bound=140,
                ),
            ],
        ),
    )


def _series(*, with_spans: bool = False) -> RunSeriesResponse:
    embedded = RunningActivitySeries(
        elapsed_s=[0, 30, 60, 90],
        speed_mps=[3.0, 3.1, None, 2.9],
        heart_rate_bpm=[130, 136, None, 142],
        cadence_spm=[170, 172, None, 168],
        altitude_m=[100, 102, None, 104],
        power_w=[220, 230, None, 210],
        run_walk_spans=(
            [
                RunWalkSpan(span_type="run", start_s=0, end_s=60),
                RunWalkSpan(span_type="walk", start_s=60, end_s=90),
            ]
            if with_spans
            else []
        ),
    )
    response = RunSeriesResponse(
        series=embedded,
        pace_min_per_mi=[8.94, 8.65, None, 9.25],
        altitude_ft=[328, 335, None, 341],
    )
    return response.model_copy(
        update={
            "heart_rate_evidence": heart_rate_evidence(
                embedded.heart_rate_bpm, _detail().display.heart_rate_zones
            )
        }
    )


def _assert_png(path: Path) -> None:
    assert path.is_file()
    assert path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")


def test_missing_panel_renders_file(tmp_path):
    path = render_library_panel(tmp_path, _detail(), _series())

    _assert_png(path)
    assert path.name.startswith("run-1-")


def test_same_content_second_call_is_noop_with_unchanged_mtime(tmp_path):
    detail = _detail()
    series = _series()
    path = render_library_panel(tmp_path, detail, series)
    os.utime(path, ns=(1_000_000_000, 1_000_000_000))
    before = path.stat().st_mtime_ns

    same_path = render_library_panel(tmp_path, detail, series)

    assert same_path == path
    assert same_path.stat().st_mtime_ns == before


def test_changed_series_fingerprint_renders_new_panel(tmp_path):
    detail = _detail()
    first = _series()
    changed = first.model_copy(update={"pace_min_per_mi": [8.5, 8.4, None, 8.6]})

    first_path = render_library_panel(tmp_path, detail, first)
    changed_path = render_library_panel(tmp_path, detail, changed)

    assert run_content_fingerprint(detail, first) != run_content_fingerprint(detail, changed)
    assert changed_path != first_path
    _assert_png(changed_path)


def test_panel_spec_change_changes_path(tmp_path):
    fingerprint = "abc123"

    first = library_panel_path(tmp_path, "run-1", fingerprint, spec_version=PANEL_SPEC_VERSION)
    next_version = library_panel_path(
        tmp_path, "run-1", fingerprint, spec_version=PANEL_SPEC_VERSION + 1
    )

    assert first != next_version


def test_empty_series_produces_explicit_no_series_panel(tmp_path):
    series = RunSeriesResponse(series=RunningActivitySeries())

    path = render_library_panel(tmp_path, _detail(), series)

    _assert_png(path)


def test_current_stack_starts_with_intensity_composite_then_supplemental_channels(tmp_path):
    series = _series()

    channels = available_current_channels(series)
    pages = render_current_run_stack(tmp_path, _detail(), series)

    assert channels == ["Pace", "Heart rate", "Cadence", "Elevation", "Power"]
    assert len(pages) == 2
    assert "intensity" in pages[0].name
    assert "p01" in pages[1].name
    for page in pages:
        _assert_png(page)


def test_library_panel_with_hr_evidence_renders_composite(tmp_path):
    path = render_library_panel(tmp_path, _detail(), _series())

    _assert_png(path)


def test_walk_shading_and_lap_markers_accept_empty_or_present_inputs(tmp_path):
    plain = render_library_panel(tmp_path / "plain", _detail(), _series())
    annotated = render_library_panel(
        tmp_path / "annotated", _detail(with_lap=True), _series(with_spans=True)
    )

    _assert_png(plain)
    _assert_png(annotated)


def test_elapsed_time_gap_inserts_nan_break_before_next_observation():
    x, y = break_elapsed_gaps([0, 1, 10], [8.0, 8.1, 9.0], max_gap_s=3)

    assert x == [0.0, 1.0, 2.0, 10.0]
    assert y[:2] == [8.0, 8.1]
    assert isnan(y[2])
    assert y[3] == 9.0
