"""SQLite repository adapter for program use cases."""

from __future__ import annotations

from app.infra.database import (
    load_program,
    load_program_versions,
    load_programs,
    replace_program_import,
    save_program,
)
from app.models import Experiment, Program, ProgramVersion, Routine


class SqliteProgramRepository:
    def get_program(self, program_id: str) -> Program | None:
        return load_program(program_id)

    def list_programs(self, *, status: str | None = None) -> list[Program]:
        return load_programs(status=status)

    def save_program(self, program: Program) -> None:
        save_program(program)

    def list_program_versions(self, program_id: str) -> list[ProgramVersion]:
        return load_program_versions(program_id)

    def replace_program_import(
        self,
        *,
        program: Program,
        previous_version: ProgramVersion | None,
        routines: list[Routine],
        experiments: list[Experiment],
        stale_routine_ids: set[str],
        stale_experiment_ids: set[str],
    ) -> None:
        replace_program_import(
            program=program,
            previous_version=previous_version,
            routines=routines,
            experiments=experiments,
            stale_routine_ids=stale_routine_ids,
            stale_experiment_ids=stale_experiment_ids,
        )
