"""Container-wired wrappers around routine application services for tests."""

from app.bootstrap.container import build_container
from app.domains.routines.application.schedule_window import (
    get_schedule_window as _get_schedule_window,
)
from app.domains.routines.application.today import (
    get_today as _get_today,
)
from app.domains.routines.application.today import (
    upsert_today_card_log as _upsert_today_card_log,
)
from app.models import TodayCardLogUpdateRequest


def get_schedule_window(start_date: str, duration_days: int = 14):
    return _get_schedule_window(
        build_container().routines_repo,
        start_date=start_date,
        duration_days=duration_days,
    )


def get_today(date: str):
    return _get_today(build_container().routines_repo, date=date)


def upsert_today_card_log(
    date: str,
    occurrence_key: str,
    request: TodayCardLogUpdateRequest,
):
    container = build_container()
    return _upsert_today_card_log(
        container.routines_repo,
        date=date,
        occurrence_key=occurrence_key,
        request=request,
        observer=container.experiment_exposure_sync,
    )
