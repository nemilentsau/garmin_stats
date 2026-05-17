"""Experiment preview validation rules.

Preview validation is pure policy over experiment contracts and Garmin read
models. The application use case orchestrates data loading and persistence
checks, while this module owns issue construction for names, baseline coverage,
metric paths, confounder paths, lag values, and overwrite warnings.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.domains.experiments.contracts import (
    ExperimentPreviewIssue,
    OutcomeMetric,
)
from app.domains.experiments.domain.metric_paths import (
    is_valid_checkin_path,
    resolve_metric_path,
)
from app.domains.garmin_health.contracts import DailyMetric


def validate_experiment_name(name: str) -> list[ExperimentPreviewIssue]:
    """Return a required-name issue when the preview spec is unnamed."""
    if name and name.strip():
        return []
    return [ExperimentPreviewIssue(level="error", message="Name is required.")]


def validate_baseline_coverage(
    metrics: Sequence[DailyMetric],
    *,
    baseline_start: str,
    baseline_end: str,
) -> list[ExperimentPreviewIssue]:
    """Validate that the baseline window has enough Garmin metric rows."""
    metrics_in_baseline = [
        m for m in metrics
        if baseline_start <= m.date <= baseline_end
    ]
    if not metrics_in_baseline:
        return [ExperimentPreviewIssue(
            level="error",
            message=f"No health data found for baseline period "
                    f"{baseline_start} to {baseline_end}.",
        )]
    if len(metrics_in_baseline) < 7:
        return [ExperimentPreviewIssue(
            level="warning",
            message=f"Only {len(metrics_in_baseline)} days of baseline data. "
                    f"At least 14 recommended for reliable analysis.",
        )]
    return []


def resolve_metric_validation_end(
    *,
    treatment_end: str | None,
    baseline_end: str,
    metrics: Sequence[DailyMetric],
) -> str:
    """Return the inclusive end date used for preview metric path validation."""
    validation_end = treatment_end or baseline_end
    if metrics:
        validation_end = max(validation_end, metrics[-1].date)
    return validation_end


def validate_outcome_metrics(
    outcome_metrics: Sequence[OutcomeMetric],
    metrics: Sequence[DailyMetric],
    *,
    start_date: str,
    end_date: str,
) -> list[ExperimentPreviewIssue]:
    """Validate required outcome metric paths against the experiment window."""
    issues: list[ExperimentPreviewIssue] = []
    if not outcome_metrics:
        issues.append(ExperimentPreviewIssue(
            level="error", message="At least one outcome metric is required.",
        ))

    for outcome in outcome_metrics:
        if not _validate_metric_path(
            metrics,
            outcome.path,
            start_date=start_date,
            end_date=end_date,
        ):
            issues.append(ExperimentPreviewIssue(
                level="error",
                message=(
                    f"Metric path '{outcome.path}' does not resolve to any data in the "
                    "configured experiment window."
                ),
            ))
    return issues


def validate_confounder_paths(
    confounder_paths: Sequence[str],
    metrics: Sequence[DailyMetric],
    *,
    start_date: str,
    end_date: str,
) -> list[ExperimentPreviewIssue]:
    """Validate Garmin and check-in confounder paths for preview warnings."""
    issues: list[ExperimentPreviewIssue] = []
    for path in confounder_paths:
        if path.startswith("checkin."):
            if not is_valid_checkin_path(path):
                issues.append(ExperimentPreviewIssue(
                    level="error",
                    message=f"Unknown checkin field: '{path}'.",
                ))
        elif not _validate_metric_path(
            metrics,
            path,
            start_date=start_date,
            end_date=end_date,
        ):
            issues.append(ExperimentPreviewIssue(
                level="warning",
                message=(
                    f"Confounder path '{path}' has no data in the configured "
                    "experiment window."
                ),
            ))
    return issues


def validate_expected_lag_days(lag_days: Sequence[int]) -> list[ExperimentPreviewIssue]:
    """Validate that expected lag offsets are non-negative."""
    return [
        ExperimentPreviewIssue(
            level="error", message=f"Lag days must be non-negative, got {lag}.",
        )
        for lag in lag_days
        if lag < 0
    ]


def validate_existing_experiment(
    experiment_id: str,
    *,
    exists: bool,
) -> list[ExperimentPreviewIssue]:
    """Return a warning when importing would overwrite an experiment id."""
    if not exists:
        return []
    return [ExperimentPreviewIssue(
        level="warning",
        message=f"Experiment '{experiment_id}' already exists and will be overwritten.",
    )]


def _validate_metric_path(
    metrics: Sequence[DailyMetric],
    path: str,
    *,
    start_date: str,
    end_date: str,
) -> bool:
    return any(
        resolve_metric_path(metric, path) is not None
        for metric in metrics
        if start_date <= metric.date <= end_date
    )
