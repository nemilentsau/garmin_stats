"""Cross-domain migration for durable training occurrence references in coach data."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Sequence
from typing import Any

from app.domains.training.domain.instance_identity import is_occurrence_id, occurrence_id


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
        paths=(("occurrence_key",), ("measurement_assessment", "occurrence_key")),
        instance_id=instance_id,
    )
    _rewrite_json_rows(
        connection,
        table="coach_review_revisions",
        paths=(("occurrence_key",), ("measurement_assessment", "occurrence_key")),
        instance_id=instance_id,
    )
    _rewrite_json_rows(
        connection,
        table="coach_messages",
        paths=(("measurement_assessment", "occurrence_key"),),
        instance_id=instance_id,
    )
    _rewrite_json_rows(
        connection,
        table="coach_jobs",
        paths=(("payload", "occurrence_key"),),
        instance_id=instance_id,
    )
