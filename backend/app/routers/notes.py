"""Notes HTTP routes."""

from fastapi import APIRouter, Query

from ..models import Note, NotesResponse
from ..services.notes import create_note, list_notes

router = APIRouter(prefix="/api/notes", tags=["notes"])


@router.get("", response_model=NotesResponse)
def get_notes(date: str | None = Query(None, description="Filter by date (YYYY-MM-DD)")):
    """Return notes."""
    return list_notes(date=date)


@router.post("", response_model=Note)
def post_note(note: Note):
    """Create a note."""
    return create_note(note)
