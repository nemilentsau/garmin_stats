"""Time-series helpers for Garmin analytics daily metric views."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date as date_type
from typing import Protocol

import numpy as np

# Re-exported so existing `from ...primitives.trends import BASELINE_WINDOW_DEFAULT`
# importers keep working; the constant is defined once in the contracts layer.
from app.domains.garmin_analytics.contracts.analysis import (
    BASELINE_WINDOW_DEFAULT as BASELINE_WINDOW_DEFAULT,
)
from app.domains.garmin_health.contracts import DailyMetric
from app.utils.numeric import (
    robust_center_scale,
    safe_avg,
    safe_percentile,
)

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


def trailing_ma7_point(values: list[float | None], index: int) -> float | None:
    """Trailing 7-day moving average at a single ``index``, inclusive of that point.

    Averages the present values in the inclusive window ``[index - 6, index]`` (current
    value included), skipping ``None``; returns ``None`` when the window holds no present
    value. This is the single definition of the HRV "7-day average": the chart line
    (:func:`trailing_ma7`) maps it across the series, and the selected-day footnote
    compares this same point against the long baseline — so the line and the footnote
    can never label two different quantities as "7-day average". Distinct from
    :func:`prior_7d_avg`, which excludes the current night for the "tonight vs recent"
    recovery delta.
    """
    window = [v for v in values[max(0, index - 6) : index + 1] if v is not None]
    return safe_avg(window)


def trailing_ma7(values: list[float | None]) -> list[float | None]:
    """7-day trailing moving average across the series, inclusive of each point.

    Series form of :func:`trailing_ma7_point` — see it for the window and ``None``-skipping
    policy. Defined as a map over the single-point helper so the chart line and any
    single-index caller share one formula.
    """
    return [trailing_ma7_point(values, i) for i in range(len(values))]


def trailing_band_point(
    values: list[float | None],
    index: int,
    *,
    window: int,
    min_days: int,
    k_sigma: float = BASELINE_K_SIGMA,
    z_extreme: float = BASELINE_Z_EXTREME,
) -> TrailingBandPoint:
    """Robust trailing baseline for a single series ``index``.

    Same policy as :func:`trailing_robust_band` for one point: the band is built from
    present values in the half-open trailing window ``[index - window, index)`` (current
    value excluded). Returns an empty point when the window holds fewer than ``min_days``
    present values, and a collapsed band (``low == high``) with null z for a zero-spread
    window. Exposed so callers that need a single night (selected-day insights) avoid
    recomputing the band for the whole series.
    """
    prior = [v for v in values[max(0, index - window):index] if v is not None]
    if len(prior) < min_days:
        return TrailingBandPoint(None, None, None, None, False)
    median, scale = robust_center_scale(prior)
    if scale <= 1e-9:
        # Degenerate window: all priors are identical — no spread to judge "unusual".
        # Emit a collapsed band (low == high) and null z so callers can render the
        # insufficient-spread state rather than a bogus score.
        med = round(median, 1)
        return TrailingBandPoint(med, med, med, None, False)
    low = round(median - k_sigma * scale, 1)
    high = round(median + k_sigma * scale, 1)
    current = values[index]
    if current is None:
        return TrailingBandPoint(low, high, round(median, 1), None, False)
    # Round z once and derive the extreme flag from that SAME displayed value. Comparing
    # the raw z would let a value in [2.000, 2.005) round to "2.00" yet still be flagged
    # extreme — rendering "+2.00 SD · extreme night" where the shown number does not exceed
    # the |z| > 2 threshold the marker implies.
    z = round((current - median) / scale, 2)
    return TrailingBandPoint(low, high, round(median, 1), z, abs(z) > z_extreme)


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
    return [
        trailing_band_point(
            values, i, window=window, min_days=min_days, k_sigma=k_sigma, z_extreme=z_extreme
        )
        for i in range(len(values))
    ]


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
