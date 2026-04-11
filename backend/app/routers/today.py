"""Compatibility wrapper for today routes."""

from app.domains.routines.api.today import router
from app.services.today import get_today, upsert_today_card_log

__all__ = [
    "router",
    "get_today",
    "upsert_today_card_log",
]
