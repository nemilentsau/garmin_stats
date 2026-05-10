"""Small serializers and ordering helpers for assistant evidence payloads.

These helpers convert cross-domain contracts into stable JSON-ready fragments
for assistant evidence. They own representation policy only; callers remain
responsible for loading records and deciding which records belong in a bundle.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.core.profile.contracts import UserProfile
from app.domains.garmin_health.contracts import DailyMetric
from app.domains.journal.contracts import DailyCheckIn, Note
from app.domains.routines.contracts import CardLog, RoutineAssignment, RoutineSchedule


def metric_payload(metric: DailyMetric) -> dict[str, object]:
    """Return the compact metric fields useful for assistant grounding."""

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


def checkin_payload(checkin: DailyCheckIn) -> dict[str, object]:
    """Return subjective check-in fields used by recovery and coaching context."""

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


def note_payload(note: Note) -> dict[str, object]:
    """Return note fields that are safe to include in assistant context."""

    return {
        "date": note.date,
        "category": note.category,
        "title": note.title,
        "tags": list(note.tags),
    }


def profile_payload(profile: UserProfile) -> dict[str, object]:
    """Return profile preferences used for coaching context."""

    return {
        "id": profile.id,
        "name": profile.name,
        "primary_goals": list(profile.primary_goals),
        "constraints": list(profile.constraints),
        "sleep_constraints": list(profile.sleep_constraints),
        "coaching_style_preferences": list(profile.coaching_style_preferences),
    }


def routine_payload(routine: RoutineSchedule) -> dict[str, object]:
    """Return the schedule-level routine fields used in evidence payloads."""

    return {
        "id": routine.id,
        "name": routine.name,
        "status": routine.status,
        "start_date": routine.start_date,
        "end_date": routine.end_date,
        "tags": list(routine.tags),
        "notes": routine.notes,
    }


def card_log_payload(card_log: CardLog) -> dict[str, object]:
    """Return compact card-log fields for recent adherence evidence."""

    return {
        "id": card_log.id,
        "date": card_log.date,
        "assignment_id": card_log.assignment_id,
        "card_template_id": card_log.card_template_id,
        "status": card_log.status,
    }


def ordered_metrics(metrics: Sequence[DailyMetric]) -> list[DailyMetric]:
    return sorted(
        metrics,
        key=lambda metric: (
            metric.date,
            metric.utc_offset_hours or 0.0,
            metric.body_battery.avg or 0.0,
        ),
        reverse=True,
    )


def ordered_checkins(checkins: Sequence[DailyCheckIn]) -> list[DailyCheckIn]:
    return sorted(checkins, key=lambda checkin: (checkin.date, checkin.id), reverse=True)


def ordered_routines(routines: Sequence[RoutineSchedule]) -> list[RoutineSchedule]:
    return sorted(routines, key=lambda routine: (routine.start_date, routine.id), reverse=True)


def ordered_assignments(assignments: Sequence[RoutineAssignment]) -> list[RoutineAssignment]:
    return sorted(
        assignments,
        key=lambda assignment: (assignment.date, assignment.id),
        reverse=True,
    )


def ordered_card_logs(card_logs: Sequence[CardLog]) -> list[CardLog]:
    return sorted(card_logs, key=lambda card_log: (card_log.date, card_log.id), reverse=True)


def ordered_notes(notes: Sequence[Note]) -> list[Note]:
    return sorted(notes, key=lambda note: (note.date, note.id), reverse=True)
