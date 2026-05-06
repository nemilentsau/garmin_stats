"""Program spec HTTP routes."""

from fastapi import APIRouter, HTTPException

from app.bootstrap.container import build_container
from app.domains.programs.application.programs import (
    activate_program,
    get_program,
    get_program_versions,
    import_program,
    list_programs,
    retire_program,
)
from app.models import Program, ProgramsResponse, ProgramVersionsResponse

router = APIRouter(prefix="/api/programs", tags=["programs"])


@router.get("", response_model=ProgramsResponse)
def get_programs(status: str | None = None):
    """Return all programs, optionally filtered by status."""
    return list_programs(build_container().programs_repo, status=status)


@router.get("/{program_id}", response_model=Program)
def get_program_detail(program_id: str):
    """Return a single program with its full spec."""
    return get_program(build_container().programs_repo, program_id)


@router.post("/import", response_model=Program)
def post_import_program(spec: dict[str, object]):
    """Import a program spec JSON. Creates/updates program, routines, and experiments."""
    if "program" not in spec:
        raise HTTPException(status_code=400, detail="Missing 'program' key in spec")
    program_info = spec["program"]
    if not isinstance(program_info, dict) or not program_info.get("id") or not program_info.get(
        "name"
    ):
        raise HTTPException(
            status_code=400,
            detail="Program spec must have 'program.id' and 'program.name'",
        )
    return import_program(build_container().programs_repo, spec)


@router.put("/{program_id}/retire", response_model=Program)
def put_retire_program(program_id: str):
    """Set a program's status to retired, preserving all data."""
    return retire_program(build_container().programs_repo, program_id)


@router.put("/{program_id}/activate", response_model=Program)
def put_activate_program(program_id: str):
    """Reactivate a retired program."""
    return activate_program(build_container().programs_repo, program_id)


@router.get("/{program_id}/versions", response_model=ProgramVersionsResponse)
def get_versions(program_id: str):
    """Return version history for a program."""
    return get_program_versions(build_container().programs_repo, program_id)
