"""Tests for `GarminRunActivityPort` — training's `RunActivityReadPort` adapter.

Lives in `tests/bootstrap/` (not `tests/domains/training/`) because the
adapter itself lives in `backend/app/bootstrap/`, outside any domain slice —
see `training/CHARTER.md`'s "Must not import" note on why this composition
is not training's own code.
"""

from __future__ import annotations

import pytest

from app.bootstrap.run_activity_port import GarminRunActivityPort
from app.domains.garmin_analytics.adapters import SqliteRunsRepository
from app.domains.garmin_health.contracts import RunningActivitySeries, RunWalkSpan
from app.infra.sqlite import connect
from tests._runs_helpers import insert_run


def _port() -> GarminRunActivityPort:
    return GarminRunActivityPort(SqliteRunsRepository())


def _replace_series(run_id: str, series: RunningActivitySeries) -> None:
    with connect() as con:
        con.execute(
            "UPDATE running_activity_series SET data = ? WHERE session_id = ?",
            (series.model_dump_json(), run_id),
        )
        con.commit()


def test_runs_between_keeps_inclusive_boundaries_and_excludes_outside_dates():
    insert_run("2026-07-05", "before")
    insert_run("2026-07-06", "start")
    insert_run("2026-07-08", "end")
    insert_run("2026-07-09", "after")

    summaries = _port().runs_between("2026-07-06", "2026-07-08")

    assert [(summary.run_id, summary.session_date) for summary in summaries] == [
        ("start", "2026-07-06"),
        ("end", "2026-07-08"),
    ]


def test_runs_between_preserves_imperial_summary_rounding():
    insert_run("2026-07-06", "r1")

    summaries = _port().runs_between("2026-07-06", "2026-07-06")

    assert len(summaries) == 1
    summary = summaries[0]
    assert summary.run_id == "r1"
    assert summary.start_time_local == "2026-07-06T10:57:26"
    assert summary.distance_mi == round(9695.29 / 1609.344, 2)
    assert summary.timer_time_s == 3050.674
    assert summary.pace_min_per_mi == round(5.24 * 1.609344, 2)
    assert summary.avg_heart_rate_bpm == 139
    assert summary.hr_source == "strap"
    assert summary.training_load is None
    assert summary.aerobic_training_effect is None


def test_runs_between_defaults_link_source_to_auto():
    insert_run("2026-07-06", "r1")

    assert _port().runs_between("2026-07-06", "2026-07-06")[0].link_source == "auto"


def test_runs_between_returns_empty_list_when_no_session_exists_in_range():
    insert_run("2026-07-06", "r1")

    assert _port().runs_between("2026-07-10", "2026-07-12") == []


def test_evidence_for_run_preserves_samples_and_maps_run_walk_spans():
    insert_run("2026-07-06", "r1")
    _replace_series(
        "r1",
        RunningActivitySeries(
            elapsed_s=[0, 1, 2],
            distance_m=[0.0, 100.0, None],
            heart_rate_bpm=[140, None, 142],
            run_walk_spans=[
                RunWalkSpan(span_type="run", start_s=0.0, end_s=1.5),
                RunWalkSpan(span_type="walk", start_s=1.5, end_s=2.0),
            ],
        ),
    )

    evidence = _port().evidence_for_run("r1")

    assert evidence.summary.run_id == "r1"
    assert evidence.summary.session_date == "2026-07-06"
    assert evidence.elapsed_s == [0, 1, 2]
    assert evidence.distance_mi == [0.0, 100.0 / 1609.344, None]
    assert evidence.heart_rate_bpm == [140, None, 142]
    assert [span.model_dump() for span in evidence.run_walk_spans] == [
        {"span_type": "run", "start_s": 0.0, "end_s": 1.5},
        {"span_type": "walk", "start_s": 1.5, "end_s": 2.0},
    ]
    assert evidence.dew_point_c is None


def test_evidence_for_run_raises_for_unknown_run_id():
    with pytest.raises(LookupError, match="missing"):
        _port().evidence_for_run("missing")
