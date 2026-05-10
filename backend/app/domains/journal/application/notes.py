"""Journal note application use cases.

Notes are append-style user context attached to local dates. The application
layer only shapes responses and delegates storage to the injected repository.
"""

from app.domains.journal.contracts import (
    Note,
    NotesResponse,
)
from app.domains.journal.dependencies import JournalRepository


def list_notes(
    repo: JournalRepository,
    date: str | None = None,
) -> NotesResponse:
    """List journal notes, optionally restricted to one local date."""
    notes = repo.list_notes(date=date)
    return NotesResponse(notes=notes)


def create_note(repo: JournalRepository, note: Note) -> Note:
    """Persist one note without altering its caller-provided identity."""
    repo.save_note(note)
    return note
