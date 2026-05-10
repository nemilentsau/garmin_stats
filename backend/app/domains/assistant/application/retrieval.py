"""Deterministic retrieval helpers for assistant evidence collection."""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from datetime import date, timedelta

from app.core.profile.contracts import UserProfile
from app.domains.assistant.contracts import (
    AssistantEvidenceItem,
    AssistantResolvedEntity,
    AssistantRouteDecision,
)
from app.domains.assistant.dependencies import AssistantReadModelStore
from app.domains.experiments.contracts import (
    Experiment,
    ExperimentAnalysis,
    ExperimentExposure,
)
from app.domains.garmin_health.contracts import DailyMetric
from app.domains.journal.contracts import (
    DailyCheckIn,
    Note,
)
from app.domains.routines.contracts import CardLog, RoutineAssignment, RoutineSchedule


def retrieve_experiment_review(
    *,
    store: AssistantReadModelStore,
    route: AssistantRouteDecision,
    entities: Sequence[AssistantResolvedEntity],
) -> tuple[list[AssistantEvidenceItem], list[str]]:
    """Collect deterministic evidence records for experiment-review queries."""

    items: list[AssistantEvidenceItem] = []
    gaps: list[str] = []

    experiment_entity = _select_experiment_entity(entities)
    if experiment_entity is None:
        if _is_experiment_scan_request(route):
            return _build_experiment_scan_context(store=store)
        return [], ["experiment_entity_missing"]
    else:
        experiment = _load_experiment(store=store, experiment_id=experiment_entity.entity_id)
        if experiment is None:
            return [], [f"experiment_not_found:{experiment_entity.entity_id}"]

    items, gaps = _build_experiment_evidence(store=store, experiment=experiment)
    return items, gaps


def retrieve_recovery_briefing(
    *,
    store: AssistantReadModelStore,
) -> tuple[list[AssistantEvidenceItem], list[str]]:
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
    recovery_payload, recovery_gaps = _build_recovery_context(store=store)
    routine_payload, routine_gaps = _build_routine_context(store=store)
    notes = _ordered_notes(store.list_recent_notes(last_n=3))
    profile = store.get_profile()

    payload: dict[str, object] = {}
    if recovery_payload:
        payload["recovery"] = recovery_payload
    if routine_payload:
        payload["routine"] = routine_payload
    if notes:
        payload["recent_notes"] = [_note_payload(note) for note in notes]
    if profile is not None:
        payload["profile"] = _profile_payload(profile)

    gaps = _dedupe_strings([*recovery_gaps, *routine_gaps])
    if not payload:
        gaps.append("current_state_missing")
        return [], _dedupe_strings(gaps)

    return [
        AssistantEvidenceItem(
            kind="coaching_context",
            source="read_model.current_state",
            payload_json=payload,
        )
    ], _dedupe_strings(gaps)


def _build_experiment_evidence(
    *,
    store: AssistantReadModelStore,
    experiment: Experiment,
) -> tuple[list[AssistantEvidenceItem], list[str]]:
    items: list[AssistantEvidenceItem] = []
    gaps: list[str] = []

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
                payload_json=_analysis_payload(analysis),
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
                    "routines": [_routine_payload(routine) for routine in linked_routines],
                },
            )
        )
    if missing_routine_ids:
        gaps.extend([f"linked_routine_missing:{routine_id}" for routine_id in missing_routine_ids])

    return items, gaps


def _build_experiment_scan_context(
    *,
    store: AssistantReadModelStore,
) -> tuple[list[AssistantEvidenceItem], list[str]]:
    active_experiments = _load_active_experiments(store=store)
    active_routines = _ordered_routines(store.list_routines(status="active"))
    recovery_payload, recovery_gaps = _build_recovery_context(store=store)
    routine_payload, routine_gaps = _build_routine_context(
        store=store, active_routines=active_routines,
    )

    payload: dict[str, object] = {
        "active_experiment_count": len(active_experiments),
        "active_experiments": [
            _active_experiment_payload(store=store, experiment=experiment)
            for experiment in active_experiments
        ],
        "active_routine_count": len(active_routines),
        "active_routines": [
            _scan_routine_payload(routine=routine, routine_payload=routine_payload)
            for routine in active_routines
        ],
        "tracking_quality": _scan_tracking_quality(
            recovery_payload=recovery_payload,
            routine_payload=routine_payload,
        ),
    }

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
    ], _dedupe_strings(gaps)


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


def _load_experiment(*, store: AssistantReadModelStore, experiment_id: str) -> Experiment | None:
    for experiment in store.list_experiments():
        if experiment.id == experiment_id:
            return experiment
    return None


def _load_active_experiments(*, store: AssistantReadModelStore) -> list[Experiment]:
    active_experiments = store.list_experiments(statuses=("active",))
    return sorted(
        active_experiments,
        key=lambda experiment: (experiment.priority, experiment.id),
        reverse=True,
    )


def _analysis_payload(analysis: ExperimentAnalysis) -> dict[str, object]:
    return analysis.model_dump(mode="json")


def _active_experiment_payload(
    *,
    store: AssistantReadModelStore,
    experiment: Experiment,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "id": experiment.id,
        "name": experiment.name,
        "status": experiment.status,
        "linked_routine_ids": list(experiment.linked_routine_ids),
    }
    analysis = store.get_experiment_analysis(experiment.id)
    if analysis is not None:
        payload["analysis"] = _analysis_payload(analysis)
    exposures = store.list_experiment_exposures(experiment_id=experiment.id)
    if exposures:
        payload["exposures"] = _summarize_exposures(exposures)
    return payload


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


def _build_recovery_context(store: AssistantReadModelStore) -> tuple[dict[str, object], list[str]]:
    payload: dict[str, object] = {}
    gaps: list[str] = []

    metrics = _ordered_metrics(store.list_recent_metrics(last_n=7))
    if metrics:
        payload["recent_metrics"] = [_metric_payload(metric) for metric in metrics]
    else:
        gaps.append("recent_metrics_missing")

    checkins = _ordered_checkins(store.list_recent_checkins(last_n=7))
    if checkins:
        payload["recent_checkins"] = [_checkin_payload(checkin) for checkin in checkins]
    else:
        gaps.append("recent_checkins_missing")

    return payload, gaps


def _build_routine_context(
    store: AssistantReadModelStore,
    *,
    active_routines: Sequence[RoutineSchedule] | None = None,
) -> tuple[dict[str, object], list[str]]:
    payload: dict[str, object] = {}
    gaps: list[str] = []

    if active_routines is None:
        active_routines = _ordered_routines(store.list_routines(status="active"))
    if active_routines:
        payload["active_routines"] = [_routine_payload(routine) for routine in active_routines]
    else:
        gaps.append("active_routines_missing")

    assignment_summaries, relevant_assignment_ids = _routine_assignment_summaries(
        store=store,
        active_routines=active_routines,
    )
    if assignment_summaries:
        payload["assignment_summary"] = assignment_summaries
        window = _assignment_window(assignment_summaries)
        if window is not None:
            card_logs = _ordered_card_logs(
                store.list_card_logs_range(start_date=window[0], end_date=window[1])
            )
            card_logs = [
                card_log
                for card_log in card_logs
                if card_log.assignment_id in relevant_assignment_ids
            ]
            if card_logs:
                payload["card_log_window"] = {
                    "start_date": window[0],
                    "end_date": window[1],
                    "status_counts": _status_counts(card_logs),
                    "logged_dates": sorted({card_log.date for card_log in card_logs}),
                    "logs": [_card_log_payload(card_log) for card_log in card_logs[:5]],
                }
            else:
                gaps.append("recent_card_logs_missing")
    else:
        gaps.append("routine_assignments_missing")

    return payload, gaps


def _routine_assignment_summaries(
    *,
    store: AssistantReadModelStore,
    active_routines: Sequence[RoutineSchedule],
) -> tuple[list[dict[str, object]], set[str]]:
    summaries: list[dict[str, object]] = []
    assignment_ids: set[str] = set()
    for routine in active_routines:
        assignments = _ordered_assignments(store.list_assignments(routine_id=routine.id))
        if not assignments:
            continue
        scheduled_dates = sorted({assignment.date for assignment in assignments})
        assignment_ids.update(assignment.id for assignment in assignments)
        summaries.append(
            {
                "routine_id": routine.id,
                "routine_name": routine.name,
                "assignment_count": len(assignments),
                "scheduled_date_count": len(scheduled_dates),
                "date_range": {
                    "start_date": assignments[-1].date,
                    "end_date": assignments[0].date,
                },
                "recent_scheduled_dates": _recent_scheduled_dates(scheduled_dates),
                "slots": _slot_counts(assignments),
            }
        )
    return summaries, assignment_ids


def _assignment_window(summaries: Sequence[dict[str, object]]) -> tuple[str, str] | None:
    dates: list[date] = []
    for summary in summaries:
        date_range = summary.get("date_range")
        if not isinstance(date_range, dict):
            continue
        start_date = date_range.get("start_date")
        end_date = date_range.get("end_date")
        if isinstance(start_date, str):
            dates.append(date.fromisoformat(start_date))
        if isinstance(end_date, str):
            dates.append(date.fromisoformat(end_date))
    if not dates:
        return None
    latest = min(max(dates), date.today())
    return (latest - timedelta(days=6)).isoformat(), latest.isoformat()


def _recent_scheduled_dates(scheduled_dates: Sequence[str]) -> list[str]:
    parsed_dates = [date.fromisoformat(value) for value in scheduled_dates]
    if not parsed_dates:
        return []
    latest = min(max(parsed_dates), date.today())
    earliest = latest - timedelta(days=6)
    return [
        value
        for value in scheduled_dates
        if earliest <= date.fromisoformat(value) <= latest
    ]


def _scan_routine_payload(
    *,
    routine: RoutineSchedule,
    routine_payload: dict[str, object],
) -> dict[str, object]:
    payload = _routine_payload(routine)
    summary = _routine_summary_by_id(routine_payload, routine.id)
    if summary is not None:
        payload["assignment_count"] = summary["assignment_count"]
        payload["date_range"] = summary["date_range"]
        payload["slots"] = summary["slots"]
    return payload


def _routine_summary_by_id(
    routine_payload: dict[str, object],
    routine_id: str,
) -> dict[str, object] | None:
    assignment_summary = routine_payload.get("assignment_summary")
    if not isinstance(assignment_summary, list):
        return None
    for summary in assignment_summary:
        if not isinstance(summary, dict):
            continue
        if summary.get("routine_id") == routine_id:
            return summary
    return None


def _scan_tracking_quality(
    *,
    recovery_payload: dict[str, object],
    routine_payload: dict[str, object],
) -> dict[str, object]:
    tracking_quality: dict[str, object] = {}

    recent_metrics = recovery_payload.get("recent_metrics")
    if isinstance(recent_metrics, list):
        tracking_quality["metric_days"] = len(recent_metrics)
        if recent_metrics:
            first_metric = recent_metrics[0]
            if isinstance(first_metric, dict):
                tracking_quality["latest_metric_date"] = first_metric.get("date")

    recent_checkins = recovery_payload.get("recent_checkins")
    if isinstance(recent_checkins, list):
        tracking_quality["checkin_days"] = len(recent_checkins)
        if recent_checkins:
            first_checkin = recent_checkins[0]
            if isinstance(first_checkin, dict):
                tracking_quality["latest_checkin_date"] = first_checkin.get("date")

    card_log_window = routine_payload.get("card_log_window")
    if isinstance(card_log_window, dict):
        status_counts = card_log_window.get("status_counts")
        if isinstance(status_counts, dict):
            tracking_quality["card_log_status_counts"] = dict(status_counts)
        logged_dates = card_log_window.get("logged_dates")
        if isinstance(logged_dates, list):
            tracking_quality["card_log_days"] = len(logged_dates)

    assignment_summary = routine_payload.get("assignment_summary")
    if isinstance(assignment_summary, list):
        covered_dates: set[str] = set()
        for summary in assignment_summary:
            if not isinstance(summary, dict):
                continue
            recent_scheduled_dates = summary.get("recent_scheduled_dates")
            if isinstance(recent_scheduled_dates, list):
                covered_dates.update(
                    date_value
                    for date_value in recent_scheduled_dates
                    if isinstance(date_value, str)
                )
        tracking_quality["routine_coverage_dates"] = len(covered_dates)

    return tracking_quality


def _metric_payload(metric: DailyMetric) -> dict[str, object]:
    return {
        "date": metric.date,
        "utc_offset_hours": metric.utc_offset_hours,
        "sleep_score": metric.sleep.score,
        "hrv_nightly_avg": metric.hrv.nightly_avg,
        "hrv_weekly_avg": metric.hrv.weekly_avg,
        "hrv_status": metric.hrv.status,
        "resting_heart_rate": metric.heart_rate.resting,
        "body_battery_avg": metric.body_battery.avg,
        "respiration_avg": metric.respiration.avg,
        "spo2_avg": metric.spo2.avg,
    }


def _checkin_payload(checkin: DailyCheckIn) -> dict[str, object]:
    return {
        "date": checkin.date,
        "energy": checkin.energy,
        "mood": checkin.mood,
        "motivation": checkin.motivation,
        "soreness": checkin.soreness,
        "stress_subjective": checkin.stress_subjective,
        "sleep_quality_subjective": checkin.sleep_quality_subjective,
        "illness_flag": checkin.illness_flag,
        "travel_flag": checkin.travel_flag,
        "alcohol_flag": checkin.alcohol_flag,
    }


def _note_payload(note: Note) -> dict[str, object]:
    return {
        "date": note.date,
        "category": note.category,
        "title": note.title,
        "tags": list(note.tags),
    }


def _profile_payload(profile: UserProfile) -> dict[str, object]:
    return {
        "id": profile.id,
        "name": profile.name,
        "primary_goals": list(profile.primary_goals),
        "constraints": list(profile.constraints),
        "sleep_constraints": list(profile.sleep_constraints),
        "coaching_style_preferences": list(profile.coaching_style_preferences),
    }


def _routine_payload(routine: RoutineSchedule) -> dict[str, object]:
    return {
        "id": routine.id,
        "name": routine.name,
        "status": routine.status,
        "start_date": routine.start_date,
        "end_date": routine.end_date,
        "tags": list(routine.tags),
        "notes": routine.notes,
    }


def _ordered_metrics(metrics: Sequence[DailyMetric]) -> list[DailyMetric]:
    return sorted(
        metrics,
        key=lambda metric: (
            metric.date,
            metric.utc_offset_hours or 0.0,
            metric.body_battery.avg or 0.0,
        ),
        reverse=True,
    )


def _ordered_checkins(checkins: Sequence[DailyCheckIn]) -> list[DailyCheckIn]:
    return sorted(checkins, key=lambda checkin: (checkin.date, checkin.id), reverse=True)


def _ordered_routines(routines: Sequence[RoutineSchedule]) -> list[RoutineSchedule]:
    return sorted(routines, key=lambda routine: (routine.start_date, routine.id), reverse=True)


def _ordered_assignments(assignments: Sequence[RoutineAssignment]) -> list[RoutineAssignment]:
    return sorted(
        assignments,
        key=lambda assignment: (assignment.date, assignment.id),
        reverse=True,
    )


def _ordered_card_logs(card_logs: Sequence[CardLog]) -> list[CardLog]:
    return sorted(card_logs, key=lambda card_log: (card_log.date, card_log.id), reverse=True)


def _ordered_notes(notes: Sequence[Note]) -> list[Note]:
    return sorted(notes, key=lambda note: (note.date, note.id), reverse=True)


def _slot_counts(assignments: Sequence[RoutineAssignment]) -> dict[str, int]:
    return {
        slot: count
        for slot, count in sorted(
            Counter(assignment.slot for assignment in assignments).items(),
            key=lambda item: item[0],
        )
    }


def _status_counts(card_logs: Sequence[CardLog]) -> dict[str, int]:
    return {
        status: count
        for status, count in sorted(
            Counter(card_log.status for card_log in card_logs).items(),
            key=lambda item: item[0],
        )
    }


def _card_log_payload(card_log: CardLog) -> dict[str, object]:
    return {
        "id": card_log.id,
        "date": card_log.date,
        "assignment_id": card_log.assignment_id,
        "card_template_id": card_log.card_template_id,
        "status": card_log.status,
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


def _dedupe_strings(values: Sequence[str]) -> list[str]:
    """Return strings in first-seen order without duplicates."""
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered
