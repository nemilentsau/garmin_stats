"""Experiment service — CRUD, preview, import, and analysis access."""

from __future__ import annotations

from datetime import date as date_type
from datetime import timedelta

from ..infra.database import (
    delete_experiment_analysis,
    experiment_exists,
    load_all_experiment_analyses,
    load_daily_metrics,
    load_experiment,
    load_experiment_analysis,
    load_experiments,
    load_routine_schedule,
    save_experiment,
    save_experiment_analysis,
)
from ..models import (
    DailyMetric,
    Experiment,
    ExperimentAnalysis,
    ExperimentDesign,
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
    _persist_experiment_analysis(experiment)
    return experiment


# ---------------------------------------------------------------------------
# Preview / import
# ---------------------------------------------------------------------------


def _persist_experiment_analysis(experiment: Experiment) -> ExperimentAnalysis | None:
    """Refresh the saved analysis so reads stay aligned with the experiment spec."""
    if experiment.design is None:
        delete_experiment_analysis(experiment.id)
        return None

    analysis = compute_experiment_analysis(experiment)
    save_experiment_analysis(experiment.id, analysis)
    return analysis


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

    routine = load_routine_schedule(linked_routine_ids[0])
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

    # Resolve dates from linked routine if using baseline_duration_days
    resolve_issues = _resolve_design_dates(design, experiment.linked_routine_ids)
    issues.extend(resolve_issues)
    if any(i.level == "error" for i in resolve_issues):
        return ExperimentPreviewResponse(valid=False, issues=issues, experiment=experiment)

    # Date validation
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

    # Check baseline data availability
    b_start_str = b_start.isoformat()
    b_end_str = b_end.isoformat()

    all_metrics = load_daily_metrics()
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

    # Validate outcome metric paths
    if not experiment.outcome_metrics:
        issues.append(ExperimentPreviewIssue(
            level="error", message="At least one outcome metric is required.",
        ))
    for om in experiment.outcome_metrics:
        if not _validate_metric_path(
            all_metrics,
            om.path,
            start_date=b_start_str,
            end_date=validation_end,
        ):
            issues.append(ExperimentPreviewIssue(
                level="error",
                message=(
                    f"Metric path '{om.path}' does not resolve to any data in the "
                    "configured experiment window."
                ),
            ))

    # Validate confounder paths
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
    analysis = _persist_experiment_analysis(experiment)

    return ExperimentWithAnalysis(experiment=experiment, analysis=analysis)


# ---------------------------------------------------------------------------
# Analysis access
# ---------------------------------------------------------------------------


def get_experiment_analysis(experiment_id: str) -> ExperimentAnalysis | None:
    """Return the latest persisted analysis for an experiment."""
    if not experiment_exists(experiment_id):
        raise LookupError(f"Experiment {experiment_id} not found")
    return load_experiment_analysis(experiment_id)
