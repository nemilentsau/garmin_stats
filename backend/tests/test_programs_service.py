"""Tests for program import service behavior."""

from app.services.experiments import list_experiments
from app.services.programs import import_program
from app.services.routines import list_routines


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

        routines = list_routines().routines
        experiments = list_experiments().experiments

        assert [routine.id for routine in routines] == ["program-1:protocol-1"]
        assert routines[0].name == "Walk updated"
        assert [experiment.id for experiment in experiments] == ["program-1:experiment-1"]
        assert experiments[0].name == "Walk test updated"
