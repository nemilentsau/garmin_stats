"""Pure experiment exposure derivation rules."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from app.domains.experiments.contracts import ExperimentExposure

_PARTIAL_ENTRY_WEIGHT = 0.5


def derive_experiment_exposure(
    *,
    experiment_id: str,
    date: str,
    routine_entry_ids: Sequence[str],
    statuses_by_routine_entry_id: Mapping[str, str],
) -> ExperimentExposure | None:
    """Derive one experiment-day exposure from linked routine entry statuses."""
    if not routine_entry_ids:
        return None

    completed = 0
    partial = 0
    skipped = 0
    pending = 0
    for entry_id in routine_entry_ids:
        status = statuses_by_routine_entry_id.get(entry_id, "pending")
        if status == "completed":
            completed += 1
        elif status == "partial":
            partial += 1
        elif status == "skipped":
            skipped += 1
        else:
            pending += 1

    total = len(routine_entry_ids)
    if pending == total:
        return None

    exposure_score = round((completed + (_PARTIAL_ENTRY_WEIGHT * partial)) / total, 3)
    if completed == total:
        adherence_state = "full"
    elif pending == 0 and completed == 0 and partial == 0 and skipped == total:
        adherence_state = "missed"
    else:
        adherence_state = "partial"

    return ExperimentExposure(
        id=ExperimentExposure.auto_id(experiment_id, date),
        experiment_id=experiment_id,
        date=date,
        exposure_score=exposure_score,
        adherence_state=adherence_state,
        linked_routine_entry_ids=list(routine_entry_ids),
    )
