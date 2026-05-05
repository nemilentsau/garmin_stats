"""Tests for program import service behavior."""

import pytest

from app.domains.experiments.application.management import list_experiments
from app.domains.experiments.infra.sqlite_repository import SqliteExperimentRepository
from app.infra.database import load_routines
from app.services.programs import import_program, list_programs


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
    def test_invalid_protocol_rolls_back_entire_import(self):
        with pytest.raises(KeyError, match="name"):
            import_program(
                _program_spec(
                    version=1,
                    protocols=[
                        {"id": "protocol-1", "name": "Walk"},
                        {"id": "protocol-2"},
                    ],
                    experiments=[],
                )
            )

        assert list_programs().programs == []
        assert load_routines() == []
        assert list_experiments(SqliteExperimentRepository()).experiments == []

    def test_reimport_removes_deleted_protocols_and_experiments(self):
        import_program(
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

        routines = load_routines()
        experiments = list_experiments(SqliteExperimentRepository()).experiments

        assert [routine.id for routine in routines] == ["program-1:protocol-1"]
        assert routines[0].name == "Walk updated"
        assert [e.experiment.id for e in experiments] == ["program-1:experiment-1"]
        assert experiments[0].experiment.name == "Walk test updated"
