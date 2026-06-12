"""Per-metric expanding robust-z normalization for the recovery score.

Each day is z-scored against the median/MAD of the user's own PRIOR present days
(expanding window, current day excluded), requiring at least 30 prior present days.
Validated in run 2026-06-11-recovery-normalization-baseline: trailing 30-60-day
windows absorb sustained regimes and were rejected; an expanding personal baseline
is the shippable choice. The MAD is scaled to a normal-consistent SD (x1.4826) with
a std fallback for degenerate (zero-spread) history.
"""

from __future__ import annotations

import numpy as np

MIN_PRIOR_DAYS = 30
_MAD_SCALE = 1.4826


def expanding_robust_z(values: list[float | None]) -> list[float | None]:
    """Robust-z each value against the median/MAD of its prior present values.

    Returns None for a day that is itself missing or that has fewer than
    MIN_PRIOR_DAYS present values before it (the warm-up).
    """
    out: list[float | None] = []
    arr = np.array([np.nan if v is None else float(v) for v in values], dtype=float)
    for i in range(len(arr)):
        if np.isnan(arr[i]):
            out.append(None)
            continue
        prior = arr[:i][~np.isnan(arr[:i])]
        if len(prior) < MIN_PRIOR_DAYS:
            out.append(None)
            continue
        median = float(np.median(prior))
        mad = float(np.median(np.abs(prior - median))) * _MAD_SCALE
        scale = mad if mad > 1e-9 else (float(np.std(prior)) or 1e-9)
        out.append((float(arr[i]) - median) / scale)
    return out


def expanding_baseline_median(values: list[float | None]) -> list[float | None]:
    """Median of prior present values per day (raw units) — the baseline the z is vs.

    Same warm-up rule as `expanding_robust_z`, so the two align index-for-index. Used
    by the evidence rows to show the baseline a metric is being compared against.
    """
    out: list[float | None] = []
    arr = np.array([np.nan if v is None else float(v) for v in values], dtype=float)
    for i in range(len(arr)):
        if np.isnan(arr[i]):
            out.append(None)
            continue
        prior = arr[:i][~np.isnan(arr[:i])]
        if len(prior) < MIN_PRIOR_DAYS:
            out.append(None)
            continue
        out.append(float(np.median(prior)))
    return out
