"""Build assistant current-state evidence payloads.

This module owns deterministic recovery and routine context policy: which
recent fields are exposed, how assignment windows are summarized, and how gaps
are reported. It accepts records that the application layer already loaded.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import date, timedelta

from app.domains.assistant.domain.payloads import (
    card_log_payload,
    checkin_payload,
    metric_payload,
    routine_payload,
)
from app.domains.garmin_health.contracts import DailyMetric
from app.domains.journal.contracts import DailyCheckIn
from app.domains.routines.contracts import CardLog, RoutineAssignment, RoutineSchedule


def build_recovery_context(
    *,
    metrics: Sequence[DailyMetric],
    checkins: Sequence[DailyCheckIn],
) -> tuple[dict[str, object], list[str]]:
    """Return recovery context and missing-data gaps from loaded records."""

    payload: dict[str, object] = {}
    gaps: list[str] = []

    if metrics:
        payload["recent_metrics"] = [metric_payload(metric) for metric in metrics]
    else:
        gaps.append("recent_metrics_missing")

    if checkins:
        payload["recent_checkins"] = [checkin_payload(checkin) for checkin in checkins]
    else:
        gaps.append("recent_checkins_missing")

    return payload, gaps


def build_routine_context(
    *,
    active_routines: Sequence[RoutineSchedule],
    assignment_summaries: Sequence[dict[str, object]],
    card_logs: Sequence[CardLog],
    card_log_window: tuple[str, str] | None,
) -> tuple[dict[str, object], list[str]]:
    """Return routine adherence context and missing-data gaps."""

    payload: dict[str, object] = {}
    gaps: list[str] = []

    if active_routines:
        payload["active_routines"] = [
            routine_payload(routine) for routine in active_routines
        ]
    else:
        gaps.append("active_routines_missing")

    if assignment_summaries:
        payload["assignment_summary"] = list(assignment_summaries)
        if card_log_window is not None:
            if card_logs:
                payload["card_log_window"] = {
                    "start_date": card_log_window[0],
                    "end_date": card_log_window[1],
                    "status_counts": status_counts(card_logs),
                    "logged_dates": sorted({card_log.date for card_log in card_logs}),
                    "logs": [card_log_payload(card_log) for card_log in card_logs[:5]],
                }
            else:
                gaps.append("recent_card_logs_missing")
    else:
        gaps.append("routine_assignments_missing")

    return payload, gaps


def routine_assignment_summaries(
    *,
    active_routines: Sequence[RoutineSchedule],
    assignments_by_routine_id: Mapping[str, Sequence[RoutineAssignment]],
) -> tuple[list[dict[str, object]], set[str]]:
    """Summarize active routine assignments and return relevant assignment IDs."""

    summaries: list[dict[str, object]] = []
    assignment_ids: set[str] = set()
    for routine in active_routines:
        assignments = list(assignments_by_routine_id.get(routine.id, ()))
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
                "recent_scheduled_dates": recent_scheduled_dates(scheduled_dates),
                "slots": slot_counts(assignments),
            }
        )
    return summaries, assignment_ids


def assignment_window(summaries: Sequence[dict[str, object]]) -> tuple[str, str] | None:
    """Return the seven-day card-log window implied by assignment summaries."""

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


def recent_scheduled_dates(scheduled_dates: Sequence[str]) -> list[str]:
    """Return scheduled dates from the most recent seven-day window."""

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


def slot_counts(assignments: Sequence[RoutineAssignment]) -> dict[str, int]:
    return {
        slot: count
        for slot, count in sorted(
            Counter(assignment.slot for assignment in assignments).items(),
            key=lambda item: item[0],
        )
    }


def status_counts(card_logs: Sequence[CardLog]) -> dict[str, int]:
    return {
        status: count
        for status, count in sorted(
            Counter(card_log.status for card_log in card_logs).items(),
            key=lambda item: item[0],
        )
    }
