"""Journal HTTP routes."""

from fastapi import APIRouter, Query

from app.bootstrap.container import build_container
from app.domains.journal.application.checkins import create_checkin, list_checkins
from app.domains.journal.application.notes import create_note, list_notes
from app.domains.journal.contracts import (
    DailyCheckIn,
    DailyCheckInsResponse,
    Note,
    NotesResponse,
)

checkins_router = APIRouter(prefix="/api/checkins", tags=["checkins"])
notes_router = APIRouter(prefix="/api/notes", tags=["notes"])


@checkins_router.get("", response_model=DailyCheckInsResponse)
def get_checkins(date: str | None = Query(None, description="Filter by date (YYYY-MM-DD)")):
    """Return daily check-ins."""
    return list_checkins(build_container().journal_repo, date=date)


@checkins_router.post("", response_model=DailyCheckIn)
def post_checkin(checkin: DailyCheckIn):
    """Create or replace a daily check-in."""
    return create_checkin(build_container().journal_repo, checkin)


@notes_router.get("", response_model=NotesResponse)
def get_notes(date: str | None = Query(None, description="Filter by date (YYYY-MM-DD)")):
    """Return notes."""
    return list_notes(build_container().journal_repo, date=date)


@notes_router.post("", response_model=Note)
def post_note(note: Note):
    """Create a note."""
    return create_note(build_container().journal_repo, note)
