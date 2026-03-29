"""Pure statistical functions for N=1 experiment analysis.

All functions accept plain arrays of floats — no experiment-specific logic.
"""

from __future__ import annotations

import math

import numpy as np
from pydantic import BaseModel
from scipy import stats as sp_stats

from ..models import DailyCheckIn, DailyMetric

# ---------------------------------------------------------------------------
# Metric path resolution
# ---------------------------------------------------------------------------


def resolve_metric_path(metric: DailyMetric, path: str) -> float | None:
    """Resolve a dotted path like 'hrv.nightly_avg' to a numeric value."""
    current: object = metric
    for part in path.split("."):
        if current is None:
            return None
        if isinstance(current, BaseModel):
            current = getattr(current, part, None)
        else:
            return None
    if isinstance(current, (int, float)) and not isinstance(current, bool):
        return float(current)
    return None


def resolve_checkin_path(checkin: DailyCheckIn, path: str) -> float | bool | None:
    """Resolve a checkin field. *path* should NOT include the 'checkin.' prefix."""
    val = getattr(checkin, path, None)
    if isinstance(val, bool):
        return val
    if isinstance(val, (int, float)):
        return float(val)
    return None


def resolve_path(
    metric: DailyMetric | None,
    checkin: DailyCheckIn | None,
    path: str,
) -> float | bool | None:
    """Dispatch to the right resolver based on path prefix."""
    if path.startswith("checkin."):
        if checkin is None:
            return None
        return resolve_checkin_path(checkin, path.removeprefix("checkin."))
    if metric is None:
        return None
    return resolve_metric_path(metric, path)


# ---------------------------------------------------------------------------
# NAP — Non-overlap of All Pairs
# ---------------------------------------------------------------------------

_NAP_THRESHOLDS = [
    (0.93, "large"),
    (0.66, "medium"),
    (0.51, "weak"),
]


def compute_nap(baseline: list[float], treatment: list[float]) -> tuple[float, str]:
    """Non-overlap of All Pairs.

    Returns (nap_score, interpretation) where nap_score is in [0, 1].
    0.5 = no effect, 1.0 = complete separation.
    """
    if not baseline or not treatment:
        return 0.5, "no_effect"

    score = 0.0
    total = len(baseline) * len(treatment)
    for b in baseline:
        for t in treatment:
            if t > b:
                score += 1.0
            elif t == b:
                score += 0.5
    nap = score / total

    interpretation = "no_effect"
    for threshold, label in _NAP_THRESHOLDS:
        if nap >= threshold:
            interpretation = label
            break
    return round(nap, 4), interpretation


# ---------------------------------------------------------------------------
# Effect sizes
# ---------------------------------------------------------------------------


def compute_cohens_d(baseline: list[float], treatment: list[float]) -> float:
    """Cohen's d: standardised mean difference with pooled SD."""
    if len(baseline) < 2 or len(treatment) < 2:
        return 0.0
    n1, n2 = len(baseline), len(treatment)
    m1, m2 = np.mean(baseline), np.mean(treatment)
    s1, s2 = np.std(baseline, ddof=1), np.std(treatment, ddof=1)
    pooled_sd = math.sqrt(((n1 - 1) * s1**2 + (n2 - 1) * s2**2) / (n1 + n2 - 2))
    if pooled_sd == 0:
        return 0.0
    return float((m2 - m1) / pooled_sd)


def compute_hedges_g(baseline: list[float], treatment: list[float]) -> tuple[float, float]:
    """Return (cohens_d, hedges_g) with small-sample correction."""
    d = compute_cohens_d(baseline, treatment)
    n = len(baseline) + len(treatment)
    correction = 1 - 3 / (4 * n - 9) if n > 3 else 1.0
    return round(d, 4), round(d * correction, 4)


# ---------------------------------------------------------------------------
# Significance tests
# ---------------------------------------------------------------------------


def permutation_test(
    baseline: list[float],
    treatment: list[float],
    n_perms: int = 10_000,
    seed: int | None = None,
) -> float:
    """Two-sided permutation test. Returns p-value."""
    if not baseline or not treatment:
        return 1.0
    observed = abs(np.mean(treatment) - np.mean(baseline))
    pooled = np.array(baseline + treatment)
    n_b = len(baseline)
    rng = np.random.default_rng(seed)

    count = 0
    for _ in range(n_perms):
        rng.shuffle(pooled)
        perm_diff = abs(np.mean(pooled[n_b:]) - np.mean(pooled[:n_b]))
        if perm_diff >= observed:
            count += 1
    return round(count / n_perms, 4)


def welch_t_test(baseline: list[float], treatment: list[float]) -> float:
    """Welch's t-test p-value (two-sided)."""
    if len(baseline) < 2 or len(treatment) < 2:
        return 1.0
    result = sp_stats.ttest_ind(treatment, baseline, equal_var=False)
    return round(float(result.pvalue), 4)  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# Trend & autocorrelation diagnostics
# ---------------------------------------------------------------------------


def linear_trend(values: list[float]) -> tuple[float, float]:
    """OLS slope and p-value on integer index. Returns (slope, p_value)."""
    if len(values) < 3:
        return 0.0, 1.0
    x = np.arange(len(values), dtype=float)
    result = sp_stats.linregress(x, values)
    return round(float(result.slope), 6), round(float(result.pvalue), 4)  # type: ignore[union-attr]


def autocorrelation_lag1(values: list[float]) -> float:
    """Lag-1 autocorrelation coefficient."""
    if len(values) < 4:
        return 0.0
    arr = np.array(values)
    corr = np.corrcoef(arr[:-1], arr[1:])
    return round(float(corr[0, 1]), 4)
