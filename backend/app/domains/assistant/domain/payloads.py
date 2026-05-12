"""Small serializers and ordering helpers for assistant evidence payloads.

These helpers convert cross-domain contracts into stable JSON-ready fragments
for assistant evidence. They own representation policy only; callers remain
responsible for loading records and deciding which records belong in a bundle.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from app.core.profile.contracts import UserProfile
from app.domains.garmin_health.contracts import DailyMetric
from app.domains.journal.contracts import DailyCheckIn, Note
from app.domains.routines.contracts import CardLog, RoutineAssignment, RoutineSchedule


class _DateIdRecord(Protocol):
    date: str
    id: str


def metric_payload(metric: DailyMetric) -> dict[str, object]:
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
    return {
        "date": note.date,
        "category": note.category,
        "title": note.title,
        "tags": list(note.tags),
    }


def profile_payload(profile: UserProfile) -> dict[str, object]:
    return {
        "id": profile.id,
        "name": profile.name,
        "primary_goals": list(profile.primary_goals),
        "constraints": list(profile.constraints),
        "sleep_constraints": list(profile.sleep_constraints),
        "coaching_style_preferences": list(profile.coaching_style_preferences),
    }


def routine_payload(routine: RoutineSchedule) -> dict[str, object]:
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
    return ordered_by_date(checkins)


def ordered_routines(routines: Sequence[RoutineSchedule]) -> list[RoutineSchedule]:
    return sorted(routines, key=lambda routine: (routine.start_date, routine.id), reverse=True)


def ordered_assignments(assignments: Sequence[RoutineAssignment]) -> list[RoutineAssignment]:
    return ordered_by_date(assignments)


def ordered_card_logs(card_logs: Sequence[CardLog]) -> list[CardLog]:
    return ordered_by_date(card_logs)


def ordered_notes(notes: Sequence[Note]) -> list[Note]:
    return ordered_by_date(notes)


def ordered_by_date[DateIdT: _DateIdRecord](
    records: Sequence[DateIdT],
) -> list[DateIdT]:
    return sorted(records, key=lambda record: (record.date, record.id), reverse=True)
