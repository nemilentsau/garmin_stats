"""Application retrieval flow for assistant evidence collection.

This module owns read-model interaction and evidence item assembly. Pure
payload shaping lives in ``assistant.domain`` so retrieval remains a dependency
boundary rather than the home for assistant evidence policy.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.domains.assistant.contracts import (
    AssistantEvidenceItem,
    AssistantResolvedEntity,
    AssistantRouteDecision,
)
from app.domains.assistant.dependencies import AssistantReadModelStore
from app.domains.assistant.domain import current_state, experiment_evidence, payloads
from app.domains.assistant.domain.text import dedupe_strings
from app.domains.experiments.contracts import Experiment
from app.domains.routines.contracts import RoutineAssignment, RoutineSchedule


def retrieve_experiment_review(
    *,
    store: AssistantReadModelStore,
    route: AssistantRouteDecision,
    entities: Sequence[AssistantResolvedEntity],
) -> tuple[list[AssistantEvidenceItem], list[str]]:
    """Collect deterministic evidence records for experiment-review queries."""

    experiment_entity = _select_experiment_entity(entities)
    if experiment_entity is None:
        if _is_experiment_scan_request(route):
            return _build_experiment_scan_context(store=store)
        return [], ["experiment_entity_missing"]

    experiment = store.get_experiment(experiment_entity.entity_id)
    if experiment is None:
        return [], [f"experiment_not_found:{experiment_entity.entity_id}"]

    return _build_experiment_evidence(store=store, experiment=experiment)


def retrieve_recovery_briefing(
    *,
    store: AssistantReadModelStore,
) -> tuple[list[AssistantEvidenceItem], list[str]]:
    """Collect current recovery evidence for assistant briefing queries."""

    payload, gaps = _build_recovery_context(store=store)
    if not payload:
        return [], gaps or ["recovery_context_missing"]
    return [
        AssistantEvidenceItem(
            kind="recovery_state",
            source="read_model.current_recovery_state",
            payload_json=payload,
        )
    ], gaps


def retrieve_routine_adherence(
    *,
    store: AssistantReadModelStore,
) -> tuple[list[AssistantEvidenceItem], list[str]]:
    """Collect routine adherence evidence for assistant queries."""

    payload, gaps = _build_routine_context(store=store)
    if not payload:
        return [], gaps or ["routine_context_missing"]
    return [
        AssistantEvidenceItem(
            kind="routine_state",
            source="read_model.current_routine_state",
            payload_json=payload,
        )
    ], gaps


def retrieve_open_ended_coaching(
    *,
    store: AssistantReadModelStore,
) -> tuple[list[AssistantEvidenceItem], list[str]]:
    """Collect broad current-state evidence for coaching queries."""

    recovery_payload, recovery_gaps = _build_recovery_context(store=store)
    routine_payload, routine_gaps = _build_routine_context(store=store)
    notes = payloads.ordered_notes(store.list_recent_notes(last_n=3))
    profile = store.get_profile()

    payload: dict[str, object] = {}
    if recovery_payload:
        payload["recovery"] = recovery_payload
    if routine_payload:
        payload["routine"] = routine_payload
    if notes:
        payload["recent_notes"] = [payloads.note_payload(note) for note in notes]
    if profile is not None:
        payload["profile"] = payloads.profile_payload(profile)

    gaps = dedupe_strings([*recovery_gaps, *routine_gaps])
    if not payload:
        gaps.append("current_state_missing")
        return [], dedupe_strings(gaps)

    return [
        AssistantEvidenceItem(
            kind="coaching_context",
            source="read_model.current_state",
            payload_json=payload,
        )
    ], dedupe_strings(gaps)


def _build_experiment_evidence(
    *,
    store: AssistantReadModelStore,
    experiment: Experiment,
) -> tuple[list[AssistantEvidenceItem], list[str]]:
    items: list[AssistantEvidenceItem] = [
        AssistantEvidenceItem(
            kind="experiment",
            source="read_model.experiments",
            entity_id=experiment.id,
            payload_json=experiment_evidence.experiment_payload(experiment),
        )
    ]
    gaps: list[str] = []

    analysis = store.get_experiment_analysis(experiment.id)
    if analysis is None:
        gaps.append(f"analysis_missing:{experiment.id}")
    else:
        items.append(
            AssistantEvidenceItem(
                kind="analysis",
                source="read_model.experiment_analysis",
                entity_id=experiment.id,
                payload_json=experiment_evidence.analysis_payload(analysis),
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
                payload_json=experiment_evidence.summarize_exposures(exposures),
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
                payload_json=experiment_evidence.linked_routines_payload(linked_routines),
            )
        )
    if missing_routine_ids:
        gaps.extend([f"linked_routine_missing:{routine_id}" for routine_id in missing_routine_ids])

    return items, gaps


def _build_experiment_scan_context(
    *,
    store: AssistantReadModelStore,
) -> tuple[list[AssistantEvidenceItem], list[str]]:
    active_experiments = sorted(
        store.list_experiments(statuses=("active",)),
        key=lambda experiment: (experiment.priority, experiment.id),
        reverse=True,
    )
    active_routines = payloads.ordered_routines(store.list_routines(status="active"))
    recovery_payload, recovery_gaps = _build_recovery_context(store=store)
    routine_payload, routine_gaps = _build_routine_context(
        store=store,
        active_routines=active_routines,
    )
    exposures_by_experiment_id = {
        experiment.id: store.list_experiment_exposures(experiment_id=experiment.id)
        for experiment in active_experiments
    }

    payload = experiment_evidence.experiment_scan_payload(
        active_experiment_payloads=[
            experiment_evidence.active_experiment_payload(
                experiment=experiment,
                analysis=store.get_experiment_analysis(experiment.id),
                exposures=exposures_by_experiment_id.get(experiment.id, []),
            )
            for experiment in active_experiments
        ],
        active_routines=active_routines,
        routine_payload_context=routine_payload,
        recovery_payload_context=recovery_payload,
    )

    gaps: list[str] = []
    if not active_experiments:
        gaps.append("active_experiments_missing")
    if not active_routines:
        gaps.append("active_routines_missing")
    gaps.extend(recovery_gaps)
    gaps.extend(routine_gaps)

    return [
        AssistantEvidenceItem(
            kind="scan_overview",
            source="read_model.scan_overview",
            payload_json=payload,
        )
    ], dedupe_strings(gaps)


def _is_experiment_scan_request(route: AssistantRouteDecision) -> bool:
    signals = set(route.matched_signals)
    return bool(
        signals.intersection(
            {
                "scan_keyword",
                "plural_experiment_context",
                "experiment_routine_scan",
            }
        )
    )


def _select_experiment_entity(
    entities: Sequence[AssistantResolvedEntity],
) -> AssistantResolvedEntity | None:
    experiment_entities = [entity for entity in entities if entity.kind == "experiment"]
    if not experiment_entities:
        return None
    experiment_entities.sort(key=lambda entity: (-entity.score, entity.entity_id))
    return experiment_entities[0]


def _build_recovery_context(
    *,
    store: AssistantReadModelStore,
) -> tuple[dict[str, object], list[str]]:
    return current_state.build_recovery_context(
        metrics=payloads.ordered_metrics(store.list_recent_metrics(last_n=7)),
        checkins=payloads.ordered_checkins(store.list_recent_checkins(last_n=7)),
    )


def _build_routine_context(
    store: AssistantReadModelStore,
    *,
    active_routines: Sequence[RoutineSchedule] | None = None,
) -> tuple[dict[str, object], list[str]]:
    if active_routines is None:
        active_routines = payloads.ordered_routines(store.list_routines(status="active"))
    else:
        active_routines = payloads.ordered_routines(active_routines)

    assignment_summaries, relevant_assignment_ids = current_state.routine_assignment_summaries(
        active_routines=active_routines,
        assignments_by_routine_id=_group_assignments_by_routine_id(
            store=store,
            active_routines=active_routines,
        ),
    )

    window = current_state.assignment_window(assignment_summaries)
    card_logs = []
    if window is not None:
        card_logs = [
            card_log
            for card_log in payloads.ordered_card_logs(
                store.list_card_logs_range(start_date=window[0], end_date=window[1])
            )
            if card_log.assignment_id in relevant_assignment_ids
        ]

    return current_state.build_routine_context(
        active_routines=active_routines,
        assignment_summaries=assignment_summaries,
        card_logs=card_logs,
        card_log_window=window,
    )


def _load_linked_routines(
    *,
    store: AssistantReadModelStore,
    experiment: Experiment,
) -> tuple[list[RoutineSchedule], list[str]]:
    if not experiment.linked_routine_ids:
        return [], []

    routines_by_id = {
        routine_id: routine
        for routine_id in experiment.linked_routine_ids
        if (routine := store.get_routine(routine_id)) is not None
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


def _group_assignments_by_routine_id(
    *,
    store: AssistantReadModelStore,
    active_routines: Sequence[RoutineSchedule],
) -> dict[str, list[RoutineAssignment]]:
    return {
        routine.id: payloads.ordered_assignments(
            store.list_assignments(routine_id=routine.id)
        )
        for routine in active_routines
    }
