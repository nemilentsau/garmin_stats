"""Null-tolerant scalar summary, histogram, and percentile helpers."""

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True, slots=True)
class ScalarSummary:
    avg: float | None = None
    min: int | float | None = None
    max: int | float | None = None
    median: float | None = None
    q1: float | None = None
    q3: float | None = None


@dataclass(frozen=True, slots=True)
class HistogramBin:
    bin_start: int
    bin_end: int
    count: int


def optional_float(value: int | float | None) -> float | None:
    """Lift `Optional[int | float]` to `Optional[float]`."""
    return float(value) if value is not None else None


def safe_avg(values: Sequence[int | float]) -> float | None:
    """Average with rounding, or None if empty."""
    return round(float(np.mean(values)), 1) if values else None


def safe_median(values: Sequence[int | float]) -> float | None:
    """Median with rounding, or None if empty."""
    return round(float(np.median(values)), 1) if values else None


def safe_percentile(values: Sequence[int | float], pct: float) -> float | None:
    """Percentile with rounding, or None if empty."""
    return round(float(np.percentile(values, pct)), 1) if values else None


def safe_min(values: Sequence[int | float], ndigits: int = 1) -> float | None:
    """Min with rounding, or None if empty."""
    return round(float(min(values)), ndigits) if values else None


def safe_max(values: Sequence[int | float], ndigits: int = 1) -> float | None:
    """Max with rounding, or None if empty."""
    return round(float(max(values)), ndigits) if values else None


def summarize_scalar_values(
    values: Sequence[int | float],
    *,
    rounded_extrema: bool = False,
) -> ScalarSummary:
    """Common nullable distribution summary for scalar metric readings."""
    return ScalarSummary(
        avg=safe_avg(values),
        min=safe_min(values) if rounded_extrema else min(values) if values else None,
        max=safe_max(values) if rounded_extrema else max(values) if values else None,
        median=safe_median(values),
        q1=safe_percentile(values, 25),
        q3=safe_percentile(values, 75),
    )


def histogram_bins(
    values: Sequence[int | float],
    bin_width: int,
) -> list[HistogramBin]:
    """Fixed-width histogram of `values`, with empty bins removed."""
    if not values:
        return []
    min_val = min(values)
    max_val = max(values)
    bin_start = int(min_val // bin_width) * bin_width
    bin_end = (int(max_val // bin_width) + 1) * bin_width
    counts: dict[int, int] = {}
    for v in values:
        b = int(v // bin_width) * bin_width
        counts[b] = counts.get(b, 0) + 1
    return [
        HistogramBin(bin_start=b, bin_end=b + bin_width, count=counts[b])
        for b in range(bin_start, bin_end, bin_width)
        if counts.get(b, 0) > 0
    ]


def percentile_rank(
    values: Sequence[int | float],
    target: float,
) -> float | None:
    """Percent of `values` at or below `target` (0-100), or None if empty."""
    if not values:
        return None
    arr = np.sort(values)
    idx = float(np.searchsorted(arr, target, side="right"))
    return round(idx / len(values) * 100, 1)
