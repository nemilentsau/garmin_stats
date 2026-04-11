"""Compatibility wrapper for routines today use cases."""

from app.bootstrap.container import build_container
from app.domains.routines.application.today import (
    get_card_log_range as _get_card_log_range,
)
from app.domains.routines.application.today import (
    get_today as _get_today,
)
from app.domains.routines.application.today import (
    upsert_today_card_log as _upsert_today_card_log,
)


def get_card_log_range(start_date: str, end_date: str):
    return _get_card_log_range(
        build_container().routines_repo, start_date=start_date, end_date=end_date
    )


def get_today(date: str):
    return _get_today(build_container().routines_repo, date=date)


def upsert_today_card_log(date: str, occurrence_key: str, request):
    container = build_container()
    return _upsert_today_card_log(
        container.routines_repo,
        date=date,
        occurrence_key=occurrence_key,
        request=request,
        observer=container.experiment_exposure_sync,
    )
