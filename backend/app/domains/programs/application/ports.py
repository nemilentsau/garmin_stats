"""Repository contracts for program use cases."""

from __future__ import annotations

from typing import Protocol

from app.models import Experiment, Program, ProgramStatus, ProgramVersion, Routine


class ProgramRepository(Protocol):
    def get_program(self, program_id: str) -> Program | None: ...

    def list_programs(self, *, status: ProgramStatus | None = None) -> list[Program]: ...

    def save_program(self, program: Program) -> None: ...

    def list_program_versions(self, program_id: str) -> list[ProgramVersion]: ...

    def replace_program_import(
        self,
        *,
        program: Program,
        previous_version: ProgramVersion | None,
        routines: list[Routine],
        experiments: list[Experiment],
        stale_routine_ids: set[str],
        stale_experiment_ids: set[str],
    ) -> None: ...
