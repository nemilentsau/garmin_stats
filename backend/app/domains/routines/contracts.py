"""API and persistence contracts for the live routine runtime."""

from __future__ import annotations

from typing import Any, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, model_validator


class _DefaultsRequired(BaseModel):
    """Base for models where defaulted fields stay required in JSON schema output."""

    model_config = ConfigDict(json_schema_serialization_defaults_required=True)


class _AutoTotalResponse(_DefaultsRequired):
    """Response base that auto-computes ``total`` from the items list field."""

    _items_field: ClassVar[str]

    def __init_subclass__(cls, items_field: str = "", **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if items_field:
            cls._items_field = items_field

    @model_validator(mode="before")
    @classmethod
    def _auto_fill_total(cls, data: Any) -> Any:
        if isinstance(data, dict) and "total" not in data:
            items = data.get(cls._items_field)
            if isinstance(items, list):
                data["total"] = len(items)
        return data


class _StrictDefaultsRequired(_DefaultsRequired):
    """Base for request models that must reject unknown keys."""

    model_config = ConfigDict(
        json_schema_serialization_defaults_required=True,
        extra="forbid",
    )


EntityStatus = Literal["active", "retired", "paused"]
RendererFamily = Literal["timer_session", "checklist_block", "exercise_block"]
SlotName = Literal["morning", "midday", "evening", "anytime"]
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


class CardTemplate(_DefaultsRequired):
    id: str
    name: str
    renderer: RendererFamily
    slot_default: SlotName
    status: EntityStatus = "active"
    summary: str | None = None
    tags: list[str] = []
    payload_json: dict[str, object] = {}
    source_artifact_id: str | None = None


class CardTemplatesResponse(_AutoTotalResponse, items_field="cards"):
    cards: list[CardTemplate] = []
    total: int = 0


class RoutineSchedule(_DefaultsRequired):
    id: str
    name: str
    status: EntityStatus = "active"
    start_date: str
    end_date: str | None = None
    tags: list[str] = []
    notes: str | None = None
    source_artifact_id: str | None = None


class RoutineAssignment(_DefaultsRequired):
    id: str
    routine_id: str
    card_template_id: str
    date: str
    slot: SlotName
    position: int = 0
    prescription_override_json: dict[str, object] = {}


class RoutineSchedulesResponse(_AutoTotalResponse, items_field="routines"):
    routines: list[RoutineSchedule] = []
    total: int = 0


class RoutineAssignmentsResponse(_AutoTotalResponse, items_field="assignments"):
    assignments: list[RoutineAssignment] = []
    total: int = 0


class CardLog(_DefaultsRequired):
    id: str
    date: str
    occurrence_key: str
    card_template_id: str
    assignment_id: str | None = None
    status: CardLogStatus = "pending"
    actual_json: dict[str, object] = {}
    notes: str | None = None


class CardOverride(_DefaultsRequired):
    id: str
    date: str
    action: CardOverrideAction
    target_occurrence_key: str | None = None
    card_template_id: str | None = None
    slot: SlotName | None = None
    position: int | None = None
    notes: str | None = None


class TodayCardLogUpdateRequest(_StrictDefaultsRequired):
    card_template_id: str
    assignment_id: str | None = None
    status: CardLogStatus = "completed"
    actual_json: dict[str, object] = {}
    notes: str | None = None


class TodayStats(_DefaultsRequired):
    total: int = 0
    completed: int = 0
    partial: int = 0
    skipped: int = 0
    pending: int = 0


class TodayCard(_DefaultsRequired):
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
    renderer: RendererFamily
    summary: str | None = None
    tags: list[str] = []
    payload_json: dict[str, object] = {}
    status: CardLogStatus = "pending"
    actual_json: dict[str, object] = {}
    notes: str | None = None


class TodaySlot(_DefaultsRequired):
    slot: SlotName
    label: str
    cards: list[TodayCard] = []


class TodayResponse(_DefaultsRequired):
    date: str
    stats: TodayStats
    slots: list[TodaySlot] = []


class CardLogStatusEntry(_DefaultsRequired):
    """Lightweight completion status for a single card occurrence."""

    occurrence_key: str
    status: CardLogStatus


class CardLogRangeResponse(_DefaultsRequired):
    """Completion statuses for a date range of card occurrences."""

    start_date: str
    end_date: str
    entries: list[CardLogStatusEntry] = []


class ScheduleOccurrence(_DefaultsRequired):
    occurrence_key: str
    date: str
    slot: SlotName
    position: int = 0
    source_kind: ScheduleOccurrenceSourceKind = "scheduled"
    schedule_override_action: CardOverrideAction | None = None
    target_occurrence_key: str | None = None
    routine_id: str | None = None
    routine_name: str | None = None
    assignment_id: str | None = None
    card_template_id: str
    name: str
    renderer: RendererFamily
    summary: str | None = None
    tags: list[str] = []
    payload_json: dict[str, object] = {}


class ScheduleDay(_DefaultsRequired):
    date: str
    weekday: WeekdayName
    occurrences: list[ScheduleOccurrence] = []


class ScheduleWindow(_DefaultsRequired):
    start_date: str
    end_date: str
    days: list[ScheduleDay] = []
