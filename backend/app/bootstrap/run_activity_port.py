"""Adapter: training's `RunActivityReadPort` backed by the garmin_analytics runs repo.

Lives in bootstrap because `training` must not import garmin code
(`garmin_analytics`/`garmin_health` — see `training/CHARTER.md`) and
`garmin_analytics` must not know training vocabulary — the container
composes the two at the boundary instead. `training/dependencies.py` defines
the `RunActivityReadPort` Protocol and the `TrainingRunActivitySummary`
contract it returns; this module is the only place that constructs one from
real Garmin data, converting to the project's imperial display units
(CLAUDE.md) with the exact same constants and rounding
`garmin_analytics/application/runs.py` uses, so a run's `distance_mi`/
`pace_min_per_mi` here always matches what `/api/activities/runs` shows for
the same run.
"""

from __future__ import annotations

from app.domains.garmin_analytics.application.dependencies import RunsReadRepository
from app.domains.training.contracts import TrainingRunActivitySummary

# Imperial conversion constants — identical to
# `garmin_analytics/application/runs.py` (kept in sync deliberately; this
# adapter converts the same source fields, not a value already converted by
# garmin_analytics, so it needs its own copy rather than importing that
# module's private helpers across the slice boundary).
_M_PER_MI = 1609.344
_KM_TO_MI = 1.609344


def _m_to_mi(value_m: float | None) -> float | None:
    """Meters -> miles, 2dp. None-preserving."""
    return None if value_m is None else round(value_m / _M_PER_MI, 2)


def _minkm_to_minmi(value_min_per_km: float | None) -> float | None:
    """min/km -> min/mi, 2dp. None-preserving."""
    return None if value_min_per_km is None else round(value_min_per_km * _KM_TO_MI, 2)


class GarminRunActivityPort:
    """`RunActivityReadPort` implementation backed by `RunsReadRepository`.

    `runs_for_date` filters `load_sessions()` (the same all-sessions read
    `garmin_analytics.application.runs.list_runs` uses) down to one calendar
    date and projects each matching session into a `TrainingRunActivitySummary`
    — `link_source` always starts `"auto"` here; `training`'s matching policy
    (`match_run_to_card`) is the one place that ever overrides it to
    `"manual"`, on a copy, for a manually-linked run.
    """

    def __init__(self, runs_repo: RunsReadRepository) -> None:
        self._runs_repo = runs_repo

    def runs_for_date(self, date: str) -> list[TrainingRunActivitySummary]:
        return [
            TrainingRunActivitySummary(
                run_id=session.id,
                start_time_local=session.start_time_local,
                distance_mi=_m_to_mi(session.distance_m),
                timer_time_s=session.timer_time_s,
                pace_min_per_mi=_minkm_to_minmi(session.pace_min_per_km),
                avg_heart_rate_bpm=session.avg_heart_rate_bpm,
                hr_source=session.hr_source,
                training_load=session.training_load,
                aerobic_training_effect=session.aerobic_training_effect,
            )
            for session in self._runs_repo.load_sessions()
            if session.session_date == date
        ]
