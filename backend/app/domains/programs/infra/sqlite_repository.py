"""SQLite repository adapter for program use cases."""

from __future__ import annotations

from app.infra.database import (
    load_program,
    load_program_versions,
    load_programs,
    save_program,
    save_program_import,
)
from app.models import Program, ProgramStatus, ProgramVersion


class SqliteProgramRepository:
    def get_program(self, program_id: str) -> Program | None:
        return load_program(program_id)

    def list_programs(self, *, status: ProgramStatus | None = None) -> list[Program]:
        return load_programs(status=status)

    def save_program(self, program: Program) -> None:
        save_program(program)

    def list_program_versions(self, program_id: str) -> list[ProgramVersion]:
        return load_program_versions(program_id)

    def save_program_import(
        self,
        *,
        program: Program,
        previous_version: ProgramVersion | None,
    ) -> None:
        save_program_import(
            program=program,
            previous_version=previous_version,
        )
