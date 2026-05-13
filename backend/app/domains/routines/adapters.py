"""SQLite-backed routine repository adapter.

This module is the database boundary for the live routine runtime. It owns
routine/card CRUD and depends only on shared SQLite connection primitives.
"""

from __future__ import annotations

import sqlite3

from app.domains.routines.contracts import (
    CardLog,
    CardOverride,
    CardTemplate,
    RoutineAssignment,
    RoutineSchedule,
)
from app.infra.jsonstore import JsonStore
from app.infra.sqlite import connect

_STORE = JsonStore({
    "card_templates",
    "routine_schedules",
    "routine_assignments",
    "card_logs",
    "card_overrides",
})


def save_card_template(card: CardTemplate) -> None:
    """Persist one live card template."""
    _STORE.save("card_templates", card.id, card.model_dump_json())


def load_card_template(card_id: str) -> CardTemplate | None:
    """Load one live card template by id."""
    return _STORE.load("card_templates", CardTemplate, card_id)


def load_card_templates(status: str | None = None) -> list[CardTemplate]:
    """Load live card templates, optionally filtered by status."""
    where_sql = ""
    params: tuple[object, ...] = ()
    if status is not None:
        where_sql = "json_extract(data, '$.status') = ?"
        params = (status,)
    return _STORE.load_many(
        "card_templates",
        CardTemplate,
        where_sql=where_sql,
        params=params,
    )


def save_routine_schedule(routine: RoutineSchedule) -> None:
    """Persist one live routine schedule."""
    _STORE.save("routine_schedules", routine.id, routine.model_dump_json())


def load_routine_schedule(routine_id: str) -> RoutineSchedule | None:
    """Load one live routine schedule by id."""
    return _STORE.load("routine_schedules", RoutineSchedule, routine_id)


def load_routine_schedules(status: str | None = None) -> list[RoutineSchedule]:
    """Load live routine schedules, optionally filtered by status."""
    where_sql = ""
    params: tuple[object, ...] = ()
    if status is not None:
        where_sql = "json_extract(data, '$.status') = ?"
        params = (status,)
    return _STORE.load_many(
        "routine_schedules",
        RoutineSchedule,
        where_sql=where_sql,
        params=params,
    )


def _validate_routine_assignment_ids(
    routine_id: str,
    assignments: list[RoutineAssignment],
) -> None:
    if any(assignment.routine_id != routine_id for assignment in assignments):
        raise ValueError("All assignments must match the provided routine_id")


def _guard_assignment_ownership(
    con: sqlite3.Connection,
    routine_id: str,
    assignments: list[RoutineAssignment],
) -> None:
    if not assignments:
        return

    placeholders = ", ".join("?" for _ in assignments)
    rows = con.execute(
        "SELECT id, routine_id FROM routine_assignments WHERE id IN "
        f"({placeholders})",
        [assignment.id for assignment in assignments],
    ).fetchall()
    existing_routine_ids = {str(row["id"]): str(row["routine_id"]) for row in rows}
    for assignment in assignments:
        owner_routine_id = existing_routine_ids.get(assignment.id)
        if owner_routine_id is not None and owner_routine_id != routine_id:
            raise ValueError(
                f"Assignment id '{assignment.id}' already belongs to routine "
                f"{owner_routine_id}"
            )


def _replace_routine_assignments_in_connection(
    con: sqlite3.Connection,
    routine_id: str,
    assignments: list[RoutineAssignment],
) -> None:
    _validate_routine_assignment_ids(routine_id, assignments)
    _guard_assignment_ownership(con, routine_id, assignments)
    con.execute("DELETE FROM routine_assignments WHERE routine_id = ?", (routine_id,))
    for assignment in assignments:
        _STORE.save_in_connection(
            con,
            "routine_assignments",
            assignment.id,
            assignment.model_dump_json(),
            extra_columns={
                "routine_id": assignment.routine_id,
                "card_template_id": assignment.card_template_id,
                "assignment_date": assignment.date,
                "slot": assignment.slot,
                "position": assignment.position,
            },
        )


def save_routine_schedule_with_assignments(
    routine: RoutineSchedule,
    assignments: list[RoutineAssignment],
) -> None:
    """Atomically persist a routine schedule and replace its assignments."""
    with connect() as con:
        con.execute("BEGIN IMMEDIATE")
        try:
            _STORE.save_in_connection(
                con,
                "routine_schedules",
                routine.id,
                routine.model_dump_json(),
            )
            _replace_routine_assignments_in_connection(con, routine.id, assignments)
        except Exception:
            con.rollback()
            raise
        else:
            con.commit()


def replace_routine_assignments(
    routine_id: str,
    assignments: list[RoutineAssignment],
) -> None:
    """Atomically replace all assignments for one routine schedule."""
    with connect() as con:
        con.execute("BEGIN IMMEDIATE")
        try:
            _replace_routine_assignments_in_connection(con, routine_id, assignments)
        except Exception:
            con.rollback()
            raise
        else:
            con.commit()


def load_routine_assignments(routine_id: str | None = None) -> list[RoutineAssignment]:
    """Load dated routine assignments, optionally for one routine."""
    where_sql = "routine_id = ?" if routine_id is not None else ""
    params = (routine_id,) if routine_id is not None else ()
    return _STORE.load_many(
        "routine_assignments",
        RoutineAssignment,
        where_sql=where_sql,
        params=params,
        order_by="routine_id, assignment_date, slot, position, id",
    )


def save_card_log(log: CardLog) -> None:
    """Persist one card completion log."""
    _STORE.save(
        "card_logs",
        log.id,
        log.model_dump_json(),
        extra_columns={
            "occurrence_key": log.occurrence_key,
            "log_date": log.date,
            "card_template_id": log.card_template_id,
            "assignment_id": log.assignment_id,
        },
    )


def load_card_logs(date: str | None = None) -> list[CardLog]:
    """Load card logs, optionally restricted to one date."""
    where_sql = "log_date = ?" if date is not None else ""
    params = (date,) if date is not None else ()
    return _STORE.load_many(
        "card_logs",
        CardLog,
        where_sql=where_sql,
        params=params,
        order_by="log_date, created_at, id",
    )


def load_card_logs_range(start_date: str, end_date: str) -> list[CardLog]:
    """Load card logs for a date range (inclusive on both ends)."""
    return _STORE.load_many(
        "card_logs",
        CardLog,
        where_sql="log_date >= ? AND log_date <= ?",
        params=(start_date, end_date),
        order_by="log_date, created_at, id",
    )


def load_card_overrides_range(
    start_date: str,
    end_date: str,
) -> list[CardOverride]:
    """Load card overrides for a contiguous date range (inclusive)."""
    return _STORE.load_many(
        "card_overrides",
        CardOverride,
        where_sql="override_date >= ? AND override_date <= ?",
        params=(start_date, end_date),
        order_by="override_date, created_at, id",
    )


class SqliteRoutineRepository:
    """Repository adapter used by routine application use cases."""

    def save_card_template(self, card: CardTemplate) -> None:
        save_card_template(card)

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
