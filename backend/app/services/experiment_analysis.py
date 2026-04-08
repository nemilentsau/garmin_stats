"""Experiment analysis orchestration.

Loads data windows, calls statistical functions, produces ExperimentAnalysis.
"""

from __future__ import annotations

import logging
from datetime import date as date_type
from datetime import timedelta

import numpy as np

from ..infra.database import (
    load_daily_checkins,
    load_daily_metrics,
    load_experiment_exposures,
    load_experiments,
    save_experiment_analysis,
)
from ..models import (
    AdherenceDayEntry,
    ConfounderCheck,
    DailyCheckIn,
    DailyMetric,
    Experiment,
    ExperimentAnalysis,
    ExperimentReportConfidence,
    MetricAnalysis,
    MetricLagResult,
    OutcomeMetric,
)
from .experiment_stats import (
    autocorrelation_lag1,
    compute_hedges_g,
    compute_nap,
    interpret_nap,
    linear_trend,
    permutation_test,
    resolve_metric_path,
    resolve_path,
    welch_t_test,
)

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Window extraction
# ---------------------------------------------------------------------------


def _date_range(start: str, end: str) -> list[str]:
    """Return all ISO date strings from start to end inclusive."""
    d = date_type.fromisoformat(start)
    end_d = date_type.fromisoformat(end)
    days: list[str] = []
    while d <= end_d:
        days.append(d.isoformat())
        d += timedelta(days=1)
    return days


def _extract_metric_values(
    metrics_map: dict[str, DailyMetric],
    path: str,
    start: str,
    end: str,
) -> list[float]:
    """Extract non-None numeric values for a metric path within a date range."""
    values: list[float] = []
    for ds in _date_range(start, end):
        m = metrics_map.get(ds)
        if m is not None:
            val = resolve_metric_path(m, path)
            if val is not None:
                values.append(val)
    return values


def _extract_confounder(
    metrics_map: dict[str, DailyMetric],
    checkins_map: dict[str, DailyCheckIn],
    path: str,
    start: str,
    end: str,
) -> list[float] | tuple[int, int]:
    """Extract confounder data.

    For boolean checkin flags: returns (flag_count, total_days).
    For numeric paths: returns list[float].
    """
    is_checkin_bool = path.startswith("checkin.") and path.split(".")[-1].endswith("_flag")
    days = _date_range(start, end)

    if is_checkin_bool:
        field = path.removeprefix("checkin.")
        flag_count = sum(
            1 for ds in days
            if getattr(checkins_map.get(ds), field, False)
        )
        return (flag_count, len(days))

    values: list[float] = []
    for ds in days:
        val = resolve_path(metrics_map.get(ds), checkins_map.get(ds), path)
        if isinstance(val, (int, float)) and not isinstance(val, bool):
            values.append(float(val))
    return values


# ---------------------------------------------------------------------------
# Single metric × single lag
# ---------------------------------------------------------------------------


def _analyse_metric_lag(
    baseline_vals: list[float],
    treatment_vals: list[float],
    lag_days: int,
    treatment_start_effective: str,
    direction: str,
) -> MetricLagResult:
    """Run full statistical battery for one metric at one lag offset."""
    b_mean = float(np.mean(baseline_vals)) if baseline_vals else 0.0
    b_sd = float(np.std(baseline_vals, ddof=1)) if len(baseline_vals) > 1 else 0.0
    t_mean = float(np.mean(treatment_vals)) if treatment_vals else 0.0
    t_sd = float(np.std(treatment_vals, ddof=1)) if len(treatment_vals) > 1 else 0.0

    delta_abs = t_mean - b_mean
    delta_pct = (delta_abs / b_mean * 100) if b_mean != 0 else 0.0

    cohens_d, hedges_g = compute_hedges_g(baseline_vals, treatment_vals)
    nap, nap_interp = compute_nap(baseline_vals, treatment_vals)
    if direction == "lower_is_better":
        nap = round(1 - nap, 4)
        nap_interp = interpret_nap(nap)
    p_perm = permutation_test(baseline_vals, treatment_vals)
    p_welch = welch_t_test(baseline_vals, treatment_vals)
    b_slope, b_slope_p = linear_trend(baseline_vals)
    ac_b = autocorrelation_lag1(baseline_vals)
    ac_t = autocorrelation_lag1(treatment_vals)

    direction_correct = delta_abs > 0 if direction == "higher_is_better" else delta_abs < 0

    return MetricLagResult(
        lag_days=lag_days,
        treatment_start_effective=treatment_start_effective,
        baseline_mean=round(b_mean, 2),
        baseline_sd=round(b_sd, 2),
        baseline_n=len(baseline_vals),
        treatment_mean=round(t_mean, 2),
        treatment_sd=round(t_sd, 2),
        treatment_n=len(treatment_vals),
        delta_abs=round(delta_abs, 2),
        delta_pct=round(delta_pct, 1),
        cohens_d=cohens_d,
        hedges_g=hedges_g,
        nap=nap,
        nap_interpretation=nap_interp,
        p_value_permutation=p_perm,
        p_value_welch=p_welch,
        baseline_trend_slope=b_slope,
        baseline_trend_p=b_slope_p,
        autocorrelation_lag1_baseline=ac_b,
        autocorrelation_lag1_treatment=ac_t,
        direction_correct=direction_correct,
    )


# ---------------------------------------------------------------------------
# Full metric analysis (across all lags)
# ---------------------------------------------------------------------------


def _analyse_metric(
    outcome: OutcomeMetric,
    metrics_map: dict[str, DailyMetric],
    baseline_start: str,
    baseline_end: str,
    treatment_start: str,
    treatment_end: str,
    lag_days_list: list[int],
) -> MetricAnalysis:
    """Compute analysis for one outcome metric across all lag offsets."""
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
        # Fallback: zero-lag with whatever data exists
        treatment_vals = _extract_metric_values(
            metrics_map, outcome.path, treatment_start, treatment_end,
        )
        lag_results.append(
            _analyse_metric_lag(
                baseline_vals, treatment_vals, 0, treatment_start, outcome.direction,
            )
        )

    # Best lag = strongest NAP away from 0.5 (accounting for direction)
    best = max(lag_results, key=lambda r: abs(r.nap - 0.5) if r.direction_correct else 0)

    return MetricAnalysis(
        path=outcome.path,
        direction=outcome.direction,
        lag_results=lag_results,
        best_lag=best.lag_days,
        best_result=best,
    )


# ---------------------------------------------------------------------------
# Confounder checks
# ---------------------------------------------------------------------------


def _check_confounders(
    confounder_paths: list[str],
    metrics_map: dict[str, DailyMetric],
    checkins_map: dict[str, DailyCheckIn],
    baseline_start: str,
    baseline_end: str,
    treatment_start: str,
    treatment_end: str,
) -> list[ConfounderCheck]:
    checks: list[ConfounderCheck] = []
    for path in confounder_paths:
        source = "checkin" if path.startswith("checkin.") else "metric"

        b_data = _extract_confounder(metrics_map, checkins_map, path, baseline_start, baseline_end)
        t_data = _extract_confounder(
            metrics_map, checkins_map, path, treatment_start, treatment_end,
        )

        if isinstance(b_data, tuple) and isinstance(t_data, tuple):
            # Boolean flag comparison
            b_flags, b_total = b_data
            t_flags, t_total = t_data
            b_rate = b_flags / b_total if b_total else 0
            t_rate = t_flags / t_total if t_total else 0
            delta = t_rate - b_rate
            is_sig = abs(delta) > _CONFOUNDER_FLAG_THRESHOLD
            field_name = path.split(".")[-1].replace("_flag", "").replace("_", " ")
            note = (
                f"{field_name}: {t_flags}/{t_total} days in treatment "
                f"vs {b_flags}/{b_total} in baseline"
            )
            checks.append(ConfounderCheck(
                path=path,
                source=source,
                baseline_mean=round(b_rate, 3),
                treatment_mean=round(t_rate, 3),
                delta_pct=round(delta * 100, 1),
                is_significant=is_sig,
                note=note,
                baseline_flag_days=b_flags,
                treatment_flag_days=t_flags,
                baseline_total_days=b_total,
                treatment_total_days=t_total,
            ))
        elif isinstance(b_data, list) and isinstance(t_data, list):
            b_mean = float(np.mean(b_data)) if b_data else None
            t_mean = float(np.mean(t_data)) if t_data else None
            delta_pct = None
            is_sig = False
            if b_mean is not None and t_mean is not None and b_mean != 0:
                delta_pct = round((t_mean - b_mean) / b_mean * 100, 1)
                # Significant if >10% change or Welch's p < 0.1
                is_sig = abs(delta_pct) > _CONFOUNDER_NUMERIC_THRESHOLD
                if len(b_data) >= 2 and len(t_data) >= 2:
                    is_sig = is_sig or welch_t_test(b_data, t_data) < _P_MODERATE

            note = f"{path}: " + (
                f"{round(t_mean, 1)} vs {round(b_mean, 1)} baseline"
                if b_mean is not None and t_mean is not None
                else "insufficient data"
            )
            checks.append(ConfounderCheck(
                path=path,
                source=source,
                baseline_mean=round(b_mean, 2) if b_mean is not None else None,
                treatment_mean=round(t_mean, 2) if t_mean is not None else None,
                delta_pct=delta_pct,
                is_significant=is_sig,
                note=note,
            ))

    return checks


# ---------------------------------------------------------------------------
# Adherence
# ---------------------------------------------------------------------------


def _compute_adherence(
    experiment: Experiment,
    treatment_start: str,
    treatment_end: str,
) -> tuple[float, list[AdherenceDayEntry]]:
    """Compute adherence rate and per-day calendar from exposures."""
    exposures = load_experiment_exposures(experiment_id=experiment.id)
    exposure_map = {e.date: e for e in exposures}

    today = date_type.today().isoformat()
    capped_end = min(treatment_end, today)
    entries: list[AdherenceDayEntry] = []
    full_count = 0

    for ds in _date_range(treatment_start, capped_end):
        exp = exposure_map.get(ds)
        if exp is not None:
            entries.append(AdherenceDayEntry(
                date=ds,
                state=exp.adherence_state,
                exposure_score=exp.exposure_score,
            ))
            if exp.adherence_state in ("full", "completed"):
                full_count += 1
        else:
            entries.append(AdherenceDayEntry(date=ds, state="unknown"))

    rate = full_count / len(entries) if entries else 0.0
    return round(rate, 3), entries


# ---------------------------------------------------------------------------
# Confidence classification
# ---------------------------------------------------------------------------

_MIN_DAYS_INSUFFICIENT = 7
_MIN_ADHERENCE_INSUFFICIENT = 0.50
_NAP_HIGH = 0.93
_NAP_MODERATE = 0.66
_P_HIGH = 0.05
_P_MODERATE = 0.10
_ADHERENCE_HIGH = 0.85
_ADHERENCE_MODERATE = 0.70
_BASELINE_HIGH = 21
_BASELINE_MODERATE = 14
_CONFOUNDER_FLAG_THRESHOLD = 0.15
_CONFOUNDER_NUMERIC_THRESHOLD = 10


def _classify_confidence(
    metrics: list[MetricAnalysis],
    confounders: list[ConfounderCheck],
    adherence_rate: float,
    baseline_n: int,
    treatment_n: int,
) -> ExperimentReportConfidence:
    if baseline_n < _MIN_DAYS_INSUFFICIENT or treatment_n < _MIN_DAYS_INSUFFICIENT:
        return "insufficient"
    if adherence_rate < _MIN_ADHERENCE_INSUFFICIENT:
        return "insufficient"

    best_results = [m.best_result for m in metrics]
    has_major_confounder = any(c.is_significant for c in confounders)
    best_nap = max((r.nap for r in best_results), default=0.5)
    best_p = min((r.p_value_permutation for r in best_results), default=1.0)

    if (
        best_nap >= _NAP_HIGH and best_p < _P_HIGH
        and adherence_rate >= _ADHERENCE_HIGH
        and not has_major_confounder and baseline_n >= _BASELINE_HIGH
    ):
        return "high"
    if (
        best_nap >= _NAP_MODERATE and best_p < _P_MODERATE
        and adherence_rate >= _ADHERENCE_MODERATE and not has_major_confounder
    ):
        return "moderate"
    return "low"


# ---------------------------------------------------------------------------
# Summary generation
# ---------------------------------------------------------------------------


def _generate_summary(
    experiment: Experiment,
    confidence: ExperimentReportConfidence,
    metrics: list[MetricAnalysis],
    phase: str,
) -> str:
    if not metrics:
        return f"Experiment '{experiment.name}' has no analysable metrics yet."

    primary = metrics[0]
    r = primary.best_result
    direction_word = "improved" if r.direction_correct else "worsened"

    if phase == "collecting_baseline":
        return f"Collecting baseline data for '{experiment.name}'."

    if confidence == "insufficient":
        return (
            f"Insufficient data for '{experiment.name}' — "
            f"{r.baseline_n} baseline days, {r.treatment_n} treatment days."
        )

    return (
        f"{primary.path} {direction_word} by {abs(r.delta_pct):.1f}% "
        f"(Hedges' g={r.hedges_g}, NAP={r.nap} [{r.nap_interpretation}], "
        f"p={r.p_value_permutation}). "
        f"Confidence: {confidence}."
    )


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def compute_experiment_analysis(experiment: Experiment) -> ExperimentAnalysis:
    """Compute full analysis for an experiment."""
    design = experiment.design
    if design is None:
        return ExperimentAnalysis(
            experiment_id=experiment.id,
            analysis_date=date_type.today().isoformat(),
            phase="draft",
            days_in_baseline=0,
            days_in_treatment=0,
            adherence_rate=0.0,
            adherence_by_day=[],
            metrics=[],
            confounders=[],
            overall_confidence="insufficient",
            summary=f"Experiment '{experiment.name}' has no design configured.",
        )

    dates_missing = (
        not design.baseline_start_date
        or not design.baseline_end_date
        or not design.treatment_start_date
    )
    if dates_missing:
        return ExperimentAnalysis(
            experiment_id=experiment.id,
            analysis_date=date_type.today().isoformat(),
            phase="draft",
            days_in_baseline=0,
            days_in_treatment=0,
            adherence_rate=0.0,
            adherence_by_day=[],
            metrics=[],
            confounders=[],
            overall_confidence="insufficient",
            summary=f"Experiment '{experiment.name}' has unresolved design dates.",
        )

    # After the guard above, all date fields are guaranteed non-None.
    assert design.baseline_start_date is not None
    assert design.baseline_end_date is not None
    assert design.treatment_start_date is not None

    metrics_map = {m.date: m for m in load_daily_metrics()}
    checkins_map = {c.date: c for c in load_daily_checkins()}

    today = date_type.today().isoformat()
    treatment_end = design.treatment_end_date or today
    if treatment_end > today:
        treatment_end = today

    # Determine phase
    if today < design.treatment_start_date:
        phase = "collecting_baseline"
    elif design.treatment_end_date and today > design.treatment_end_date:
        phase = "completed"
    else:
        phase = "treatment"

    # Lag days from design or experiment-level fallback
    lag_days_list = design.expected_lag_days or experiment.expected_lag_days or [0]

    # Metric analyses
    metric_analyses: list[MetricAnalysis] = []
    for outcome in experiment.outcome_metrics:
        analysis = _analyse_metric(
            outcome,
            metrics_map,
            design.baseline_start_date,
            design.baseline_end_date,
            design.treatment_start_date,
            treatment_end,
            lag_days_list,
        )
        metric_analyses.append(analysis)

    # Confounder checks
    confounders = _check_confounders(
        experiment.confounder_watch,
        metrics_map,
        checkins_map,
        design.baseline_start_date,
        design.baseline_end_date,
        design.treatment_start_date,
        treatment_end,
    )

    # Adherence
    adherence_rate, adherence_by_day = _compute_adherence(
        experiment, design.treatment_start_date, treatment_end,
    )

    # Days counts — reuse from primary metric analysis to avoid redundant extraction
    if metric_analyses:
        primary = metric_analyses[0].best_result
        baseline_n = primary.baseline_n
        treatment_n = primary.treatment_n
    else:
        baseline_n = 0
        treatment_n = 0

    # Confidence
    confidence = _classify_confidence(
        metric_analyses, confounders, adherence_rate, baseline_n, treatment_n,
    )

    # Summary
    summary = _generate_summary(experiment, confidence, metric_analyses, phase)

    return ExperimentAnalysis(
        experiment_id=experiment.id,
        analysis_date=date_type.today().isoformat(),
        phase=phase,
        days_in_baseline=baseline_n,
        days_in_treatment=treatment_n,
        adherence_rate=adherence_rate,
        adherence_by_day=adherence_by_day,
        metrics=metric_analyses,
        confounders=confounders,
        overall_confidence=confidence,
        summary=summary,
    )


# ---------------------------------------------------------------------------
# Batch refresh
# ---------------------------------------------------------------------------


def refresh_active_experiments() -> int:
    """Recompute analysis for all active experiments. Returns count refreshed."""
    experiments = load_experiments(status="active")
    count = 0
    for exp in experiments:
        if exp.design is None:
            continue
        try:
            analysis = compute_experiment_analysis(exp)
            save_experiment_analysis(exp.id, analysis)
            count += 1
        except Exception:
            log.exception("Failed to refresh experiment %s", exp.id)
    return count
