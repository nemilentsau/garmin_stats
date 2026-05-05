"""Derive experiment-day exposures from routine card logs."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping

from app.domains.routines.application.schedule_window import get_schedule_window
from app.infra.database import (
    delete_experiment_analysis,
    load_experiment_exposures,
    load_experiments,
    replace_experiment_exposure_for_date,
    save_experiment_analysis,
)
from app.models import CardLog, Experiment, ExperimentExposure, ScheduleOccurrence

from .analysis import compute_experiment_analysis

_PARTIAL_CARD_WEIGHT = 0.5
_SYNCABLE_EXPERIMENT_STATUSES = ("active", "draft", "completed")


class ExperimentExposureSyncService:
    def sync_for_date(self, *, date: str) -> None:
        sync_experiment_exposures_for_date(date)


def _refresh_persisted_analysis_if_changed(
    experiment: Experiment,
    *,
    old_exposure: ExperimentExposure | None,
    new_exposure: ExperimentExposure | None,
) -> None:
    changed = (old_exposure is None) != (new_exposure is None)
    if not changed and old_exposure is not None and new_exposure is not None:
        changed = (
            old_exposure.exposure_score != new_exposure.exposure_score
            or old_exposure.adherence_state != new_exposure.adherence_state
        )
    if not changed:
        return
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
    from app.bootstrap.container import build_container

    repo = build_container().routines_repo
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
        log.occurrence_key: log for log in repo.list_card_logs(date=date)
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
        old_exposures = load_experiment_exposures(experiment_id=experiment.id, date=date)
        old_exposure = old_exposures[0] if old_exposures else None
        new_exposure = _derive_experiment_exposure(
            experiment,
            date=date,
            occurrences=relevant_occurrences,
            logs_by_occurrence_key=logs_by_occurrence_key,
        )
        replace_experiment_exposure_for_date(experiment.id, date, new_exposure)
        _refresh_persisted_analysis_if_changed(
            experiment, old_exposure=old_exposure, new_exposure=new_exposure,
        )
