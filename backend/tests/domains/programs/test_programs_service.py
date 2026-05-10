"""Tests for program import service behavior."""


from app.domains.experiments.adapters import SqliteExperimentRepository
from app.domains.experiments.application.management import list_experiments
from app.domains.programs.adapters import SqliteProgramRepository
from app.domains.programs.application.programs import (
    get_program,
    get_program_versions,
    import_program,
    list_programs,
)


def _program_spec(
    *,
    version: int,
    protocols: list[dict[str, object]],
    experiments: list[dict[str, object]],
) -> dict[str, object]:
    return {
        "program": {
            "id": "program-1",
            "name": "Program One",
            "version": version,
        },
        "protocols": protocols,
        "experiments": experiments,
    }


class TestImportProgram:
    def test_import_stores_program_spec_without_creating_legacy_children(self):
        repo = SqliteProgramRepository()

        imported = import_program(
            repo,
            _program_spec(
                version=1,
                protocols=[
                    {"id": "protocol-1", "name": "Walk"},
                    {"id": "protocol-2"},
                ],
                experiments=[
                    {"id": "experiment-1", "name": "Walk test"},
                ],
            )
        )

        assert imported.id == "program-1"
        assert list_programs(repo).programs == [imported]
        assert list_experiments(SqliteExperimentRepository()).experiments == []

    def test_reimport_versions_program_without_touching_legacy_children(self):
        repo = SqliteProgramRepository()

        import_program(
            repo,
            _program_spec(
                version=1,
                protocols=[
                    {"id": "protocol-1", "name": "Walk"},
                    {"id": "protocol-2", "name": "Lift"},
                ],
                experiments=[
                    {"id": "experiment-1", "name": "Walk test"},
                    {"id": "experiment-2", "name": "Lift test"},
                ],
            )
        )

        import_program(
            repo,
            _program_spec(
                version=2,
                protocols=[
                    {"id": "protocol-1", "name": "Walk updated"},
                ],
                experiments=[
                    {"id": "experiment-1", "name": "Walk test updated"},
                ],
            )
        )

        program = get_program(repo, "program-1")
        versions = get_program_versions(repo, "program-1").versions

        assert program.version == 2
        assert versions[0].version == 1
        assert list_experiments(SqliteExperimentRepository()).experiments == []
