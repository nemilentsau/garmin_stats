"""Pure schedule-domain helpers.

Helpers here define routine-date matching, occurrence keys, payload merging, and
slot ordering. They stay free of repository, FastAPI, and artifact concerns.
"""

from __future__ import annotations

import logging
from datetime import date as date_cls

from pydantic import TypeAdapter, ValidationError

from app.domains.routines.contracts import (
    CardOverride,
    CardPayload,
    CardTemplate,
    RoutineAssignment,
    RoutineSchedule,
    ScheduleOccurrence,
)

log = logging.getLogger(__name__)

_PAYLOAD_ADAPTER: TypeAdapter[CardPayload] = TypeAdapter(CardPayload)

SLOT_ORDER = ("morning", "midday", "evening", "anytime")
_SLOT_INDEX = {slot: index for index, slot in enumerate(SLOT_ORDER)}


def parse_schedule_date(date_str: str) -> date_cls:
    """Parse an ISO calendar date used by routine schedules."""
    return date_cls.fromisoformat(date_str)


def scheduled_occurrence_key(assignment_id: str, date: str) -> str:
    """Build the stable occurrence key for a scheduled assignment on a date."""
    return f"scheduled:{assignment_id}:{date}"


def override_occurrence_key(override: CardOverride, date: str) -> str:
    """Build the stable occurrence key for an override-created occurrence."""
    return f"override:{override.action}:{override.id}:{date}"


def merge_schedule_payload(
    card: CardTemplate,
    assignment: RoutineAssignment | None,
) -> CardPayload:
    """Merge card payload defaults with assignment-level prescription overrides.

    Robustness guarantees (per the bundle spec's override rules):
    - ``card_type`` is always stripped from the override dict so no override can
      silently swap the payload discriminator to a different type.
    - Override keys are salvaged individually: keys the payload type rejects
      (unknown fields or invalid values) are dropped with a warning while the
      remaining valid keys still apply.  One bad key must not silently revert a
      prescribed dose to the card default, and must never 500 the schedule.
    """
    if assignment is None or not assignment.prescription_override_json:
        return card.payload_json

    # Strip card_type so overrides can never swap the discriminator.
    override = {
        k: v
        for k, v in assignment.prescription_override_json.items()
        if k != "card_type"
    }
    if not override:
        return card.payload_json

    merged = dict(card.payload_json)
    merged.update(override)
    try:
        return _PAYLOAD_ADAPTER.validate_python(merged)
    except ValidationError as exc:
        rejected = {
            part for err in exc.errors() for part in err["loc"] if part in override
        }
        log.warning(
            "Dropping invalid prescription override keys %s for card %s "
            "(assignment %s)",
            sorted(rejected) if rejected else sorted(override),
            card.id,
            assignment.id,
        )
        salvaged = {k: v for k, v in override.items() if k not in rejected}
        if not salvaged or salvaged == override:
            return card.payload_json

    merged = dict(card.payload_json)
    merged.update(salvaged)
    try:
        return _PAYLOAD_ADAPTER.validate_python(merged)
    except ValidationError:
        log.warning(
            "Prescription override for card %s (assignment %s) still invalid "
            "after salvage; using the base payload",
            card.id,
            assignment.id,
        )
        return card.payload_json


def routine_is_active_on_date(routine: RoutineSchedule, day: date_cls) -> bool:
    """Return whether a compiled routine contributes assignments on ``day``."""
    start_date = parse_schedule_date(routine.start_date)
    if day < start_date:
        return False
    if routine.end_date is not None and day > parse_schedule_date(routine.end_date):
        return False
    return routine.status == "active"


def assignment_matches_date(assignment: RoutineAssignment, day: date_cls) -> bool:
    """Return whether a dated assignment belongs to ``day``."""
    return assignment.date == day.isoformat()


def occurrence_sort_key(occurrence: ScheduleOccurrence) -> tuple[int, int, str]:
    """Sort occurrences by slot order, position, then display name."""
    return (_SLOT_INDEX[occurrence.slot], occurrence.position, occurrence.name)
