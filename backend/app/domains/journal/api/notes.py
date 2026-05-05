"""Notes HTTP routes."""

from fastapi import APIRouter, Query

from app.domains.journal.application.notes import create_note, list_notes
from app.models import Note, NotesResponse

router = APIRouter(prefix="/api/notes", tags=["notes"])


@router.get("", response_model=NotesResponse)
def get_notes(date: str | None = Query(None, description="Filter by date (YYYY-MM-DD)")):
    """Return notes."""
    return list_notes(date=date)


@router.post("", response_model=Note)
def post_note(note: Note):
    """Create a note."""
    return create_note(note)
