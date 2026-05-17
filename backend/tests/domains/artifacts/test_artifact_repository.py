"""Tests for artifact SQLite repository queries."""

from app.domains.artifacts.adapters import SqliteArtifactRepository
from app.domains.artifacts.contracts import AssistantArtifact
from app.utils.timeutil import now_iso


class TestArtifactRepository:
    def test_load_artifact_by_payload_id_finds_matching_artifact(self):
        repo = SqliteArtifactRepository()
        now = now_iso()
        artifact = AssistantArtifact(
            id="bundle:test-bundle:card_template:card-1:r1",
            kind="card_template",
            schema_version=1,
            status="validated",
            payload_json={"id": "card-1", "name": "Test"},
            created_at=now,
            updated_at=now,
        )
        repo.save_assistant_artifact(artifact)

        result = repo.get_assistant_artifact_by_payload_id(
            "card_template", "card-1", ("validated", "activated"),
        )

        assert result is not None
        assert result.id == artifact.id

    def test_load_artifact_by_payload_id_empty_statuses_returns_none(self):
        repo = SqliteArtifactRepository()
        now = now_iso()
        artifact = AssistantArtifact(
            id="bundle:test-bundle:card_template:card-1:r1",
            kind="card_template",
            schema_version=1,
            status="validated",
            payload_json={"id": "card-1", "name": "Test"},
            created_at=now,
            updated_at=now,
        )
        repo.save_assistant_artifact(artifact)

        result = repo.get_assistant_artifact_by_payload_id("card_template", "card-1", ())

        assert result is None

    def test_load_max_artifact_revision_returns_highest(self):
        repo = SqliteArtifactRepository()
        now = now_iso()
        prefix = "bundle:test:card_template:card-1:r"
        for rev in [1, 2, 5]:
            repo.save_assistant_artifact(
                AssistantArtifact(
                    id=f"{prefix}{rev}",
                    kind="card_template",
                    schema_version=1,
                    status="validated",
                    payload_json={"id": "card-1"},
                    created_at=now,
                    updated_at=now,
                )
            )

        result = repo.get_max_artifact_revision(kind="card_template", id_prefix=prefix)

        assert result == 5
