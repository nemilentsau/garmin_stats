"""Generic JSON-record CRUD over the shared SQLite connection.

Each persistence module defines a ``JsonStore`` bound to its own table
whitelist; the store handles the shared INSERT/SELECT/DELETE shape used by
records that store one Pydantic model per row plus ``created_at``/``updated_at``
columns. Table names are validated against the whitelist before being
interpolated into SQL.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable, Sequence

from app.infra.sqlite import connect
from app.utils.timeutil import now_iso

JSON_RECORD_COLUMNS_SQL = (
    "id TEXT PRIMARY KEY, data TEXT NOT NULL, "
    "created_at TEXT NOT NULL, updated_at TEXT NOT NULL"
)
"""SQL column fragment for tables consumed by ``JsonStore`` defaults."""

JSON_FIELD_SQL: dict[str, str] = {
    "$.kind": "json_extract(data, '$.kind')",
    "$.payload_json.id": "json_extract(data, '$.payload_json.id')",
    "$.status": "json_extract(data, '$.status')",
}
"""Allowlisted JSON payload paths that may be used in SQL predicates."""


def model_from_row[M](model: type[M], row: sqlite3.Row) -> M:
    """Parse a JSON ``data`` column into a Pydantic model with row timestamps."""
    payload = json.loads(row["data"])
    for key in ("created_at", "updated_at"):
        if payload.get(key) is None and row[key] is not None:
            payload[key] = row[key]
    return model.model_validate(payload)  # type: ignore[union-attr]


class JsonStore:
    """SQLite JSON-record CRUD bound to fixed table and JSON-field allowlists."""

    def __init__(self, allowed_tables: Iterable[str]) -> None:
        self._allowed = frozenset(allowed_tables)

    def _check(self, table: str) -> None:
        if table not in self._allowed:
            raise ValueError(f"Invalid table name: {table}")

    def json_field_predicate(
        self,
        path: str,
        values: Sequence[object],
    ) -> tuple[str, tuple[object, ...]]:
        """Build a parameterized predicate for an allowlisted JSON payload field.

        Empty value sequences deliberately match no rows so callers never emit
        invalid ``IN ()`` SQL. JSON paths are mapped through ``JSON_FIELD_SQL``
        before reaching SQL, keeping caller-provided path strings out of query
        interpolation.
        """
        field_sql = JSON_FIELD_SQL.get(path)
        if field_sql is None:
            raise ValueError(f"Invalid JSON filter path: {path}")

        params = tuple(values)
        if not params:
            return "0 = 1", ()
        if len(params) == 1:
            return f"{field_sql} = ?", params
        placeholders = ", ".join("?" for _ in params)
        return f"{field_sql} IN ({placeholders})", params

    def status_predicate(
        self,
        values: Sequence[object],
    ) -> tuple[str, tuple[object, ...]]:
        """Build a predicate for the conventional JSON ``status`` field."""
        return self.json_field_predicate("$.status", values)

    def save(
        self,
        table: str,
        record_id: str,
        data_json: str,
        *,
        extra_columns: dict[str, object | None] | None = None,
        created_at: str | None = None,
        updated_at: str | None = None,
    ) -> None:
        """Upsert one JSON-backed record in its own short transaction."""
        self._check(table)
        with connect() as con, con:
            self.save_in_connection(
                con,
                table,
                record_id,
                data_json,
                extra_columns=extra_columns,
                created_at=created_at,
                updated_at=updated_at,
            )

    def save_in_connection(
        self,
        con: sqlite3.Connection,
        table: str,
        record_id: str,
        data_json: str,
        *,
        extra_columns: dict[str, object | None] | None = None,
        created_at: str | None = None,
        updated_at: str | None = None,
    ) -> None:
        """Upsert one JSON-backed record using a caller-managed transaction."""
        self._check(table)
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

    def load[M](self, table: str, model: type[M], record_id: str) -> M | None:
        """Load one JSON-backed record by id, or ``None`` when missing."""
        self._check(table)
        with connect() as con:
            row = con.execute(
                f"SELECT data, created_at, updated_at FROM {table} WHERE id = ?",  # noqa: S608
                (record_id,),
            ).fetchone()
        if row is None:
            return None
        return model_from_row(model, row)

    def load_many[M](
        self,
        table: str,
        model: type[M],
        *,
        where_sql: str = "",
        params: tuple[object, ...] = (),
        order_by: str = "created_at, id",
        last_n: int | None = None,
    ) -> list[M]:
        """Load JSON-backed records with optional filtering and tail limit.

        When *last_n* is set the query returns only the last N rows (by
        *order_by*) while preserving ascending order in the result.
        """
        self._check(table)
        if last_n is not None and last_n > 0:
            desc_cols = ", ".join(f"{col.strip()} DESC" for col in order_by.split(","))
            inner = f"SELECT * FROM {table}"  # noqa: S608
            if where_sql:
                inner += f" WHERE {where_sql}"  # noqa: S608
            inner += f" ORDER BY {desc_cols} LIMIT ?"  # noqa: S608
            query = (
                f"SELECT data, created_at, updated_at FROM ({inner}) "  # noqa: S608
                f"ORDER BY {order_by}"  # noqa: S608
            )
            with connect() as con:
                rows = con.execute(query, (*params, last_n)).fetchall()
            return [model_from_row(model, row) for row in rows]

        query = f"SELECT data, created_at, updated_at FROM {table}"  # noqa: S608
        if where_sql:
            query += f" WHERE {where_sql}"  # noqa: S608
        query += f" ORDER BY {order_by}"  # noqa: S608
        with connect() as con:
            rows = con.execute(query, params).fetchall()
        return [model_from_row(model, row) for row in rows]

    def exists(self, table: str, record_id: str) -> bool:
        """Check whether a record exists without loading the JSON payload."""
        self._check(table)
        with connect() as con:
            row = con.execute(
                f"SELECT 1 FROM {table} WHERE id = ? LIMIT 1",  # noqa: S608
                (record_id,),
            ).fetchone()
        return row is not None
