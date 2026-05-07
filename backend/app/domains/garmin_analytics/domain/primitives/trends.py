"""Time-series helpers for Garmin analytics daily metric views."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date as date_type
from typing import Protocol

from app.domains.garmin_analytics.contracts import DailyMetric
from app.domains.garmin_analytics.domain.primitives.numeric import (
    safe_avg,
    safe_percentile,
)


@dataclass(frozen=True, slots=True)
class WeeklyFiveNumberSummary:
    iso_week: str
    min: float
    q1: float | None
    median: float | None
    q3: float | None
    max: float
    count: int


class _HasDate(Protocol):
    @property
    def date(self) -> str: ...


def prior_7d_avg(
    metrics: list[DailyMetric],
    selected_index: int,
    value_fn: Callable[[DailyMetric], float | None],
) -> float | None:
    """Average of `value_fn` over up to 7 metrics preceding `selected_index`."""
    previous = [
        v
        for v in (
            value_fn(m)
            for m in metrics[max(0, selected_index - 7) : selected_index]
        )
        if v is not None
    ]
    return safe_avg(previous)


def trailing_ma7(values: list[float | None]) -> list[float | None]:
    """Compute 7-day trailing moving average, skipping None values."""
    result: list[float | None] = []
    for i in range(len(values)):
        window_start = max(0, i - 6)
        window = [v for v in values[window_start : i + 1] if v is not None]
        result.append(safe_avg(window))
    return result


def group_by_iso_week(
    metrics: list[DailyMetric],
    value_fn: Callable[[DailyMetric], float | None],
) -> dict[str, list[float]]:
    """Group daily metric values by ISO week, skipping None values."""
    weeks: dict[str, list[float]] = {}
    for metric in metrics:
        val = value_fn(metric)
        if val is None:
            continue
        try:
            metric_date = date_type.fromisoformat(metric.date)
        except ValueError:
            continue
        iso_year, iso_week, _ = metric_date.isocalendar()
        key = f"{iso_year}-W{iso_week:02d}"
        weeks.setdefault(key, []).append(val)
    return weeks


def weekly_five_number_summaries[T: _HasDate](
    items: list[T],
    value_fn: Callable[[T], float | None],
) -> list[WeeklyFiveNumberSummary]:
    """Build per-ISO-week five-number summaries, skipping missing values."""
    weeks: dict[str, list[float]] = {}
    for item in items:
        val = value_fn(item)
        if val is None:
            continue
        try:
            item_date = date_type.fromisoformat(item.date)
        except ValueError:
            continue
        iso_year, iso_week, _ = item_date.isocalendar()
        key = f"{iso_year}-W{iso_week:02d}"
        weeks.setdefault(key, []).append(val)

    summaries: list[WeeklyFiveNumberSummary] = []
    for week_key in sorted(weeks):
        values = sorted(weeks[week_key])
        summaries.append(
            WeeklyFiveNumberSummary(
                iso_week=week_key,
                min=float(values[0]),
                q1=safe_percentile(values, 25),
                median=safe_percentile(values, 50),
                q3=safe_percentile(values, 75),
                max=float(values[-1]),
                count=len(values),
            )
        )
    return summaries
