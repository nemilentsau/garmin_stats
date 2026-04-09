"""Compatibility wrapper for today routes."""

from app.domains.routines.api.today import router
from app.services.today import get_card_log_range, get_today, upsert_today_card_log


def get_today_view(date: str):
    return get_today(date)


def get_today_card_logs(start_date: str, end_date: str):
    return get_card_log_range(start_date, end_date)


def get_card_logs_range(start_date: str, end_date: str):
    return get_today_card_logs(start_date, end_date)


def put_today_card_log(date: str, occurrence_key: str, request):
    return upsert_today_card_log(date, occurrence_key, request)

__all__ = [
    "router",
    "get_card_log_range",
    "get_today",
    "upsert_today_card_log",
    "get_today_view",
    "get_today_card_logs",
    "get_card_logs_range",
    "put_today_card_log",
]
