"""Experiment analysis pipeline assembly."""

from __future__ import annotations

from datetime import date as date_type

from app.domains.experiments.contracts import (
    Experiment,
    ExperimentAnalysis,
    ExperimentDesign,
    ExperimentExposure,
    MetricAnalysis,
)
from app.domains.garmin_health.contracts import DailyMetric
from app.domains.journal.contracts import DailyCheckIn

from .adherence import compute_adherence
from .confounders import check_confounders
from .outcomes import analyse_metric
from .reporting import classify_confidence, generate_summary


def expected_experiment_phase(experiment: Experiment) -> str:
    """Phase that ``compute_experiment_analysis`` would assign for the current date."""
    design = experiment.design
    if design is None or not design.treatment_start_date:
        return "draft"
    today = date_type.today().isoformat()
    if today < design.treatment_start_date:
        return "collecting_baseline"
    if design.treatment_end_date and today > design.treatment_end_date:
        return "completed"
    return "treatment"


def current_treatment_window_end(design: ExperimentDesign | None) -> str | None:
    """End of the realised treatment window: the planned end clamped to today."""
    if design is None or not design.treatment_start_date:
        return None
    today = date_type.today().isoformat()
    treatment_end = design.treatment_end_date or today
    return min(treatment_end, today)


def unanalyzable_placeholder(experiment: Experiment) -> ExperimentAnalysis | None:
    """Placeholder analysis for experiments without enough design to be analyzed, else None.

    Exposed so callers can short-circuit data loading before invoking the full pipeline.
    """
    design = experiment.design
    if design is None:
        return _draft_placeholder(
            experiment, f"Experiment '{experiment.name}' has no design configured.",
        )
    if (
        not design.baseline_start_date
        or not design.baseline_end_date
        or not design.treatment_start_date
    ):
        return _draft_placeholder(
            experiment, f"Experiment '{experiment.name}' has unresolved design dates.",
        )
    return None


def _draft_placeholder(experiment: Experiment, summary: str) -> ExperimentAnalysis:
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
        summary=summary,
    )


def compute_experiment_analysis(
    experiment: Experiment,
    *,
    daily_metrics: list[DailyMetric],
    daily_checkins: list[DailyCheckIn],
    exposures: list[ExperimentExposure],
) -> ExperimentAnalysis:
    """Compute full analysis for an experiment."""
    placeholder = unanalyzable_placeholder(experiment)
    if placeholder is not None:
        return placeholder

    design = experiment.design
    assert design is not None
    assert design.baseline_start_date is not None
    assert design.baseline_end_date is not None
    assert design.treatment_start_date is not None

    metrics_map = {metric.date: metric for metric in daily_metrics}
    checkins_map = {checkin.date: checkin for checkin in daily_checkins}

    treatment_end = current_treatment_window_end(design)
    assert treatment_end is not None
    phase = expected_experiment_phase(experiment)
    lag_days_list = design.expected_lag_days or experiment.expected_lag_days or [0]

    metric_analyses: list[MetricAnalysis] = [
        analyse_metric(
            outcome,
            metrics_map,
            design.baseline_start_date,
            design.baseline_end_date,
            design.treatment_start_date,
            treatment_end,
            lag_days_list,
        )
        for outcome in experiment.outcome_metrics
    ]

    confounders = check_confounders(
        experiment.confounder_watch,
        metrics_map,
        checkins_map,
        design.baseline_start_date,
        design.baseline_end_date,
        design.treatment_start_date,
        treatment_end,
    )
    adherence_rate, adherence_by_day = compute_adherence(
        exposures, design.treatment_start_date, treatment_end,
    )

    if metric_analyses:
        primary = metric_analyses[0].best_result
        baseline_n = primary.baseline_n
        treatment_n = primary.treatment_n
    else:
        baseline_n = 0
        treatment_n = 0

    confidence = classify_confidence(
        metric_analyses, confounders, adherence_rate, baseline_n, treatment_n,
    )
    summary = generate_summary(experiment, confidence, metric_analyses, phase)

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
