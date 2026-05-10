"""Outcome metric analysis for N=1 experiments.

Outcome analysis extracts baseline and treatment samples for a configured
metric path, evaluates every expected lag, and selects the lag with the
strongest directionally correct non-overlap signal.
"""

from __future__ import annotations

from datetime import date as date_type
from datetime import timedelta

import numpy as np

from app.domains.experiments.contracts import (
    MetricAnalysis,
    MetricLagResult,
    OutcomeMetric,
    OutcomeMetricDirection,
)
from app.domains.garmin_health.contracts import DailyMetric

from .metric_paths import resolve_metric_path
from .statistics import (
    autocorrelation_lag1,
    compute_hedges_g,
    compute_nap,
    interpret_nap,
    linear_trend,
    permutation_test,
    welch_t_test,
)
from .windows import date_range


def _extract_metric_values(
    metrics_map: dict[str, DailyMetric],
    path: str,
    start: str,
    end: str,
) -> list[float]:
    """Extract non-null numeric values for a metric path within a date range."""
    values: list[float] = []
    for day in date_range(start, end):
        metric = metrics_map.get(day)
        if metric is None:
            continue
        value = resolve_metric_path(metric, path)
        if value is not None:
            values.append(value)
    return values


def _analyse_metric_lag(
    baseline_vals: list[float],
    treatment_vals: list[float],
    lag_days: int,
    treatment_start_effective: str,
    direction: OutcomeMetricDirection,
) -> MetricLagResult:
    """Run the statistical battery for one outcome at one lag offset."""
    baseline_mean = float(np.mean(baseline_vals)) if baseline_vals else 0.0
    baseline_sd = float(np.std(baseline_vals, ddof=1)) if len(baseline_vals) > 1 else 0.0
    treatment_mean = float(np.mean(treatment_vals)) if treatment_vals else 0.0
    treatment_sd = (
        float(np.std(treatment_vals, ddof=1)) if len(treatment_vals) > 1 else 0.0
    )

    delta_abs = treatment_mean - baseline_mean
    delta_pct = (delta_abs / baseline_mean * 100) if baseline_mean != 0 else 0.0

    cohens_d, hedges_g = compute_hedges_g(baseline_vals, treatment_vals)
    nap, nap_interp = compute_nap(baseline_vals, treatment_vals)
    if direction == "lower_is_better":
        nap = round(1 - nap, 4)
        nap_interp = interpret_nap(nap)
    p_perm = permutation_test(baseline_vals, treatment_vals)
    p_welch = welch_t_test(baseline_vals, treatment_vals)
    baseline_slope, baseline_slope_p = linear_trend(baseline_vals)
    baseline_autocorrelation = autocorrelation_lag1(baseline_vals)
    treatment_autocorrelation = autocorrelation_lag1(treatment_vals)

    direction_correct = delta_abs > 0 if direction == "higher_is_better" else delta_abs < 0

    return MetricLagResult(
        lag_days=lag_days,
        treatment_start_effective=treatment_start_effective,
        baseline_mean=round(baseline_mean, 2),
        baseline_sd=round(baseline_sd, 2),
        baseline_n=len(baseline_vals),
        treatment_mean=round(treatment_mean, 2),
        treatment_sd=round(treatment_sd, 2),
        treatment_n=len(treatment_vals),
        delta_abs=round(delta_abs, 2),
        delta_pct=round(delta_pct, 1),
        cohens_d=cohens_d,
        hedges_g=hedges_g,
        nap=nap,
        nap_interpretation=nap_interp,
        p_value_permutation=p_perm,
        p_value_welch=p_welch,
        baseline_trend_slope=baseline_slope,
        baseline_trend_p=baseline_slope_p,
        autocorrelation_lag1_baseline=baseline_autocorrelation,
        autocorrelation_lag1_treatment=treatment_autocorrelation,
        direction_correct=direction_correct,
    )


def analyse_metric(
    outcome: OutcomeMetric,
    metrics_map: dict[str, DailyMetric],
    baseline_start: str,
    baseline_end: str,
    treatment_start: str,
    treatment_end: str,
    lag_days_list: list[int],
) -> MetricAnalysis:
    """Compute one outcome metric across all configured lag offsets."""
    baseline_vals = _extract_metric_values(
        metrics_map, outcome.path, baseline_start, baseline_end,
    )

    lag_results: list[MetricLagResult] = []
    for lag in lag_days_list:
        effective_start = (
            date_type.fromisoformat(treatment_start) + timedelta(days=lag)
        ).isoformat()
        if effective_start > treatment_end:
            continue
        treatment_vals = _extract_metric_values(
            metrics_map, outcome.path, effective_start, treatment_end,
        )
        result = _analyse_metric_lag(
            baseline_vals, treatment_vals, lag, effective_start, outcome.direction,
        )
        lag_results.append(result)

    if not lag_results:
        treatment_vals = _extract_metric_values(
            metrics_map, outcome.path, treatment_start, treatment_end,
        )
        lag_results.append(
            _analyse_metric_lag(
                baseline_vals, treatment_vals, 0, treatment_start, outcome.direction,
            )
        )

    best = max(lag_results, key=lambda result: (
        abs(result.nap - 0.5) if result.direction_correct else 0
    ))

    return MetricAnalysis(
        path=outcome.path,
        direction=outcome.direction,
        lag_results=lag_results,
        best_lag=best.lag_days,
        best_result=best,
    )
