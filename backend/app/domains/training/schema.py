"""SQLite schema for imported v3 training artifacts and capture logs.

Training owns five jsonstore tables: the imported bundle/block/registry/
library artifact wrappers (verbatim uploads plus lifecycle bookkeeping) and
the per-occurrence capture log. All five use the shared JSON-record column
shape (`id`, `data`, `created_at`, `updated_at`) with no bespoke columns or
indexes — lookups go through jsonstore's id/status/json-field predicates, and
read volume is small (one active block's worth of bundles/cards at a time),
so a dedicated index isn't worth the schema complexity yet.
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from app.domains.training.domain.instance_identity import card_log_id, program_instance_id
from app.infra.jsonstore import JSON_RECORD_COLUMNS_SQL

_SCHEMA = f"""
CREATE TABLE IF NOT EXISTS training_bundles ({JSON_RECORD_COLUMNS_SQL});
CREATE TABLE IF NOT EXISTS training_blocks ({JSON_RECORD_COLUMNS_SQL});
CREATE TABLE IF NOT EXISTS training_registry ({JSON_RECORD_COLUMNS_SQL});
CREATE TABLE IF NOT EXISTS training_exercise_library ({JSON_RECORD_COLUMNS_SQL});
CREATE TABLE IF NOT EXISTS training_card_logs ({JSON_RECORD_COLUMNS_SQL});
"""


def init_training_schema(con: sqlite3.Connection) -> None:
    """Create training-owned tables and namespace pre-identity capture logs."""
    con.executescript(_SCHEMA)
    _migrate_program_instance_identity(con)


def _migrate_program_instance_identity(con: sqlite3.Connection) -> None:
    """Assign the active legacy import and its logs one deterministic owner.

    Old databases have no import-generation identity. The only honest mapping
    available is their active complete artifact set, so startup derives that
    identity and rekeys every still-unnamespaced log in the same transaction.
    A destination-key collision raises instead of overwriting either row.
    """
    block_row = con.execute(
        "SELECT id, data FROM training_blocks "
        "WHERE json_extract(data, '$.status') = 'active' "
        "AND json_extract(data, '$.program_instance_id') IS NULL"
    ).fetchone()
    if block_row is None:
        return

    block_data: dict[str, Any] = json.loads(block_row["data"])
    block_artifact = block_data.get("artifact")
    if not isinstance(block_artifact, dict):
        return
    bundle_ids = block_artifact.get("bundle_ids")
    if not isinstance(bundle_ids, list) or not all(isinstance(value, str) for value in bundle_ids):
        return

    bundle_rows = con.execute(
        "SELECT id, data FROM training_bundles "
        "WHERE json_extract(data, '$.status') = 'active'"
    ).fetchall()
    bundle_artifacts = {
        row["id"]: json.loads(row["data"]).get("artifact") for row in bundle_rows
    }
    if any(not isinstance(bundle_artifacts.get(bundle_id), dict) for bundle_id in bundle_ids):
        return

    registry_row = con.execute("SELECT data FROM training_registry LIMIT 1").fetchone()
    library_row = con.execute(
        "SELECT data FROM training_exercise_library LIMIT 1"
    ).fetchone()
    if registry_row is None or library_row is None:
        return
    registry = json.loads(registry_row["data"]).get("artifact")
    library = json.loads(library_row["data"]).get("artifact")
    if not isinstance(registry, dict) or not isinstance(library, dict):
        return

    authored_start = block_artifact.get("window", {}).get("start")
    schedule_start = block_data.get("schedule_start") or authored_start
    if not isinstance(schedule_start, str):
        return
    instance_id = program_instance_id(
        block=block_artifact,
        bundles=[bundle_artifacts[bundle_id] for bundle_id in bundle_ids],
        registry=registry,
        library=library,
        schedule_start=schedule_start,
    )
    block_data["program_instance_id"] = instance_id
    con.execute(
        "UPDATE training_blocks SET data = ? WHERE id = ?",
        (json.dumps(block_data, separators=(",", ":")), block_row["id"]),
    )

    legacy_logs = con.execute(
        "SELECT id, data, created_at, updated_at FROM training_card_logs "
        "WHERE json_extract(data, '$.program_instance_id') IS NULL"
    ).fetchall()
    for row in legacy_logs:
        payload: dict[str, Any] = json.loads(row["data"])
        log_date = payload.get("date")
        occurrence_key = payload.get("occurrence_key")
        if not isinstance(log_date, str) or not isinstance(occurrence_key, str):
            continue
        new_id = card_log_id(instance_id, log_date, occurrence_key)
        payload["id"] = new_id
        payload["program_instance_id"] = instance_id
        con.execute(
            "INSERT INTO training_card_logs (id, data, created_at, updated_at) "
            "VALUES (?, ?, ?, ?)",
            (
                new_id,
                json.dumps(payload, separators=(",", ":")),
                row["created_at"],
                row["updated_at"],
            ),
        )
        con.execute("DELETE FROM training_card_logs WHERE id = ?", (row["id"],))
