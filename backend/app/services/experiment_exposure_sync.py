"""Derive experiment-day exposures from routine card logs."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping

from app.domains.routines.application.schedule_window import get_schedule_window
from app.domains.routines.infra.sqlite_repository import SqliteRoutineRepository
from app.infra.database import (
    delete_experiment_analysis,
    load_card_logs,
    load_experiments,
    replace_experiment_exposure_for_date,
    save_experiment_analysis,
)
from app.models import CardLog, Experiment, ExperimentExposure, ScheduleOccurrence
from app.services.experiment_analysis import compute_experiment_analysis

_PARTIAL_CARD_WEIGHT = 0.5
_SYNCABLE_EXPERIMENT_STATUSES = ("active", "draft")


class ExperimentExposureSyncService:
    def sync_for_date(self, *, date: str) -> None:
        sync_experiment_exposures_for_date(date)


def _refresh_persisted_analysis(experiment: Experiment) -> None:
    if experiment.design is None:
        delete_experiment_analysis(experiment.id)
        return
    analysis = compute_experiment_analysis(experiment)
    save_experiment_analysis(experiment.id, analysis)


def _derive_experiment_exposure(
    experiment: Experiment,
    *,
    date: str,
    occurrences: list[ScheduleOccurrence],
    logs_by_occurrence_key: Mapping[str, CardLog],
) -> ExperimentExposure | None:
    if not occurrences:
        return None

    completed = 0
    partial = 0
    skipped = 0
    pending = 0
    for occurrence in occurrences:
        log = logs_by_occurrence_key.get(occurrence.occurrence_key)
        status = log.status if log is not None else "pending"
        if status == "completed":
            completed += 1
        elif status == "partial":
            partial += 1
        elif status == "skipped":
            skipped += 1
        else:
            pending += 1

    total = len(occurrences)
    if pending == total:
        return None

    exposure_score = round((completed + (_PARTIAL_CARD_WEIGHT * partial)) / total, 3)
    if completed == total:
        adherence_state = "full"
    elif pending == 0 and completed == 0 and partial == 0 and skipped == total:
        adherence_state = "missed"
    else:
        adherence_state = "partial"

    return ExperimentExposure(
        id=f"exposure:auto:{experiment.id}:{date}",
        experiment_id=experiment.id,
        date=date,
        exposure_score=exposure_score,
        adherence_state=adherence_state,
        linked_routine_entry_ids=[occurrence.occurrence_key for occurrence in occurrences],
    )


def sync_experiment_exposures_for_date(date: str) -> None:
    """Recompute derived experiment exposures for one date from current card logs."""
    repo = SqliteRoutineRepository()
    window = get_schedule_window(repo, start_date=date, duration_days=1)
    occurrences = window.days[0].occurrences if window.days else []
    routine_ids_on_date = {
        occurrence.routine_id
        for occurrence in occurrences
        if occurrence.routine_id is not None
    }
    if not routine_ids_on_date:
        return

    occurrences_by_routine: dict[str, list[ScheduleOccurrence]] = defaultdict(list)
    for occurrence in occurrences:
        if occurrence.routine_id is None:
            continue
        occurrences_by_routine[occurrence.routine_id].append(occurrence)

    logs_by_occurrence_key = {
        log.occurrence_key: log for log in load_card_logs(date)
    }
    experiments = [
        experiment
        for experiment in load_experiments(statuses=_SYNCABLE_EXPERIMENT_STATUSES)
        if routine_ids_on_date.intersection(experiment.linked_routine_ids)
    ]
    for experiment in experiments:
        relevant_occurrences: list[ScheduleOccurrence] = []
        for routine_id in experiment.linked_routine_ids:
            relevant_occurrences.extend(occurrences_by_routine.get(routine_id, []))
        exposure = _derive_experiment_exposure(
            experiment,
            date=date,
            occurrences=relevant_occurrences,
            logs_by_occurrence_key=logs_by_occurrence_key,
        )
        replace_experiment_exposure_for_date(experiment.id, date, exposure)
        _refresh_persisted_analysis(experiment)
