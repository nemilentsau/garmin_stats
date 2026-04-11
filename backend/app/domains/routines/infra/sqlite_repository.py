"""SQLite repository adapter for the routines domain."""

from __future__ import annotations

from app.infra.database import (
    load_card_logs,
    load_card_logs_range,
    load_card_overrides_range,
    load_card_template,
    load_card_templates,
    load_routine_assignments,
    load_routine_schedule,
    load_routine_schedules,
    replace_routine_assignments,
    save_card_log,
    save_routine_schedule,
    save_routine_schedule_with_assignments,
)
from app.models import (
    CardLog,
    CardOverride,
    CardTemplate,
    RoutineAssignment,
    RoutineSchedule,
)


class SqliteRoutineRepository:
    def list_routines(self, *, status: str | None = None) -> list[RoutineSchedule]:
        return load_routine_schedules(status=status)

    def get_routine(self, routine_id: str) -> RoutineSchedule | None:
        return load_routine_schedule(routine_id)

    def list_assignments(self, *, routine_id: str | None = None) -> list[RoutineAssignment]:
        return load_routine_assignments(routine_id=routine_id)

    def list_card_templates(self, *, status: str | None = None) -> list[CardTemplate]:
        return load_card_templates(status=status)

    def get_card_template(self, card_id: str) -> CardTemplate | None:
        return load_card_template(card_id)

    def list_card_overrides_range(self, *, start_date: str, end_date: str) -> list[CardOverride]:
        return load_card_overrides_range(start_date, end_date)

    def list_card_logs(self, *, date: str | None = None) -> list[CardLog]:
        return load_card_logs(date)

    def list_card_logs_range(self, *, start_date: str, end_date: str) -> list[CardLog]:
        return load_card_logs_range(start_date, end_date)

    def save_card_log(self, log: CardLog) -> None:
        save_card_log(log)

    def save_routine(self, routine: RoutineSchedule) -> None:
        save_routine_schedule(routine)

    def save_routine_with_assignments(
        self,
        *,
        routine: RoutineSchedule,
        assignments: list[RoutineAssignment],
    ) -> None:
        save_routine_schedule_with_assignments(routine, assignments)

    def replace_assignments(
        self,
        *,
        routine_id: str,
        assignments: list[RoutineAssignment],
    ) -> None:
        replace_routine_assignments(routine_id, assignments)
