"""SQLite-backed artifact repository adapter.

This module is the persistence boundary for staged assistant artifacts. It owns
assistant artifact JSON-store access and keeps artifact CRUD out of the global
database helper module.
"""

from __future__ import annotations

from app.domains.artifacts.contracts import AssistantArtifact
from app.infra.jsonstore import JsonStore
from app.infra.jsonstore import model_from_row as _model_from_row
from app.infra.sqlite import connect
from app.utils.timeutil import now_iso

_STORE = JsonStore({"assistant_artifacts"})


class SqliteArtifactRepository:
    """Repository adapter used by artifact application use cases."""

    def save_assistant_artifact(self, artifact: AssistantArtifact) -> None:
        """Insert or replace one staged assistant artifact."""
        _STORE.save(
            "assistant_artifacts",
            artifact.id,
            artifact.model_dump_json(),
            created_at=artifact.created_at,
            updated_at=artifact.updated_at,
        )

    def save_assistant_artifacts_batch(self, artifacts: list[AssistantArtifact]) -> None:
        """Persist a bundle import in one transaction."""
        with connect() as con, con:
            for artifact in artifacts:
                con.execute(
                    (
                        "INSERT OR REPLACE INTO assistant_artifacts "
                        "(id, data, created_at, updated_at) VALUES (?, ?, ?, ?)"
                    ),
                    (
                        artifact.id,
                        artifact.model_dump_json(),
                        artifact.created_at or now_iso(),
                        artifact.updated_at or now_iso(),
                    ),
                )

    def get_assistant_artifact(self, artifact_id: str) -> AssistantArtifact | None:
        """Load one artifact by stable artifact id."""
        return _STORE.load("assistant_artifacts", AssistantArtifact, artifact_id)

    def list_assistant_artifacts(
        self,
        *,
        kind: str | None = None,
        status: str | None = None,
    ) -> list[AssistantArtifact]:
        """List artifacts newest-first, optionally filtered by kind and status."""
        clauses: list[str] = []
        params: list[object] = []
        if kind is not None:
            clauses.append("json_extract(data, '$.kind') = ?")
            params.append(kind)
        if status is not None:
            clauses.append("json_extract(data, '$.status') = ?")
            params.append(status)
        return _STORE.load_many(
            "assistant_artifacts",
            AssistantArtifact,
            where_sql=" AND ".join(clauses),
            params=tuple(params),
            order_by="created_at DESC, id",
        )

    def get_assistant_artifact_by_payload_id(
        self,
        kind: str,
        payload_id: str,
        statuses: tuple[str, ...],
    ) -> AssistantArtifact | None:
        """Load the newest artifact whose embedded payload owns ``payload_id``."""
        if not statuses:
            return None
        placeholders = ", ".join("?" for _ in statuses)
        rows_query = (
            "SELECT data, created_at, updated_at FROM assistant_artifacts "
            "WHERE json_extract(data, '$.kind') = ? "
            "AND json_extract(data, '$.payload_json.id') = ? "
            f"AND json_extract(data, '$.status') IN ({placeholders}) "
            "ORDER BY created_at DESC LIMIT 1"
        )
        with connect() as con:
            row = con.execute(rows_query, (kind, payload_id, *statuses)).fetchone()
        if row is None:
            return None
        return _model_from_row(AssistantArtifact, row)

    def get_max_artifact_revision(self, *, kind: str, id_prefix: str) -> int:
        """Return the highest bundle revision stored for an artifact id prefix."""
        query = (
            "SELECT MAX(CAST(SUBSTR(id, ?) AS INTEGER)) AS max_rev "
            "FROM assistant_artifacts "
            "WHERE json_extract(data, '$.kind') = ? AND id LIKE ? || '%'"
        )
        prefix_len = len(id_prefix) + 1
        with connect() as con:
            row = con.execute(query, (prefix_len, kind, id_prefix)).fetchone()
        if row is None or row["max_rev"] is None:
            return 0
        return int(row["max_rev"])
