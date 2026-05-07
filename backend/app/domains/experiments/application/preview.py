"""Experiment design preview and validation use cases."""

from __future__ import annotations

from datetime import date as date_type
from datetime import timedelta

from app.domains.garmin_analytics.contracts import DailyMetric
from app.domains.routines.application.ports import RoutineRepository
from app.models import (
    Experiment,
    ExperimentDesign,
    ExperimentPreviewIssue,
    ExperimentPreviewResponse,
)

from .analysis_math import resolve_metric_path
from .ports import ExperimentRepository


def _validate_metric_path(
    metrics: list[DailyMetric],
    path: str,
    *,
    start_date: str,
    end_date: str,
) -> bool:
    """Check that a metric path resolves inside the configured experiment window."""
    return any(
        resolve_metric_path(metric, path) is not None
        for metric in metrics
        if start_date <= metric.date <= end_date
    )


_VALID_CHECKIN_FIELDS = {
    "checkin.alcohol_flag",
    "checkin.travel_flag",
    "checkin.illness_flag",
    "checkin.energy",
    "checkin.mood",
    "checkin.motivation",
    "checkin.soreness",
    "checkin.stress_subjective",
    "checkin.sleep_quality_subjective",
    "checkin.workload_subjective",
}


def _resolve_design_dates(
    routine_repo: RoutineRepository,
    design: ExperimentDesign,
    linked_routine_ids: list[str],
) -> list[ExperimentPreviewIssue]:
    """Fill in design dates from linked routine when using baseline_duration_days.

    Mutates design in place and returns any issues encountered.
    """
    issues: list[ExperimentPreviewIssue] = []

    has_dates = (
        design.baseline_start_date
        and design.baseline_end_date
        and design.treatment_start_date
    )
    if has_dates:
        return issues

    if design.baseline_duration_days is None:
        issues.append(ExperimentPreviewIssue(
            level="error",
            message="Either provide explicit dates or baseline_duration_days.",
        ))
        return issues

    if design.baseline_duration_days < 1:
        issues.append(ExperimentPreviewIssue(
            level="error",
            message="baseline_duration_days must be at least 1.",
        ))
        return issues

    if not linked_routine_ids:
        issues.append(ExperimentPreviewIssue(
            level="error",
            message="baseline_duration_days requires a linked routine to derive dates.",
        ))
        return issues

    routine = routine_repo.get_routine(linked_routine_ids[0])
    if routine is None:
        issues.append(ExperimentPreviewIssue(
            level="error",
            message=f"Linked routine '{linked_routine_ids[0]}' not found. "
                    "Import and activate the routine before the experiment.",
        ))
        return issues

    treatment_start = date_type.fromisoformat(routine.start_date)
    baseline_end = treatment_start - timedelta(days=1)
    baseline_start = baseline_end - timedelta(days=design.baseline_duration_days - 1)

    design.baseline_start_date = baseline_start.isoformat()
    design.baseline_end_date = baseline_end.isoformat()
    design.treatment_start_date = treatment_start.isoformat()

    if routine.end_date and design.treatment_end_date is None:
        design.treatment_end_date = routine.end_date

    return issues


def preview_experiment(
    repo: ExperimentRepository,
    experiment: Experiment,
    *,
    routine_repo: RoutineRepository,
) -> ExperimentPreviewResponse:
    """Validate an experiment spec without persisting."""
    issues: list[ExperimentPreviewIssue] = []

    if not experiment.name or not experiment.name.strip():
        issues.append(ExperimentPreviewIssue(level="error", message="Name is required."))

    design = experiment.design
    if design is None:
        issues.append(ExperimentPreviewIssue(
            level="error", message="Experiment design is required.",
        ))
        return ExperimentPreviewResponse(valid=False, issues=issues, experiment=experiment)

    resolve_issues = _resolve_design_dates(routine_repo, design, experiment.linked_routine_ids)
    issues.extend(resolve_issues)
    if any(i.level == "error" for i in resolve_issues):
        return ExperimentPreviewResponse(valid=False, issues=issues, experiment=experiment)

    try:
        b_start = date_type.fromisoformat(design.baseline_start_date)  # type: ignore[arg-type]
        b_end = date_type.fromisoformat(design.baseline_end_date)  # type: ignore[arg-type]
        t_start = date_type.fromisoformat(design.treatment_start_date)  # type: ignore[arg-type]
    except ValueError as e:
        issues.append(ExperimentPreviewIssue(level="error", message=f"Invalid date: {e}"))
        return ExperimentPreviewResponse(valid=False, issues=issues, experiment=experiment)

    if b_start >= b_end:
        issues.append(ExperimentPreviewIssue(
            level="error", message="Baseline start must be before baseline end.",
        ))
    if b_end >= t_start:
        issues.append(ExperimentPreviewIssue(
            level="error",
            message="Baseline end must be before treatment start.",
        ))

    if design.treatment_end_date:
        try:
            t_end = date_type.fromisoformat(design.treatment_end_date)
            if t_start >= t_end:
                issues.append(ExperimentPreviewIssue(
                    level="error",
                    message="Treatment start must be before treatment end.",
                ))
        except ValueError as e:
            issues.append(ExperimentPreviewIssue(
                level="error", message=f"Invalid treatment end date: {e}",
            ))

    b_start_str = b_start.isoformat()
    b_end_str = b_end.isoformat()

    all_metrics = repo.list_daily_metrics()
    metrics_in_baseline = [
        m for m in all_metrics
        if b_start_str <= m.date <= b_end_str
    ]
    if not metrics_in_baseline:
        issues.append(ExperimentPreviewIssue(
            level="error",
            message=f"No health data found for baseline period "
                    f"{b_start_str} to {b_end_str}.",
        ))
    elif len(metrics_in_baseline) < 7:
        issues.append(ExperimentPreviewIssue(
            level="warning",
            message=f"Only {len(metrics_in_baseline)} days of baseline data. "
                    f"At least 14 recommended for reliable analysis.",
        ))

    validation_end = design.treatment_end_date or b_end_str
    if all_metrics:
        validation_end = max(validation_end, all_metrics[-1].date)

    if not experiment.outcome_metrics:
        issues.append(ExperimentPreviewIssue(
            level="error", message="At least one outcome metric is required.",
        ))
    for outcome in experiment.outcome_metrics:
        if not _validate_metric_path(
            all_metrics,
            outcome.path,
            start_date=b_start_str,
            end_date=validation_end,
        ):
            issues.append(ExperimentPreviewIssue(
                level="error",
                message=(
                    f"Metric path '{outcome.path}' does not resolve to any data in the "
                    "configured experiment window."
                ),
            ))

    for path in experiment.confounder_watch:
        if path.startswith("checkin."):
            if path not in _VALID_CHECKIN_FIELDS:
                issues.append(ExperimentPreviewIssue(
                    level="error",
                    message=f"Unknown checkin field: '{path}'.",
                ))
        elif not _validate_metric_path(
            all_metrics,
            path,
            start_date=b_start_str,
            end_date=validation_end,
        ):
            issues.append(ExperimentPreviewIssue(
                level="warning",
                message=(
                    f"Confounder path '{path}' has no data in the configured "
                    "experiment window."
                ),
            ))

    for lag in design.expected_lag_days:
        if lag < 0:
            issues.append(ExperimentPreviewIssue(
                level="error", message=f"Lag days must be non-negative, got {lag}.",
            ))

    if repo.experiment_exists(experiment.id):
        issues.append(ExperimentPreviewIssue(
            level="warning",
            message=f"Experiment '{experiment.id}' already exists and will be overwritten.",
        ))

    has_errors = any(i.level == "error" for i in issues)
    return ExperimentPreviewResponse(
        valid=not has_errors,
        issues=issues,
        experiment=experiment,
    )
