"""Adapter: training's `RunActivityReadPort` backed by the garmin_analytics runs repo.

Lives in bootstrap because `training` must not import garmin code
(`garmin_analytics`/`garmin_health` — see `training/CHARTER.md`) and
`garmin_analytics` must not know training vocabulary — the container
composes the two at the boundary instead. `training/dependencies.py` defines
the `RunActivityReadPort` Protocol and training-local run contracts it
returns; this module is the only place that constructs them from real Garmin
data, converting to the project's imperial display units
(CLAUDE.md) with the exact same constants and rounding
`garmin_analytics/application/runs.py` uses, so a run's `distance_mi`/
`pace_min_per_mi` here always matches what `/api/activities/runs` shows for
the same run.
"""

from __future__ import annotations

from app.domains.garmin_analytics.application.dependencies import RunsReadRepository
from app.domains.garmin_health.contracts import RunningActivitySession
from app.domains.training.contracts import (
    TrainingRunActivitySummary,
    TrainingRunEvidence,
    TrainingRunWalkSpan,
)

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


def _m_to_mi_exact(value_m: float | None) -> float | None:
    """Meters -> miles without display rounding. None-preserving."""
    return None if value_m is None else value_m / _M_PER_MI


def _minkm_to_minmi(value_min_per_km: float | None) -> float | None:
    """min/km -> min/mi, 2dp. None-preserving."""
    return None if value_min_per_km is None else round(value_min_per_km * _KM_TO_MI, 2)


def _summary(session: RunningActivitySession) -> TrainingRunActivitySummary:
    return TrainingRunActivitySummary(
        run_id=session.id,
        session_date=session.session_date,
        start_time_local=session.start_time_local,
        distance_mi=_m_to_mi(session.distance_m),
        timer_time_s=session.timer_time_s,
        pace_min_per_mi=_minkm_to_minmi(session.pace_min_per_km),
        avg_heart_rate_bpm=session.avg_heart_rate_bpm,
        hr_source=session.hr_source,
        training_load=session.training_load,
        aerobic_training_effect=session.aerobic_training_effect,
    )


class GarminRunActivityPort:
    """`RunActivityReadPort` implementation backed by `RunsReadRepository`.

    `runs_between` filters the same all-sessions read used by the Garmin runs
    list, once per inclusive window. `evidence_for_run` combines the keyed
    session and record-series reads while preserving index-aligned nulls.
    """

    def __init__(self, runs_repo: RunsReadRepository) -> None:
        self._runs_repo = runs_repo

    def runs_between(
        self, start_date: str, end_date: str
    ) -> list[TrainingRunActivitySummary]:
        return [
            _summary(session)
            for session in self._runs_repo.load_sessions()
            if start_date <= session.session_date <= end_date
        ]

    def evidence_for_run(self, run_id: str) -> TrainingRunEvidence:
        session = self._runs_repo.load_session(run_id)
        series = self._runs_repo.load_series(run_id)
        if session is None or series is None:
            raise LookupError(f"Run {run_id} not found")
        return TrainingRunEvidence(
            summary=_summary(session),
            elapsed_s=series.elapsed_s,
            distance_mi=[_m_to_mi_exact(value) for value in series.distance_m],
            heart_rate_bpm=series.heart_rate_bpm,
            run_walk_spans=[
                TrainingRunWalkSpan(
                    span_type=span.span_type,
                    start_s=span.start_s,
                    end_s=span.end_s,
                )
                for span in series.run_walk_spans
            ],
        )
