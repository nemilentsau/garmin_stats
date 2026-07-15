"""Adapter: training's `RunActivityReadPort` backed by the garmin_analytics runs repo.

Lives in bootstrap because `training` must not import garmin code
(`garmin_analytics`/`garmin_health` — see `training/CHARTER.md`) and
`garmin_analytics` must not know training vocabulary — the container
composes the two at the boundary instead. `training/dependencies.py` defines
the `RunActivityReadPort` Protocol and training-local run contracts it
returns; this module is the only place that constructs them from real Garmin
data, converting to the project's imperial display units (CLAUDE.md) via the
shared `app.utils.units` helpers — the same ones
`garmin_analytics/application/runs.py` uses — so a run's `distance_mi`/
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
from app.utils.units import m_to_mi, m_to_mi_exact, min_per_km_to_min_per_mi


def _summary(session: RunningActivitySession) -> TrainingRunActivitySummary:
    return TrainingRunActivitySummary(
        run_id=session.id,
        session_date=session.session_date,
        start_time_local=session.start_time_local,
        distance_mi=m_to_mi(session.distance_m),
        timer_time_s=session.timer_time_s,
        pace_min_per_mi=min_per_km_to_min_per_mi(session.pace_min_per_km),
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
            distance_mi=[m_to_mi_exact(value) for value in series.distance_m],
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
