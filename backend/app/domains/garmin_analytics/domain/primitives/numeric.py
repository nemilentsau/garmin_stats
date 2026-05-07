"""Nullable numeric helpers for Garmin analytics read models."""

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
