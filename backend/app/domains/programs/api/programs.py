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
from app.models import Program, ProgramsResponse, ProgramStatus, ProgramVersionsResponse

router = APIRouter(prefix="/api/programs", tags=["programs"])


@router.get("", response_model=ProgramsResponse)
def get_programs(status: ProgramStatus | None = None):
    """Return all programs, optionally filtered by status."""
    return list_programs(build_container().programs_repo, status=status)


@router.get("/{program_id}", response_model=Program)
def get_program_detail(program_id: str):
    """Return a single program with its full spec."""
    try:
        return get_program(build_container().programs_repo, program_id)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.post("/import", response_model=Program)
def post_import_program(spec: dict[str, object]):
    """Import a placeholder program spec JSON without activating child records."""
    try:
        return import_program(build_container().programs_repo, spec)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.put("/{program_id}/retire", response_model=Program)
def put_retire_program(program_id: str):
    """Set a program's status to retired, preserving all data."""
    try:
        return retire_program(build_container().programs_repo, program_id)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.put("/{program_id}/activate", response_model=Program)
def put_activate_program(program_id: str):
    """Reactivate a retired program."""
    try:
        return activate_program(build_container().programs_repo, program_id)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.get("/{program_id}/versions", response_model=ProgramVersionsResponse)
def get_versions(program_id: str):
    """Return version history for a program."""
    try:
        return get_program_versions(build_container().programs_repo, program_id)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
