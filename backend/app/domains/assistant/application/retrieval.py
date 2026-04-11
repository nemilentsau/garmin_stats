"""Deterministic retrieval helpers for assistant evidence collection."""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence

from app.domains.assistant.application.ports import AssistantReadModelStore
from app.domains.assistant.application.types import AssistantEvidenceItem, AssistantResolvedEntity
from app.models import Experiment, ExperimentExposure, RoutineSchedule


def retrieve_experiment_review(
    *,
    store: AssistantReadModelStore,
    entities: Sequence[AssistantResolvedEntity],
) -> tuple[list[AssistantEvidenceItem], list[str]]:
    """Collect deterministic evidence records for experiment-review queries."""

    items: list[AssistantEvidenceItem] = []
    gaps: list[str] = []

    experiment_entity = _select_experiment_entity(entities)
    if experiment_entity is None:
        return [], ["experiment_entity_missing"]

    experiment = _load_experiment(store=store, experiment_id=experiment_entity.entity_id)
    if experiment is None:
        return [], [f"experiment_not_found:{experiment_entity.entity_id}"]

    items.append(
        AssistantEvidenceItem(
            kind="experiment",
            source="read_model.experiments",
            entity_id=experiment.id,
            payload_json={
                "id": experiment.id,
                "name": experiment.name,
                "status": experiment.status,
                "linked_routine_ids": list(experiment.linked_routine_ids),
            },
        )
    )

    analysis = store.get_experiment_analysis(experiment.id)
    if analysis is None:
        gaps.append(f"analysis_missing:{experiment.id}")
    else:
        items.append(
            AssistantEvidenceItem(
                kind="analysis",
                source="read_model.experiment_analysis",
                entity_id=experiment.id,
                payload_json={
                    "analysis_date": analysis.analysis_date,
                    "phase": analysis.phase,
                    "adherence_rate": analysis.adherence_rate,
                    "overall_confidence": analysis.overall_confidence,
                    "summary": analysis.summary,
                },
            )
        )

    exposures = store.list_experiment_exposures(experiment_id=experiment.id)
    if not exposures:
        gaps.append(f"exposures_missing:{experiment.id}")
    else:
        items.append(
            AssistantEvidenceItem(
                kind="exposures",
                source="read_model.experiment_exposures",
                entity_id=experiment.id,
                payload_json=_summarize_exposures(exposures),
            )
        )

    linked_routines, missing_routine_ids = _load_linked_routines(store=store, experiment=experiment)
    if linked_routines:
        primary_routine = linked_routines[0]
        items.append(
            AssistantEvidenceItem(
                kind="linked_routine",
                source="read_model.routines",
                entity_id=primary_routine.id,
                payload_json={
                    "count": len(linked_routines),
                    "routines": [
                        {
                            "id": routine.id,
                            "name": routine.name,
                            "status": routine.status,
                            "start_date": routine.start_date,
                            "end_date": routine.end_date,
                        }
                        for routine in linked_routines
                    ],
                },
            )
        )
    if missing_routine_ids:
        gaps.extend([f"linked_routine_missing:{routine_id}" for routine_id in missing_routine_ids])

    return items, gaps


def _select_experiment_entity(
    entities: Sequence[AssistantResolvedEntity],
) -> AssistantResolvedEntity | None:
    experiment_entities = [entity for entity in entities if entity.kind == "experiment"]
    if not experiment_entities:
        return None
    experiment_entities.sort(key=lambda entity: (-entity.score, entity.entity_id))
    return experiment_entities[0]


def _load_experiment(*, store: AssistantReadModelStore, experiment_id: str) -> Experiment | None:
    for experiment in store.list_experiments():
        if experiment.id == experiment_id:
            return experiment
    return None


def _summarize_exposures(exposures: Sequence[ExperimentExposure]) -> dict[str, object]:
    ordered_exposures = sorted(exposures, key=lambda exposure: (exposure.date, exposure.id))
    adherence_counts = Counter(exposure.adherence_state for exposure in ordered_exposures)
    return {
        "count": len(ordered_exposures),
        "first_date": ordered_exposures[0].date,
        "last_date": ordered_exposures[-1].date,
        "adherence_counts": {
            state: adherence_counts[state] for state in sorted(adherence_counts)
        },
    }


def _load_linked_routines(
    *,
    store: AssistantReadModelStore,
    experiment: Experiment,
) -> tuple[list[RoutineSchedule], list[str]]:
    if not experiment.linked_routine_ids:
        return [], []

    routines_by_id = {
        routine.id: routine
        for routine in store.list_routines()
    }
    linked = [
        routines_by_id[routine_id]
        for routine_id in experiment.linked_routine_ids
        if routine_id in routines_by_id
    ]
    missing = sorted(
        {
            routine_id
            for routine_id in experiment.linked_routine_ids
            if routine_id not in routines_by_id
        }
    )
    return sorted(linked, key=lambda routine: routine.id), missing
