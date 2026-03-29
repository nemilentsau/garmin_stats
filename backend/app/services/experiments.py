"""Experiment service — CRUD, preview, import, and analysis access."""

from __future__ import annotations

from datetime import date as date_type

from ..infra.database import (
    experiment_exists,
    load_all_experiment_analyses,
    load_daily_metrics,
    load_experiment,
    load_experiment_analysis,
    load_experiments,
    save_experiment,
    save_experiment_analysis,
)
from ..models import (
    DailyMetric,
    Experiment,
    ExperimentAnalysis,
    ExperimentPreviewIssue,
    ExperimentPreviewResponse,
    ExperimentsResponse,
    ExperimentWithAnalysis,
)
from .experiment_analysis import compute_experiment_analysis
from .experiment_stats import resolve_metric_path

# ---------------------------------------------------------------------------
# List / get
# ---------------------------------------------------------------------------


def list_experiments() -> ExperimentsResponse:
    """Return all experiments with their latest analysis."""
    experiments = load_experiments()
    analyses = load_all_experiment_analyses()
    items = [
        ExperimentWithAnalysis(
            experiment=exp,
            analysis=analyses.get(exp.id),
        )
        for exp in experiments
    ]
    return ExperimentsResponse(experiments=items)


def get_experiment(experiment_id: str) -> Experiment:
    """Load a single experiment."""
    result = load_experiment(experiment_id)
    if result is None:
        raise LookupError(f"Experiment {experiment_id} not found")
    return result


def get_experiment_with_analysis(experiment_id: str) -> ExperimentWithAnalysis:
    """Load experiment + latest analysis."""
    exp = get_experiment(experiment_id)
    analysis = load_experiment_analysis(experiment_id)
    return ExperimentWithAnalysis(experiment=exp, analysis=analysis)


# ---------------------------------------------------------------------------
# Create / update
# ---------------------------------------------------------------------------


def create_experiment(experiment: Experiment) -> Experiment:
    """Create a new experiment."""
    save_experiment(experiment)
    return experiment


def update_experiment(experiment_id: str, experiment: Experiment) -> Experiment:
    """Replace an existing experiment."""
    if experiment.id != experiment_id:
        raise ValueError("Experiment id does not match path id")
    if not experiment_exists(experiment_id):
        raise LookupError(f"Experiment {experiment_id} not found")
    save_experiment(experiment)
    return experiment


# ---------------------------------------------------------------------------
# Preview / import
# ---------------------------------------------------------------------------


def _validate_metric_path(metrics: list[DailyMetric], path: str) -> bool:
    """Check that a metric path resolves to at least one non-None value."""
    return any(resolve_metric_path(m, path) is not None for m in metrics[-30:])


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


def preview_experiment(experiment: Experiment) -> ExperimentPreviewResponse:
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

    # Date validation
    try:
        b_start = date_type.fromisoformat(design.baseline_start_date)
        b_end = date_type.fromisoformat(design.baseline_end_date)
        t_start = date_type.fromisoformat(design.treatment_start_date)
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

    # Check baseline data availability
    all_metrics = load_daily_metrics()
    metrics_in_baseline = [
        m for m in all_metrics
        if design.baseline_start_date <= m.date <= design.baseline_end_date
    ]
    if not metrics_in_baseline:
        issues.append(ExperimentPreviewIssue(
            level="error",
            message=f"No health data found for baseline period "
                    f"{design.baseline_start_date} to {design.baseline_end_date}.",
        ))
    elif len(metrics_in_baseline) < 7:
        issues.append(ExperimentPreviewIssue(
            level="warning",
            message=f"Only {len(metrics_in_baseline)} days of baseline data. "
                    f"At least 14 recommended for reliable analysis.",
        ))

    # Validate outcome metric paths
    if not experiment.outcome_metrics:
        issues.append(ExperimentPreviewIssue(
            level="error", message="At least one outcome metric is required.",
        ))
    for om in experiment.outcome_metrics:
        if not _validate_metric_path(all_metrics, om.path):
            issues.append(ExperimentPreviewIssue(
                level="error",
                message=f"Metric path '{om.path}' does not resolve to any data.",
            ))

    # Validate confounder paths
    for path in experiment.confounder_watch:
        if path.startswith("checkin."):
            if path not in _VALID_CHECKIN_FIELDS:
                issues.append(ExperimentPreviewIssue(
                    level="error",
                    message=f"Unknown checkin field: '{path}'.",
                ))
        elif not _validate_metric_path(all_metrics, path):
            issues.append(ExperimentPreviewIssue(
                level="warning",
                message=f"Confounder path '{path}' has no recent data.",
            ))

    # Lag days
    for lag in design.expected_lag_days:
        if lag < 0:
            issues.append(ExperimentPreviewIssue(
                level="error", message=f"Lag days must be non-negative, got {lag}.",
            ))

    # Duplicate check
    if experiment_exists(experiment.id):
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


def import_experiment(experiment: Experiment) -> ExperimentWithAnalysis:
    """Validate, persist, and run initial analysis."""
    preview = preview_experiment(experiment)
    if not preview.valid:
        msg = "; ".join(i.message for i in preview.issues if i.level == "error")
        raise ValueError(f"Experiment has validation errors: {msg}")

    experiment.status = "active"
    save_experiment(experiment)

    # Run initial analysis
    analysis: ExperimentAnalysis | None = None
    if experiment.design is not None:
        analysis = compute_experiment_analysis(experiment)
        save_experiment_analysis(experiment.id, analysis)

    return ExperimentWithAnalysis(experiment=experiment, analysis=analysis)


# ---------------------------------------------------------------------------
# Analysis access
# ---------------------------------------------------------------------------


def get_experiment_analysis(experiment_id: str) -> ExperimentAnalysis | None:
    """Return the latest persisted analysis for an experiment."""
    if not experiment_exists(experiment_id):
        raise LookupError(f"Experiment {experiment_id} not found")
    return load_experiment_analysis(experiment_id)
