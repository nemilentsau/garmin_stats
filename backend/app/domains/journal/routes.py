"""HTTP routes for check-ins and notes.

Routes keep FastAPI request metadata at the journal boundary, resolve the app
container, and delegate persistence policy to application use cases. They do
not reach into SQLite or apply journal lifecycle decisions directly.
"""

from datetime import date as Date
from typing import Annotated

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
_OptionalDate = Annotated[Date | None, Query(description="Filter by date (YYYY-MM-DD)")]


@checkins_router.get("", response_model=DailyCheckInsResponse)
def get_checkins(
    date: _OptionalDate = None,
):
    """Return daily check-ins, optionally restricted to one local date."""
    return list_checkins(
        build_container().journal_repo,
        date=date.isoformat() if date is not None else None,
    )


@checkins_router.post("", response_model=DailyCheckIn)
def post_checkin(checkin: DailyCheckIn):
    """Create or replace the check-in for its local date."""
    return create_checkin(build_container().journal_repo, checkin)


@notes_router.get("", response_model=NotesResponse)
def get_notes(date: _OptionalDate = None):
    """Return journal notes, optionally restricted to one local date."""
    return list_notes(
        build_container().journal_repo,
        date=date.isoformat() if date is not None else None,
    )


@notes_router.post("", response_model=Note)
def post_note(note: Note):
    """Persist one user-authored journal note."""
    return create_note(build_container().journal_repo, note)
