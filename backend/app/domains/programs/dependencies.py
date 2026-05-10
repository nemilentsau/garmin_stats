"""Dependencies consumed by program application use cases.

Program workflows persist imported specs, lifecycle state, and version history
through this protocol. Concrete SQLite details belong in the adapter layer.
"""

from __future__ import annotations

from typing import Protocol

from app.domains.programs.contracts import (
    Program,
    ProgramStatus,
    ProgramVersion,
)


class ProgramRepository(Protocol):
    """Persistence dependency for program import and lifecycle workflows."""

    def get_program(self, program_id: str) -> Program | None: ...

    def list_programs(self, *, status: ProgramStatus | None = None) -> list[Program]: ...

    def save_program(self, program: Program) -> None: ...

    def list_program_versions(self, program_id: str) -> list[ProgramVersion]: ...

    def save_program_import(
        self,
        *,
        program: Program,
        previous_version: ProgramVersion | None,
    ) -> None: ...
