"""Daily check-in application use cases.

This module owns the small lifecycle policy for check-ins: reads are routed
through the repository dependency, and writes normalize the row id so each
local date has at most one check-in.
"""

from app.domains.journal.contracts import (
    DailyCheckIn,
    DailyCheckInsResponse,
)
from app.domains.journal.dependencies import JournalRepository


def list_checkins(
    repo: JournalRepository,
    date: str | None = None,
) -> DailyCheckInsResponse:
    """List user check-ins, optionally restricted to one local date."""
    checkins = repo.list_checkins(date=date)
    return DailyCheckInsResponse(checkins=checkins)


def create_checkin(repo: JournalRepository, checkin: DailyCheckIn) -> DailyCheckIn:
    """Persist the check-in using the canonical date-derived id."""
    normalized = checkin.model_copy(update={"id": f"checkin-{checkin.date}"})
    repo.save_checkin(normalized)
    return normalized
