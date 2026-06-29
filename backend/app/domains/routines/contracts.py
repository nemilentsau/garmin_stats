"""Pydantic contracts owned by the routines domain.

These models describe the compiled live runtime: card templates, routine
schedules, dated occurrences, Today-board responses, and card logs. Draft
artifact specs are owned by the artifacts domain.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field

from app.contracts.base import (
    AutoTotalResponse,
    DefaultsRequired,
    EntityStatus,
    StrictDefaultsRequired,
)

SlotName = Literal["morning", "midday", "evening", "anytime"]
CardType = Literal[
    "running_workout",
    "strength_session",
    "breath_timer",
    "meditation_timer",
    "checklist",
]
RunSegmentKind = Literal["warmup", "main", "strides", "cooldown", "intervals"]
BreathPhaseKind = Literal["inhale", "hold_full", "exhale", "hold_empty"]


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


class BreathPhase(StrictDefaultsRequired):
    """One timed phase of a breathing pattern."""

    kind: BreathPhaseKind
    seconds: int


class BreathTimerPayload(StrictDefaultsRequired):
    """Typed prescription for a breathwork timer card."""

    card_type: Literal["breath_timer"] = "breath_timer"
    duration_minutes: int
    pattern_label: str
    phases: list[BreathPhase] = []
    instructions: str | None = None
    rating_prompts: list[RatingPrompt] = []


class MeditationTimerPayload(StrictDefaultsRequired):
    """Typed prescription for a meditation timer card."""

    card_type: Literal["meditation_timer"] = "meditation_timer"
    duration_minutes: int
    technique: str
    anchor: str | None = None
    instructions: str | None = None
    rating_prompts: list[RatingPrompt] = []


class ChecklistItem(StrictDefaultsRequired):
    """One checklist item inside a checklist card payload."""

    id: str
    label: str
    detail: str | None = None


class ChecklistPayload(StrictDefaultsRequired):
    """Typed prescription for a checklist card (reviews, setup, skip days)."""

    card_type: Literal["checklist"] = "checklist"
    instructions: str | None = None
    items: list[ChecklistItem] = []
    domain: str | None = None


CardPayload = Annotated[
    RunningWorkoutPayload
    | StrengthSessionPayload
    | BreathTimerPayload
    | MeditationTimerPayload
    | ChecklistPayload,
    Field(discriminator="card_type"),
]


class RunningActual(StrictDefaultsRequired):
    """Logged actuals for a completed running workout."""

    card_type: Literal["running_workout"] = "running_workout"
    distance_km: float | None = None
    duration_min: float | None = None
    avg_hr: int | None = None
    hr_drift_pct: float | None = None
    calibration_quality: bool = False
    rpe: int | None = None
    notes: str | None = None


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
    completed_cycles: int | None = None


class ChecklistAnswer(StrictDefaultsRequired):
    """One answered checklist item."""

    item_id: str
    checked: bool = False
    text: str | None = None


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
