"""Build assistant experiment evidence payloads.

Experiment evidence policy lives here because it is deterministic and does not
need repository access. The application layer loads analyses, exposures, and
linked routines, then this module shapes them into stable assistant context.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence

from app.domains.assistant.domain.payloads import routine_payload as base_routine_payload
from app.domains.experiments.contracts import (
    Experiment,
    ExperimentAnalysis,
    ExperimentExposure,
)
from app.domains.routines.contracts import RoutineSchedule


def experiment_payload(experiment: Experiment) -> dict[str, object]:
    """Return the canonical experiment payload for assistant evidence."""

    return {
        "id": experiment.id,
        "name": experiment.name,
        "status": experiment.status,
        "linked_routine_ids": list(experiment.linked_routine_ids),
    }


def analysis_payload(analysis: ExperimentAnalysis) -> dict[str, object]:
    """Return the JSON representation of an experiment analysis contract."""

    return analysis.model_dump(mode="json")


def active_experiment_payload(
    *,
    experiment: Experiment,
    analysis: ExperimentAnalysis | None,
    exposures: Sequence[ExperimentExposure],
) -> dict[str, object]:
    """Return scan payload for one active experiment."""

    payload = experiment_payload(experiment)
    if analysis is not None:
        payload["analysis"] = analysis_payload(analysis)
    if exposures:
        payload["exposures"] = summarize_exposures(exposures)
    return payload


def linked_routines_payload(routines: Sequence[RoutineSchedule]) -> dict[str, object]:
    """Return the linked routine payload for an experiment."""

    return {
        "count": len(routines),
        "routines": [base_routine_payload(routine) for routine in routines],
    }


def summarize_exposures(exposures: Sequence[ExperimentExposure]) -> dict[str, object]:
    """Summarize experiment exposures without collapsing daily adherence states."""

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


def experiment_scan_payload(
    *,
    active_experiment_payloads: Sequence[dict[str, object]],
    active_routines: Sequence[RoutineSchedule],
    routine_payload_context: dict[str, object],
    recovery_payload_context: dict[str, object],
) -> dict[str, object]:
    """Return the overview payload used for broad experiment scan requests."""

    return {
        "active_experiment_count": len(active_experiment_payloads),
        "active_experiments": list(active_experiment_payloads),
        "active_routine_count": len(active_routines),
        "active_routines": [
            scan_routine_payload(routine=routine, routine_payload=routine_payload_context)
            for routine in active_routines
        ],
        "tracking_quality": scan_tracking_quality(
            recovery_payload=recovery_payload_context,
            routine_payload=routine_payload_context,
        ),
    }


def scan_routine_payload(
    *,
    routine: RoutineSchedule,
    routine_payload: dict[str, object],
) -> dict[str, object]:
    """Return routine scan payload enriched with assignment summary data."""

    payload = base_routine_payload(routine)
    summary = routine_summary_by_id(routine_payload, routine.id)
    if summary is not None:
        payload["assignment_count"] = summary["assignment_count"]
        payload["date_range"] = summary["date_range"]
        payload["slots"] = summary["slots"]
    return payload


def routine_summary_by_id(
    routine_payload: dict[str, object],
    routine_id: str,
) -> dict[str, object] | None:
    """Return one routine assignment summary from a routine context payload."""

    assignment_summary = routine_payload.get("assignment_summary")
    if not isinstance(assignment_summary, list):
        return None
    for summary in assignment_summary:
        if not isinstance(summary, dict):
            continue
        if summary.get("routine_id") == routine_id:
            return summary
    return None


def scan_tracking_quality(
    *,
    recovery_payload: dict[str, object],
    routine_payload: dict[str, object],
) -> dict[str, object]:
    """Summarize whether evidence coverage is strong enough for scan answers."""

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
            recent_dates = summary.get("recent_scheduled_dates")
            if isinstance(recent_dates, list):
                covered_dates.update(
                    date_value for date_value in recent_dates if isinstance(date_value, str)
                )
        tracking_quality["routine_coverage_dates"] = len(covered_dates)

    return tracking_quality
