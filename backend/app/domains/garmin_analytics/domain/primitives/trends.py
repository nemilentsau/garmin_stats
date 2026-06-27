"""Time-series helpers for Garmin analytics daily metric views."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date as date_type
from typing import Protocol

import numpy as np

from app.domains.garmin_health.contracts import DailyMetric
from app.utils.numeric import (
    robust_center_scale,
    safe_avg,
    safe_percentile,
)

BASELINE_WINDOW_DEFAULT = 60
BASELINE_MIN_DAYS = 21
BASELINE_K_SIGMA = 1.0
BASELINE_Z_EXTREME = 2.0


@dataclass(frozen=True, slots=True)
class WeeklyFiveNumberSummary:
    """Five-number summary for values grouped by ISO week."""

    iso_week: str
    min: float
    q1: float | None
    median: float | None
    q3: float | None
    max: float
    count: int


@dataclass(frozen=True, slots=True)
class TrailingBandPoint:
    """Trailing robust baseline at one series index.

    Fields are all ``None`` (and ``is_extreme`` False) when the trailing window
    holds fewer than the minimum present values, so callers can render an
    explicit insufficient-data state instead of a misleading band.
    """

    band_low: float | None
    band_high: float | None
    median: float | None
    z: float | None
    is_extreme: bool


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


def trailing_robust_band(
    values: list[float | None],
    *,
    window: int,
    min_days: int,
    k_sigma: float = BASELINE_K_SIGMA,
    z_extreme: float = BASELINE_Z_EXTREME,
) -> list[TrailingBandPoint]:
    """Per-index robust normal range from the trailing ``window`` present values.

    For each index the band is built from present values in the half-open
    trailing window ``[i - window, i)`` (current value excluded, matching the
    recovery core's prior-only convention). Indices whose trailing window holds
    fewer than ``min_days`` present values yield an empty ``TrailingBandPoint``.
    """
    out: list[TrailingBandPoint] = []
    for i in range(len(values)):
        prior = [v for v in values[max(0, i - window):i] if v is not None]
        if len(prior) < min_days:
            out.append(TrailingBandPoint(None, None, None, None, False))
            continue
        median, scale = robust_center_scale(prior)
        if scale <= 1e-9:
            # Degenerate window: all priors are identical — no spread to judge
            # "unusual". Emit collapsed band (low == high) and null z so callers
            # can render the insufficient-spread state rather than a bogus score.
            med = round(median, 1)
            out.append(TrailingBandPoint(med, med, med, None, False))
            continue
        low = round(median - k_sigma * scale, 1)
        high = round(median + k_sigma * scale, 1)
        current = values[i]
        if current is None:
            out.append(TrailingBandPoint(low, high, round(median, 1), None, False))
            continue
        z = (current - median) / scale
        out.append(
            TrailingBandPoint(low, high, round(median, 1), round(z, 2), abs(z) > z_extreme)
        )
    return out


def trailing_sd(
    values: list[float | None],
    window: int,
    min_valid: int,
) -> list[float | None]:
    """Rolling sample standard deviation (ddof=1) over a trailing `window`.

    None values inside a window are skipped. Returns None at any position whose
    window holds fewer than `min_valid` non-None values, so a thin left edge or a
    sparse stretch produces no spurious spread. Mirrors the None-skipping policy of
    `trailing_ma7`; used to size the recovery trajectory's dispersion band.

    Callers must pass ``min_valid >= 2``; sample SD (ddof=1) is undefined for a
    single value.
    """
    result: list[float | None] = []
    for i in range(len(values)):
        window_start = max(0, i - (window - 1))
        present = [v for v in values[window_start : i + 1] if v is not None]
        if len(present) < min_valid:
            result.append(None)
        else:
            result.append(round(float(np.std(present, ddof=1)), 3))
    return result


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
