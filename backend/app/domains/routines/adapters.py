"""SQLite-backed routine repository adapter.

This module is the database boundary for the live routine runtime. It owns
routine/card CRUD and depends only on shared SQLite connection primitives, not
the broad `app.infra.database` persistence bucket.
"""

from __future__ import annotations

import json
import sqlite3

from app.domains.routines.contracts import (
    CardLog,
    CardOverride,
    CardTemplate,
    Routine,
    RoutineAssignment,
    RoutineEntry,
    RoutineSchedule,
)
from app.infra.sqlite import connect
from app.utils.timeutil import now_iso

_ROUTINE_TABLES = frozenset({
    "routines",
    "routine_entries",
    "card_templates",
    "routine_schedules",
    "routine_assignments",
    "card_logs",
    "card_overrides",
})


def _validate_table(table: str) -> None:
    if table not in _ROUTINE_TABLES:
        raise ValueError(f"Invalid routine table name: {table}")


def _save_json_record(
    table: str,
    record_id: str,
    data_json: str,
    *,
    extra_columns: dict[str, object | None] | None = None,
    created_at: str | None = None,
    updated_at: str | None = None,
) -> None:
    _validate_table(table)
    with connect() as con, con:
        _save_json_record_in_connection(
            con,
            table,
            record_id,
            data_json,
            extra_columns=extra_columns,
            created_at=created_at,
            updated_at=updated_at,
        )


def _save_json_record_in_connection(
    con: sqlite3.Connection,
    table: str,
    record_id: str,
    data_json: str,
    *,
    extra_columns: dict[str, object | None] | None = None,
    created_at: str | None = None,
    updated_at: str | None = None,
) -> None:
    _validate_table(table)
    extra_columns = extra_columns or {}
    updated_value = updated_at or now_iso()
    existing_created_at: str | None = None
    if created_at is None:
        row = con.execute(
            f"SELECT created_at FROM {table} WHERE id = ?",  # noqa: S608
            (record_id,),
        ).fetchone()
        existing_created_at = row["created_at"] if row is not None else None

    created_value = created_at or existing_created_at or now_iso()
    columns = ["id", *extra_columns.keys(), "data", "created_at", "updated_at"]
    placeholders = ", ".join("?" for _ in columns)
    values = [record_id, *extra_columns.values(), data_json, created_value, updated_value]
    con.execute(
        f"INSERT OR REPLACE INTO {table} ({', '.join(columns)}) VALUES ({placeholders})",  # noqa: S608
        values,
    )


def _model_from_row[M](model: type[M], row: sqlite3.Row) -> M:
    payload = json.loads(row["data"])
    for key in ("created_at", "updated_at"):
        if payload.get(key) is None and row[key] is not None:
            payload[key] = row[key]
    return model.model_validate(payload)  # type: ignore[union-attr]


def _load_json_record[M](
    table: str,
    model: type[M],
    record_id: str,
) -> M | None:
    _validate_table(table)
    with connect() as con:
        row = con.execute(
            f"SELECT data, created_at, updated_at FROM {table} WHERE id = ?",  # noqa: S608
            (record_id,),
        ).fetchone()
    if row is None:
        return None
    return _model_from_row(model, row)


def _load_json_records[M](
    table: str,
    model: type[M],
    *,
    where_sql: str = "",
    params: tuple[object, ...] = (),
    order_by: str = "created_at, id",
) -> list[M]:
    _validate_table(table)
    query = f"SELECT data, created_at, updated_at FROM {table}"  # noqa: S608
    if where_sql:
        query += f" WHERE {where_sql}"  # noqa: S608
    query += f" ORDER BY {order_by}"  # noqa: S608
    with connect() as con:
        rows = con.execute(query, params).fetchall()
    return [_model_from_row(model, row) for row in rows]


def _record_exists(table: str, record_id: str) -> bool:
    _validate_table(table)
    with connect() as con:
        row = con.execute(
            f"SELECT 1 FROM {table} WHERE id = ? LIMIT 1",  # noqa: S608
            (record_id,),
        ).fetchone()
    return row is not None


def _delete_json_record(table: str, record_id: str) -> None:
    _validate_table(table)
    with connect() as con, con:
        con.execute(
            f"DELETE FROM {table} WHERE id = ?",  # noqa: S608
            (record_id,),
        )


def routine_exists(routine_id: str) -> bool:
    return _record_exists("routines", routine_id)


def save_routine(routine: Routine) -> None:
    _save_json_record("routines", routine.id, routine.model_dump_json())


def delete_routine(routine_id: str) -> None:
    _delete_json_record("routines", routine_id)


def load_routines() -> list[Routine]:
    return _load_json_records("routines", Routine)


def save_routine_entry(entry: RoutineEntry) -> None:
    _save_json_record(
        "routine_entries",
        entry.id,
        entry.model_dump_json(),
        extra_columns={
            "routine_id": entry.routine_id,
            "entry_date": entry.date,
        },
    )


def load_routine_entries(
    routine_id: str | None = None,
    date: str | None = None,
) -> list[RoutineEntry]:
    clauses: list[str] = []
    params: list[object] = []
    if routine_id:
        clauses.append("routine_id = ?")
        params.append(routine_id)
    if date:
        clauses.append("entry_date = ?")
        params.append(date)
    return _load_json_records(
        "routine_entries",
        RoutineEntry,
        where_sql=" AND ".join(clauses),
        params=tuple(params),
    )


def save_card_template(card: CardTemplate) -> None:
    _save_json_record("card_templates", card.id, card.model_dump_json())


def load_card_template(card_id: str) -> CardTemplate | None:
    return _load_json_record("card_templates", CardTemplate, card_id)


def load_card_templates(status: str | None = None) -> list[CardTemplate]:
    where_sql = ""
    params: tuple[object, ...] = ()
    if status is not None:
        where_sql = "json_extract(data, '$.status') = ?"
        params = (status,)
    return _load_json_records(
        "card_templates",
        CardTemplate,
        where_sql=where_sql,
        params=params,
    )


def save_routine_schedule(routine: RoutineSchedule) -> None:
    _save_json_record("routine_schedules", routine.id, routine.model_dump_json())


def load_routine_schedule(routine_id: str) -> RoutineSchedule | None:
    return _load_json_record("routine_schedules", RoutineSchedule, routine_id)


def load_routine_schedules(status: str | None = None) -> list[RoutineSchedule]:
    where_sql = ""
    params: tuple[object, ...] = ()
    if status is not None:
        where_sql = "json_extract(data, '$.status') = ?"
        params = (status,)
    return _load_json_records(
        "routine_schedules",
        RoutineSchedule,
        where_sql=where_sql,
        params=params,
    )


def delete_routine_assignments(routine_id: str) -> None:
    with connect() as con, con:
        con.execute("DELETE FROM routine_assignments WHERE routine_id = ?", (routine_id,))


def save_routine_assignment(assignment: RoutineAssignment) -> None:
    _save_json_record(
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
        _save_json_record_in_connection(
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
    with connect() as con:
        con.execute("BEGIN IMMEDIATE")
        try:
            _save_json_record_in_connection(
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
    where_sql = "routine_id = ?" if routine_id is not None else ""
    params = (routine_id,) if routine_id is not None else ()
    return _load_json_records(
        "routine_assignments",
        RoutineAssignment,
        where_sql=where_sql,
        params=params,
        order_by="routine_id, assignment_date, slot, position, id",
    )


def save_card_log(log: CardLog) -> None:
    _save_json_record(
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
    where_sql = "log_date = ?" if date is not None else ""
    params = (date,) if date is not None else ()
    return _load_json_records(
        "card_logs",
        CardLog,
        where_sql=where_sql,
        params=params,
        order_by="log_date, created_at, id",
    )


def load_card_logs_range(start_date: str, end_date: str) -> list[CardLog]:
    """Load card logs for a date range (inclusive on both ends)."""
    return _load_json_records(
        "card_logs",
        CardLog,
        where_sql="log_date >= ? AND log_date <= ?",
        params=(start_date, end_date),
        order_by="log_date, created_at, id",
    )


def save_card_override(override: CardOverride) -> None:
    _save_json_record(
        "card_overrides",
        override.id,
        override.model_dump_json(),
        extra_columns={
            "override_date": override.date,
            "action": override.action,
            "target_occurrence_key": override.target_occurrence_key,
        },
    )


def load_card_overrides(date: str | None = None) -> list[CardOverride]:
    where_sql = "override_date = ?" if date is not None else ""
    params = (date,) if date is not None else ()
    return _load_json_records(
        "card_overrides",
        CardOverride,
        where_sql=where_sql,
        params=params,
        order_by="override_date, created_at, id",
    )


def load_card_overrides_range(
    start_date: str,
    end_date: str,
) -> list[CardOverride]:
    """Load card overrides for a contiguous date range (inclusive)."""
    return _load_json_records(
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
