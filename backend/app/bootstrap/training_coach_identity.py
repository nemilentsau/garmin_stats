"""Cross-domain migration for durable training occurrence references in coach data."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Sequence
from typing import Any

from app.domains.training.domain.instance_identity import is_occurrence_id, occurrence_id

_COACH_OCCURRENCE_PATHS: dict[str, tuple[tuple[str, ...], ...]] = {
    "coach_reviews": (
        ("occurrence_key",),
        ("measurement_assessment", "occurrence_key"),
    ),
    "coach_review_revisions": (
        ("occurrence_key",),
        ("measurement_assessment", "occurrence_key"),
    ),
    "coach_messages": (("measurement_assessment", "occurrence_key"),),
    "coach_jobs": (("payload", "occurrence_key"),),
}


def _namespace(value: object, instance_id: str) -> object:
    if not isinstance(value, str) or is_occurrence_id(value):
        return value
    return occurrence_id(instance_id, value)


def _rewrite_path(payload: dict[str, Any], path: Sequence[str], instance_id: str) -> bool:
    owner: dict[str, Any] = payload
    for key in path[:-1]:
        nested = owner.get(key)
        if not isinstance(nested, dict):
            return False
        owner = nested
    leaf = path[-1]
    current = owner.get(leaf)
    rewritten = _namespace(current, instance_id)
    if rewritten == current:
        return False
    owner[leaf] = rewritten
    return True


def _path_value(payload: dict[str, Any], path: Sequence[str]) -> object:
    owner: object = payload
    for key in path:
        if not isinstance(owner, dict):
            return None
        owner = owner.get(key)
    return owner


def _is_legacy_occurrence(value: object) -> bool:
    return isinstance(value, str) and not is_occurrence_id(value)


def legacy_coach_occurrence_identity_migration_pending(
    connection: sqlite3.Connection,
) -> bool:
    """Return whether startup can namespace any legacy Coach reference."""
    tables = {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )
    }
    if "training_blocks" not in tables:
        return False
    active = connection.execute(
        "SELECT json_extract(data, '$.program_instance_id') AS instance_id "
        "FROM training_blocks WHERE json_extract(data, '$.status') = 'active' "
        "ORDER BY updated_at DESC LIMIT 1"
    ).fetchone()
    if active is None or not isinstance(active["instance_id"], str):
        return False

    if "coach_reviews" in tables:
        columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(coach_reviews)")
        }
        if "occurrence_key" in columns:
            keys = connection.execute(
                "SELECT occurrence_key FROM coach_reviews "
                "WHERE occurrence_key IS NOT NULL"
            ).fetchall()
            if any(_is_legacy_occurrence(row["occurrence_key"]) for row in keys):
                return True

    for table, paths in _COACH_OCCURRENCE_PATHS.items():
        if table not in tables:
            continue
        rows = connection.execute(f'SELECT data FROM "{table}"').fetchall()
        for row in rows:
            payload = json.loads(row["data"])
            if not isinstance(payload, dict):
                continue
            if any(_is_legacy_occurrence(_path_value(payload, path)) for path in paths):
                return True
    return False


def _rewrite_json_rows(
    connection: sqlite3.Connection,
    *,
    table: str,
    paths: Sequence[Sequence[str]],
    instance_id: str,
) -> None:
    rows = connection.execute(f'SELECT id, data FROM "{table}"').fetchall()
    for row in rows:
        payload: dict[str, Any] = json.loads(row["data"])
        changed = False
        for path in paths:
            changed = _rewrite_path(payload, path, instance_id) or changed
        if changed:
            connection.execute(
                f'UPDATE "{table}" SET data = ? WHERE id = ?',
                (json.dumps(payload, separators=(",", ":")), row["id"]),
            )


def migrate_legacy_coach_occurrence_identity(connection: sqlite3.Connection) -> None:
    """Namespace pre-identity coach references with the active imported program.

    The program identity migration and coach schema initialization run first.
    Existing versioned program references are left untouched, so repeated startup
    and historical reviews owned by an older program instance remain stable.
    """
    row = connection.execute(
        "SELECT json_extract(data, '$.program_instance_id') AS instance_id "
        "FROM training_blocks WHERE json_extract(data, '$.status') = 'active' "
        "ORDER BY updated_at DESC LIMIT 1"
    ).fetchone()
    if row is None or not isinstance(row["instance_id"], str):
        return
    instance_id = row["instance_id"]

    reviews = connection.execute(
        "SELECT id, occurrence_key FROM coach_reviews"
    ).fetchall()
    for review in reviews:
        rewritten = _namespace(review["occurrence_key"], instance_id)
        if rewritten != review["occurrence_key"]:
            connection.execute(
                "UPDATE coach_reviews SET occurrence_key = ? WHERE id = ?",
                (rewritten, review["id"]),
            )

    _rewrite_json_rows(
        connection,
        table="coach_reviews",
        paths=_COACH_OCCURRENCE_PATHS["coach_reviews"],
        instance_id=instance_id,
    )
    _rewrite_json_rows(
        connection,
        table="coach_review_revisions",
        paths=_COACH_OCCURRENCE_PATHS["coach_review_revisions"],
        instance_id=instance_id,
    )
    _rewrite_json_rows(
        connection,
        table="coach_messages",
        paths=_COACH_OCCURRENCE_PATHS["coach_messages"],
        instance_id=instance_id,
    )
    _rewrite_json_rows(
        connection,
        table="coach_jobs",
        paths=_COACH_OCCURRENCE_PATHS["coach_jobs"],
        instance_id=instance_id,
    )
