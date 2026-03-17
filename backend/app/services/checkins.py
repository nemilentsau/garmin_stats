"""Daily check-in service."""

from ..infra.database import load_daily_checkins, save_daily_checkin
from ..models import DailyCheckIn, DailyCheckInsResponse


def list_checkins(date: str | None = None) -> DailyCheckInsResponse:
    """Return daily check-ins, optionally filtered by date."""
    checkins = load_daily_checkins(date=date)
    return DailyCheckInsResponse(checkins=checkins)


def create_checkin(checkin: DailyCheckIn) -> DailyCheckIn:
    """Persist a daily check-in."""
    normalized = checkin.model_copy(update={"id": f"checkin-{checkin.date}"})
    save_daily_checkin(normalized)
    return normalized
