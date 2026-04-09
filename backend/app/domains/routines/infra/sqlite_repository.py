"""SQLite repository adapter for the routines domain."""

from __future__ import annotations

from app.infra.database import (
    load_card_logs,
    load_card_logs_range,
    load_card_overrides_range,
    load_card_template,
    load_card_templates,
    load_routine_assignment_routine_ids,
    load_routine_assignments,
    load_routine_schedule,
    load_routine_schedules,
    replace_routine_assignments,
    save_card_log,
    save_routine_schedule,
)
from app.models import CardLog, RoutineAssignment, RoutineSchedule


class SqliteRoutineRepository:
    def list_routines(self, *, status: str | None = None):
        return load_routine_schedules(status=status)

    def get_routine(self, routine_id: str):
        return load_routine_schedule(routine_id)

    def list_assignments(self, *, routine_id: str | None = None):
        return load_routine_assignments(routine_id=routine_id)

    def list_card_templates(self, *, status: str | None = None):
        return load_card_templates(status=status)

    def get_card_template(self, card_id: str):
        return load_card_template(card_id)

    def list_card_overrides_range(self, *, start_date: str, end_date: str):
        return load_card_overrides_range(start_date, end_date)

    def list_card_logs(self, *, date: str | None = None):
        return load_card_logs(date)

    def list_card_logs_range(self, *, start_date: str, end_date: str):
        return load_card_logs_range(start_date, end_date)

    def save_card_log(self, log: CardLog) -> None:
        save_card_log(log)

    def save_routine(self, routine: RoutineSchedule) -> None:
        save_routine_schedule(routine)

    def replace_assignments(
        self,
        *,
        routine_id: str,
        assignments: list[RoutineAssignment],
    ) -> None:
        if any(assignment.routine_id != routine_id for assignment in assignments):
            raise ValueError("All assignments must match the provided routine_id")

        existing_routine_ids = load_routine_assignment_routine_ids(
            [assignment.id for assignment in assignments]
        )
        for assignment in assignments:
            owner_routine_id = existing_routine_ids.get(assignment.id)
            if owner_routine_id is not None and owner_routine_id != routine_id:
                raise ValueError(
                    f"Assignment id '{assignment.id}' already belongs to routine "
                    f"{owner_routine_id}"
                )

        replace_routine_assignments(routine_id, assignments)
