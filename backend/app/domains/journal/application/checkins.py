"""Daily check-in use cases."""

from app.domains.journal.contracts import (
    DailyCheckIn,
    DailyCheckInsResponse,
)
from app.domains.journal.dependencies import JournalRepository


def list_checkins(
    repo: JournalRepository,
    date: str | None = None,
) -> DailyCheckInsResponse:
    """Return daily check-ins, optionally filtered by date."""
    checkins = repo.list_checkins(date=date)
    return DailyCheckInsResponse(checkins=checkins)


def create_checkin(repo: JournalRepository, checkin: DailyCheckIn) -> DailyCheckIn:
    """Persist a daily check-in."""
    normalized = checkin.model_copy(update={"id": f"checkin-{checkin.date}"})
    repo.save_checkin(normalized)
    return normalized
