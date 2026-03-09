"""Windowed period summary: pre-compute PeriodSummary for 3M, 6M, and All."""

from datetime import date as date_type
from datetime import timedelta

from ..infra import cache
from ..infra.database import load_hrv, load_skin_temp, load_sleep, load_wellness
from ..models import (
    DayData,
    PeriodSummary,
)
from ..stats import compute_period_summary
from ._windows import WINDOW_DAYS

WINDOWED_PERIOD = "windowed_period"


def load_windowed_period_summary() -> dict[str, PeriodSummary]:
    """Load pre-computed period summaries for each time window (cached)."""
    return cache.cached(WINDOWED_PERIOD, _compute)


def _compute() -> dict[str, PeriodSummary]:
    day_data = _reconstruct_day_data()
    today = date_type.today()
    windows: dict[str, PeriodSummary] = {}
    for label, days in WINDOW_DAYS.items():
        if days is None:
            subset = day_data
        else:
            cutoff = (today - timedelta(days=days)).isoformat()
            subset = [d for d in day_data if d.date >= cutoff]
        windows[label] = compute_period_summary(subset)
    return windows


def _reconstruct_day_data() -> list[DayData]:
    """Join the 4 per-day DB tables into DayData objects."""
    wellness_by_date = {w.date: w for w in load_wellness()}
    sleep_by_date = {s.date: s for s in load_sleep()}
    hrv_by_date = {h.date: h for h in load_hrv()}
    skin_by_date = {s.date: s for s in load_skin_temp()}

    all_dates = sorted(
        wellness_by_date.keys()
        | sleep_by_date.keys()
        | hrv_by_date.keys()
        | skin_by_date.keys()
    )

    from ..models import DayHrv, DaySkinTemp, DaySleep, DayWellness

    result: list[DayData] = []
    for d in all_dates:
        result.append(DayData(
            date=d,
            wellness=wellness_by_date.get(d, DayWellness(date=d)),
            sleep=sleep_by_date.get(d, DaySleep(date=d)),
            hrv=hrv_by_date.get(d, DayHrv(date=d)),
            skin_temp=skin_by_date.get(d, DaySkinTemp(date=d)),
        ))
    return result
