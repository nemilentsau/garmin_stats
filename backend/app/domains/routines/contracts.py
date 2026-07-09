"""Pydantic contracts owned by the routines domain.

These models describe the compiled live runtime: card templates, routine
schedules, dated occurrences, Today-board responses, and card logs. Draft
artifact specs are owned by the artifacts domain.
"""

from __future__ import annotations

import logging
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, model_validator

from app.contracts.base import (
    AutoTotalResponse,
    DefaultsRequired,
    EntityStatus,
    StrictDefaultsRequired,
)

log = logging.getLogger(__name__)

SlotName = Literal["morning", "midday", "evening", "anytime"]
CardType = Literal[
    "running_workout",
    "strength_session",
    "breath_timer",
    "meditation_timer",
    "checklist",
]
RunSegmentKind = Literal["warmup", "main", "strides", "cooldown", "intervals"]


class RatingPrompt(StrictDefaultsRequired):
    """One post-session rating prompt shared by workout card payloads."""

    key: str
    label: str
    scale_min: int = 1
    scale_max: int = 5


class RunSegment(StrictDefaultsRequired):
    """One segment of a running workout; prescription is a range string."""

    id: str
    label: str
    kind: RunSegmentKind
    detail: str | None = None
    prescription: str


class RunCustomField(StrictDefaultsRequired):
    """A custom per-run data field to collect after a run (e.g. weather confounders)."""

    key: str
    label: str
    field_type: Literal["number", "text"] = "number"
    unit: str | None = None


class RunningWorkoutPayload(StrictDefaultsRequired):
    """Typed prescription for a running workout card."""

    card_type: Literal["running_workout"] = "running_workout"
    workout_type: str
    rpe: str | None = None
    talk_test: str | None = None
    hr_guidance: str | None = None
    calibration_quality: bool = False
    instructions: str | None = None
    segments: list[RunSegment] = []
    post_run_fields: list[RunCustomField] = []
    variant_options: list[str] = []
    selection_rule: str | None = None


class StrengthExercise(StrictDefaultsRequired):
    """One prescribed strength exercise; set_scheme is a range string."""

    id: str
    label: str
    detail: str | None = None
    set_scheme: str


class StrengthSessionPayload(StrictDefaultsRequired):
    """Typed prescription for a strength session card."""

    card_type: Literal["strength_session"] = "strength_session"
    session_focus: str | None = None
    duration_minutes: int | None = None
    rir_guidance: str | None = None
    instructions: str | None = None
    exercises: list[StrengthExercise] = []
    rating_prompts: list[RatingPrompt] = []
    variant_options: list[str] = []
    selection_rule: str | None = None


class BreathTimerPayload(StrictDefaultsRequired):
    """Typed prescription for a breathwork timer card."""

    card_type: Literal["breath_timer"] = "breath_timer"
    duration_minutes: int
    pattern_label: str
    instructions: str | None = None


class MeditationTimerPayload(StrictDefaultsRequired):
    """Typed prescription for a meditation timer card."""

    card_type: Literal["meditation_timer"] = "meditation_timer"
    duration_minutes: int
    technique: str
    anchor: str | None = None
    instructions: str | None = None
    rating_prompts: list[RatingPrompt] = []


class ChecklistItem(StrictDefaultsRequired):
    """One checklist item inside a checklist card payload.

    ``kind`` selects the answer shape: ``checkbox`` items are answered with
    ``ChecklistAnswer.checked``/``text``; ``tissue_check`` items are answered
    with ``ChecklistAnswer.scale``/``flagged`` (a 0-3 soreness rating plus a
    pain flag), used for the per-tissue morning check-in.
    """

    id: str
    label: str
    detail: str | None = None
    kind: Literal["checkbox", "tissue_check"] = "checkbox"


class ChecklistPayload(StrictDefaultsRequired):
    """Typed prescription for a checklist card (reviews, setup, skip days)."""

    card_type: Literal["checklist"] = "checklist"
    instructions: str | None = None
    items: list[ChecklistItem] = []
    domain: str | None = None
    variant_options: list[str] = []
    selection_rule: str | None = None


CardPayload = Annotated[
    RunningWorkoutPayload
    | StrengthSessionPayload
    | BreathTimerPayload
    | MeditationTimerPayload
    | ChecklistPayload,
    Field(discriminator="card_type"),
]


class RunningActual(StrictDefaultsRequired):
    """Logged actuals for a completed running workout.

    Free-text notes deliberately live on ``CardLog.notes`` (one notes field per
    occurrence), not inside the actual.
    """

    card_type: Literal["running_workout"] = "running_workout"
    distance_km: float | None = None
    duration_min: float | None = None
    avg_hr: int | None = None
    hr_drift_pct: float | None = None
    calibration_quality: bool = False
    rpe: int | None = None
    post_run: dict[str, float | str | None] = {}  # keyed by RunCustomField.key → logged value


class StrengthSetLog(StrictDefaultsRequired):
    """One logged set of a strength exercise."""

    set_index: int
    weight: float | None = None
    reps: int | None = None
    rir: int | None = None


class LoggedStrengthExercise(StrictDefaultsRequired):
    """One logged exercise; extras carry a free-text label and is_extra=True."""

    exercise_id: str | None = None
    label: str | None = None
    is_extra: bool = False
    sets: list[StrengthSetLog] = []


class StrengthActual(StrictDefaultsRequired):
    """Logged actuals for a strength session, including off-script extras."""

    card_type: Literal["strength_session"] = "strength_session"
    exercises: list[LoggedStrengthExercise] = []
    ratings: dict[str, int] = {}


class TimerActual(StrictDefaultsRequired):
    """Logged ratings for a breath or meditation timer session."""

    card_type: Literal["breath_timer", "meditation_timer"]
    ratings: dict[str, int] = {}


class ChecklistAnswer(StrictDefaultsRequired):
    """One answered checklist item.

    ``checked``/``text`` answer ``checkbox`` items; ``scale``/``flagged``
    answer ``tissue_check`` items (see ``ChecklistItem.kind``).
    """

    item_id: str
    checked: bool = False
    text: str | None = None
    scale: int | None = Field(default=None, ge=0, le=3)
    flagged: bool = False


class ChecklistActual(StrictDefaultsRequired):
    """Logged answers for a checklist card."""

    card_type: Literal["checklist"] = "checklist"
    answers: list[ChecklistAnswer] = []


CardActual = Annotated[
    RunningActual
    | StrengthActual
    | TimerActual
    | ChecklistActual,
    Field(discriminator="card_type"),
]

WeekdayName = Literal[
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
]
CardLogStatus = Literal["pending", "completed", "partial", "skipped"]
CardOverrideAction = Literal["add", "hide", "replace"]
ScheduleOccurrenceSourceKind = Literal["scheduled", "override_add", "override_replace"]


class CardTemplate(DefaultsRequired):
    """Live reusable routine card template."""

    id: str
    name: str
    slot_default: SlotName
    status: EntityStatus = "active"
    summary: str | None = None
    tags: list[str] = []
    payload_json: CardPayload
    source_artifact_id: str | None = None


class CardTemplatesResponse(AutoTotalResponse, items_field="cards"):
    """List response for live routine card templates."""

    cards: list[CardTemplate] = []


class RoutineSchedule(DefaultsRequired):
    """Live routine schedule metadata."""

    id: str
    name: str
    status: EntityStatus = "active"
    start_date: str
    end_date: str | None = None
    tags: list[str] = []
    notes: str | None = None
    source_artifact_id: str | None = None


class RoutineAssignment(DefaultsRequired):
    """Dated card assignment compiled from an active routine schedule."""

    id: str
    routine_id: str
    card_template_id: str
    date: str
    slot: SlotName
    position: int = 0
    prescription_override_json: dict[str, object] = {}


class RoutineActivationAssignment(StrictDefaultsRequired):
    """Relative-day card assignment accepted by routine activation."""

    id: str
    card_template_id: str
    day: int
    slot: SlotName
    position: int = 0
    prescription_override_json: dict[str, object] = {}


class RoutineActivationCommand(DefaultsRequired):
    """Command for compiling a routine spec into live dated assignments."""

    id: str
    name: str
    status: EntityStatus = "active"
    start_date: str
    end_date: str | None = None
    tags: list[str] = []
    notes: str | None = None
    source_artifact_id: str | None = None
    assignments: list[RoutineActivationAssignment] = []


class RoutineSchedulesResponse(AutoTotalResponse, items_field="routines"):
    """List response for live routine schedules."""

    routines: list[RoutineSchedule] = []


class RoutineAssignmentsResponse(AutoTotalResponse, items_field="assignments"):
    """List response for live routine assignments."""

    assignments: list[RoutineAssignment] = []


_ACTUAL_MODELS: dict[str, type[BaseModel]] = {
    "running_workout": RunningActual,
    "strength_session": StrengthActual,
    "breath_timer": TimerActual,
    "meditation_timer": TimerActual,
    "checklist": ChecklistActual,
}


def _coerce_empty_actual_json(data: Any) -> Any:
    """Coerce ``actual_json: {}`` in a client-sent body to None.

    Clients may send an empty dict for "nothing logged"; there is no
    discriminator to dispatch on, so treat it as absent.  Anything else is left
    for strict union validation — a client sending an undispatchable or
    unknown-field actual is a request error (422), never silently rewritten.
    """
    if isinstance(data, dict) and data.get("actual_json") == {}:
        return {**data, "actual_json": None}
    return data


def _normalize_stored_actual_json(data: Any) -> Any:
    """Normalize legacy stored actual_json shapes so reads never 500.

    Reads are tolerant while writes stay strict (see
    ``TodayCardLogUpdateRequest``).  Three legacy shapes are handled:

    - ``{}`` → None (rows written before the typed union existed);
    - a known ``card_type`` with unknown top-level keys → the unknown keys are
      dropped, so rows written before a field was removed from the contract
      (e.g. breath ``completed_cycles``) still load;
    - a missing or unknown ``card_type`` → None with a warning; the typed union
      cannot represent the shape and the Today board must stay available.
    """
    if not isinstance(data, dict):
        return data
    actual = data.get("actual_json")
    if not isinstance(actual, dict):
        return data

    card_type = actual.get("card_type")
    model = _ACTUAL_MODELS.get(card_type) if isinstance(card_type, str) else None
    if model is None:
        if any(key != "card_type" for key in actual):
            log.warning(
                "Nulling stored actual_json with undispatchable card_type %r (keys: %s)",
                card_type,
                sorted(actual),
            )
        return {**data, "actual_json": None}

    unknown_keys = actual.keys() - model.model_fields.keys()
    if unknown_keys:
        log.warning(
            "Dropping legacy actual_json keys %s for card_type %r",
            sorted(unknown_keys),
            card_type,
        )
        return {
            **data,
            "actual_json": {k: v for k, v in actual.items() if k not in unknown_keys},
        }
    return data


class CardLog(DefaultsRequired):
    """User completion log for one dated card occurrence."""

    id: str
    date: str
    occurrence_key: str
    card_template_id: str
    assignment_id: str | None = None
    status: CardLogStatus = "pending"
    actual_json: CardActual | None = None
    notes: str | None = None
    variant_taken: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _normalize_actual_json(cls, data: Any) -> Any:
        return _normalize_stored_actual_json(data)


class CardOverride(DefaultsRequired):
    """Dated add/hide/replace override for routine card occurrences."""

    id: str
    date: str
    action: CardOverrideAction
    target_occurrence_key: str | None = None
    card_template_id: str | None = None
    slot: SlotName | None = None
    position: int | None = None
    notes: str | None = None


class TodayCardLogUpdateRequest(StrictDefaultsRequired):
    """Request body for updating a Today-board card log."""

    card_template_id: str
    assignment_id: str | None = None
    status: CardLogStatus = "completed"
    actual_json: CardActual | None = None
    notes: str | None = None
    variant_taken: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _coerce_actual_json(cls, data: Any) -> Any:
        return _coerce_empty_actual_json(data)


class TodayStats(DefaultsRequired):
    """Completion counts for a Today-board response."""

    total: int = 0
    completed: int = 0
    partial: int = 0
    skipped: int = 0
    pending: int = 0


class ScheduleOccurrence(DefaultsRequired):
    """Resolved scheduled or override-created card occurrence."""

    occurrence_key: str
    date: str
    slot: SlotName
    position: int = 0
    source_kind: ScheduleOccurrenceSourceKind
    schedule_override_action: CardOverrideAction | None = None
    target_occurrence_key: str | None = None
    routine_id: str | None = None
    routine_name: str | None = None
    assignment_id: str | None = None
    card_template_id: str
    name: str
    summary: str | None = None
    tags: list[str] = []
    payload_json: CardPayload


class TodayCard(ScheduleOccurrence):
    """Resolved Today-board card occurrence with log state attached."""

    status: CardLogStatus = "pending"
    actual_json: CardActual | None = None
    notes: str | None = None
    variant_taken: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _normalize_actual_json(cls, data: Any) -> Any:
        return _normalize_stored_actual_json(data)


class TodaySlot(DefaultsRequired):
    """One named Today-board slot containing resolved cards."""

    slot: SlotName
    label: str
    cards: list[TodayCard] = []


class TodayResponse(DefaultsRequired):
    """Today-board response for one local date."""

    date: str
    stats: TodayStats
    slots: list[TodaySlot] = []


class CardLogStatusEntry(DefaultsRequired):
    """Compact card-log status entry for schedule overlays."""

    occurrence_key: str
    status: CardLogStatus


class CardLogRangeResponse(DefaultsRequired):
    """Card-log statuses for a date range."""

    start_date: str
    end_date: str
    entries: list[CardLogStatusEntry] = []


class ScheduleDay(DefaultsRequired):
    """Resolved routine occurrences for one calendar day."""

    date: str
    weekday: WeekdayName
    occurrences: list[ScheduleOccurrence] = []


class ScheduleWindow(DefaultsRequired):
    """Resolved routine schedule window."""

    start_date: str
    end_date: str
    days: list[ScheduleDay] = []
