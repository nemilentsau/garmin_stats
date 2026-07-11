"""SQLite-backed training repository adapter.

This module is the persistence boundary for imported v3 training artifacts
(bundles, block, signal registry, exercise library) and per-occurrence
capture logs. It owns the single-active-block/bundle invariant: `save_import`
retires every currently active block and bundle row inside one transaction
before writing the newly activated set, so a reader calling
`active_block()`/`bundles_for(...)` never observes more than one import
generation as active. The registry and exercise library have no lifecycle
history — each is a table that holds at most one row, replaced wholesale on
every import.
"""

from __future__ import annotations

import sqlite3

from pydantic import BaseModel

from app.domains.training.contracts import (
    StoredBlock,
    StoredBundle,
    StoredLibrary,
    StoredRegistry,
    TrainingCardLog,
)
from app.infra.jsonstore import JsonStore, model_from_row
from app.infra.sqlite import connect

_STORE = JsonStore({
    "training_bundles",
    "training_blocks",
    "training_registry",
    "training_exercise_library",
    "training_card_logs",
})


def _retire_active[StoredT: BaseModel](
    con: sqlite3.Connection, table: str, model_cls: type[StoredT]
) -> None:
    """Rewrite every currently active row in `table` to `status="retired"`.

    Reads and writes share the caller's transaction (`con`), so this only
    ever sees rows committed before the transaction began — correct for the
    single-writer, retire-then-activate flow `save_import` runs it in. Uses
    the row's own `id` column (not the parsed model) as the write key, so it
    stays generic over any stored record type that carries a `status` field.
    """
    where_sql, params = _STORE.status_predicate(("active",))
    rows = con.execute(
        f"SELECT id, data, created_at, updated_at FROM {table} WHERE {where_sql}",  # noqa: S608
        params,
    ).fetchall()
    for row in rows:
        record = model_from_row(model_cls, row)
        retired = record.model_copy(update={"status": "retired"})
        _STORE.save_in_connection(con, table, row["id"], retired.model_dump_json())


class SqliteTrainingRepository:
    """Repository adapter for imported v3 training artifacts and capture logs."""

    def active_block(self) -> StoredBlock | None:
        """Return the currently active block, or None if nothing is imported."""
        where_sql, params = _STORE.status_predicate(("active",))
        rows = _STORE.load_many(
            "training_blocks", StoredBlock, where_sql=where_sql, params=params
        )
        return rows[0] if rows else None

    def bundles_for(self, bundle_ids: str | list[str]) -> list[StoredBundle]:
        """Load active bundles by id (accepts one id or a list of ids)."""
        ids = [bundle_ids] if isinstance(bundle_ids, str) else list(bundle_ids)
        if not ids:
            return []
        placeholders = ", ".join("?" for _ in ids)
        where_sql = f"id IN ({placeholders}) AND json_extract(data, '$.status') = 'active'"
        return _STORE.load_many(
            "training_bundles",
            StoredBundle,
            where_sql=where_sql,
            params=tuple(ids),
            order_by="id",
        )

    def registry(self) -> StoredRegistry | None:
        """Load the single imported signal registry, or None if never imported.

        The registry artifact has no id of its own, so this loads whichever
        row is present rather than assuming a fixed id — the table holds at
        most one row by construction (`application/imports.py` always writes
        the same bookkeeping id).
        """
        rows = _STORE.load_many("training_registry", StoredRegistry)
        return rows[0] if rows else None

    def library(self) -> StoredLibrary | None:
        """Load the single imported exercise library, or None if never imported."""
        rows = _STORE.load_many("training_exercise_library", StoredLibrary)
        return rows[0] if rows else None

    def save_import(
        self,
        *,
        block: StoredBlock,
        bundles: list[StoredBundle],
        registry: StoredRegistry,
        library: StoredLibrary,
    ) -> None:
        """Retire the previously active block/bundles and persist the new active set.

        Runs as one transaction: every currently active block and bundle row
        is rewritten to `status="retired"` first, then the new block,
        bundles, registry, and library rows are written active. When the new
        import reuses a retired id, the later write supersedes the retired
        one (both target the same primary key), so re-importing an identical
        set replaces rows in place instead of accumulating duplicates.
        """
        with connect() as con, con:
            _retire_active(con, "training_blocks", StoredBlock)
            _retire_active(con, "training_bundles", StoredBundle)

            _STORE.save_in_connection(con, "training_blocks", block.id, block.model_dump_json())
            for bundle in bundles:
                _STORE.save_in_connection(
                    con, "training_bundles", bundle.id, bundle.model_dump_json()
                )
            _STORE.save_in_connection(
                con, "training_registry", registry.id, registry.model_dump_json()
            )
            _STORE.save_in_connection(
                con, "training_exercise_library", library.id, library.model_dump_json()
            )

    def card_log(self, date: str, occurrence_key: str) -> TrainingCardLog | None:
        """Load one capture log by its `date:occurrence_key` composite id."""
        return _STORE.load("training_card_logs", TrainingCardLog, f"{date}:{occurrence_key}")

    def card_logs_for(self, date: str) -> list[TrainingCardLog]:
        """Load every capture log recorded for one date."""
        return _STORE.load_many(
            "training_card_logs",
            TrainingCardLog,
            where_sql="json_extract(data, '$.date') = ?",
            params=(date,),
            order_by="id",
        )

    def card_logs_before(self, date: str) -> list[TrainingCardLog]:
        """Load every capture log recorded strictly before one date."""
        return _STORE.load_many(
            "training_card_logs",
            TrainingCardLog,
            where_sql="json_extract(data, '$.date') < ?",
            params=(date,),
            order_by="id",
        )

    def upsert_card_log(self, log: TrainingCardLog) -> None:
        """Persist one capture log, replacing any existing row with the same id."""
        _STORE.save("training_card_logs", log.id, log.model_dump_json())
