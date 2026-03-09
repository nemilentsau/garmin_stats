"""Windowed period summary: pre-compute PeriodSummary for 3M, 6M, and All."""

from ..infra import cache
from ..infra.database import load_hrv, load_skin_temp, load_sleep, load_wellness
from ..models import (
    DayData,
    DayHrv,
    DaySkinTemp,
    DaySleep,
    DayWellness,
    PeriodSummary,
)
from ..stats import compute_period_summary
from ._windows import compute_windows

WINDOWED_PERIOD = "windowed_period"


def load_windowed_period_summary() -> dict[str, PeriodSummary]:
    """Load pre-computed period summaries for each time window (cached)."""
    return cache.cached(WINDOWED_PERIOD, _compute)


def _compute() -> dict[str, PeriodSummary]:
    return compute_windows(_reconstruct_day_data(), compute_period_summary)


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
