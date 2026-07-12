"""Tests for `GarminRunActivityPort` — training's `RunActivityReadPort` adapter.

Lives in `tests/bootstrap/` (not `tests/domains/training/`) because the
adapter itself lives in `backend/app/bootstrap/`, outside any domain slice —
see `training/CHARTER.md`'s "Must not import" note on why this composition
is not training's own code.
"""

from __future__ import annotations

from app.bootstrap.run_activity_port import GarminRunActivityPort
from app.domains.garmin_analytics.adapters import SqliteRunsRepository
from tests._runs_helpers import insert_run


def _port() -> GarminRunActivityPort:
    return GarminRunActivityPort(SqliteRunsRepository())


def test_runs_for_date_converts_distance_and_pace_to_imperial_display_units():
    insert_run("2026-07-06", "r1")

    summaries = _port().runs_for_date("2026-07-06")

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


def test_runs_for_date_defaults_link_source_to_auto():
    insert_run("2026-07-06", "r1")

    assert _port().runs_for_date("2026-07-06")[0].link_source == "auto"


def test_runs_for_date_filters_out_sessions_on_other_dates():
    insert_run("2026-07-06", "r1")
    insert_run("2026-07-07", "r2")

    assert [s.run_id for s in _port().runs_for_date("2026-07-06")] == ["r1"]


def test_runs_for_date_returns_empty_list_when_no_session_exists():
    insert_run("2026-07-06", "r1")

    assert _port().runs_for_date("2026-07-10") == []
