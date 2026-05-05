"""Note use cases."""

from app.models import Note, NotesResponse

from .ports import JournalRepository


def list_notes(
    repo: JournalRepository,
    date: str | None = None,
) -> NotesResponse:
    """Return notes, optionally filtered by date."""
    notes = repo.list_notes(date=date)
    return NotesResponse(notes=notes)


def create_note(repo: JournalRepository, note: Note) -> Note:
    """Persist a note."""
    repo.save_note(note)
    return note
