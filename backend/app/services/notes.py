"""Notes service."""

from ..infra.database import load_notes, save_note
from ..models import Note, NotesResponse


def list_notes(date: str | None = None) -> NotesResponse:
    """Return notes, optionally filtered by date."""
    notes = load_notes(date=date)
    return NotesResponse(notes=notes, total=len(notes))


def create_note(note: Note) -> Note:
    """Persist a note."""
    save_note(note)
    return note
