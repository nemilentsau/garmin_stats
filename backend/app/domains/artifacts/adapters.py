"""SQLite-backed artifact repository adapter."""

from __future__ import annotations

from app.domains.artifacts.contracts import AssistantArtifact
from app.infra.jsonstore import JsonStore
from app.infra.jsonstore import model_from_row as _model_from_row
from app.infra.sqlite import connect

_STORE = JsonStore({"assistant_artifacts"})


class SqliteArtifactRepository:
    """Repository adapter used by artifact application use cases."""

    def save_assistant_artifact(self, artifact: AssistantArtifact) -> None:
        _STORE.save(
            "assistant_artifacts",
            artifact.id,
            artifact.model_dump_json(),
            created_at=artifact.created_at,
            updated_at=artifact.updated_at,
        )

    def save_assistant_artifacts_batch(self, artifacts: list[AssistantArtifact]) -> None:
        with connect() as con, con:
            for artifact in artifacts:
                _STORE.save_in_connection(
                    con,
                    "assistant_artifacts",
                    artifact.id,
                    artifact.model_dump_json(),
                    created_at=artifact.created_at,
                    updated_at=artifact.updated_at,
                )

    def get_assistant_artifact(self, artifact_id: str) -> AssistantArtifact | None:
        return _STORE.load("assistant_artifacts", AssistantArtifact, artifact_id)

    def list_assistant_artifacts(
        self,
        *,
        kind: str | None = None,
        status: str | None = None,
    ) -> list[AssistantArtifact]:
        clauses: list[str] = []
        params: list[object] = []
        if kind is not None:
            clause, clause_params = _STORE.json_field_predicate("$.kind", (kind,))
            clauses.append(clause)
            params.extend(clause_params)
        if status is not None:
            clause, clause_params = _STORE.status_predicate((status,))
            clauses.append(clause)
            params.extend(clause_params)
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
        kind_sql, kind_params = _STORE.json_field_predicate("$.kind", (kind,))
        payload_id_sql, payload_id_params = _STORE.json_field_predicate(
            "$.payload_json.id",
            (payload_id,),
        )
        status_sql, status_params = _STORE.status_predicate(statuses)
        rows_query = (
            "SELECT data, created_at, updated_at FROM assistant_artifacts "
            f"WHERE {kind_sql} "
            f"AND {payload_id_sql} "
            f"AND {status_sql} "
            "ORDER BY created_at DESC LIMIT 1"
        )
        with connect() as con:
            row = con.execute(
                rows_query,
                (*kind_params, *payload_id_params, *status_params),
            ).fetchone()
        if row is None:
            return None
        return _model_from_row(AssistantArtifact, row)

    def get_max_artifact_revision(self, *, kind: str, id_prefix: str) -> int:
        kind_sql, kind_params = _STORE.json_field_predicate("$.kind", (kind,))
        query = (
            "SELECT MAX(CAST(SUBSTR(id, ?) AS INTEGER)) AS max_rev "
            "FROM assistant_artifacts "
            f"WHERE {kind_sql} AND id LIKE ? || '%'"
        )
        prefix_len = len(id_prefix) + 1
        with connect() as con:
            row = con.execute(query, (prefix_len, *kind_params, id_prefix)).fetchone()
        if row is None or row["max_rev"] is None:
            return 0
        return int(row["max_rev"])
