"""Time-series helpers for Garmin analytics daily metric views."""

from collections.abc import Callable
from datetime import date as date_type

from app.models import DailyMetric


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
    return round(sum(previous) / len(previous), 1) if previous else None


def trailing_ma7(values: list[float | None]) -> list[float | None]:
    """Compute 7-day trailing moving average, skipping None values."""
    result: list[float | None] = []
    for i in range(len(values)):
        window_start = max(0, i - 6)
        window = [v for v in values[window_start : i + 1] if v is not None]
        result.append(round(sum(window) / len(window), 1) if window else None)
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
