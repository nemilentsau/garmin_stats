"""Nullable numeric helpers for Garmin analytics read models."""

from collections.abc import Sequence

import numpy as np


def safe_avg(values: Sequence[int | float]) -> float | None:
    """Average with rounding, or None if empty."""
    return round(float(np.mean(values)), 1) if values else None


def safe_median(values: Sequence[int | float]) -> float | None:
    """Median with rounding, or None if empty."""
    return round(float(np.median(values)), 1) if values else None


def safe_percentile(values: Sequence[int | float], pct: float) -> float | None:
    """Percentile with rounding, or None if empty."""
    return round(float(np.percentile(values, pct)), 1) if values else None
