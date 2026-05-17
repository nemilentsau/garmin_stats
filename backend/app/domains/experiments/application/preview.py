"""Experiment design preview and validation use cases.

Preview resolves optional routine-derived design dates, validates date windows
and metric paths, and returns issues without persisting the experiment. Import
uses this same path before saving an active experiment.
"""

from __future__ import annotations

from app.domains.experiments.contracts import (
    Experiment,
    ExperimentPreviewIssue,
    ExperimentPreviewResponse,
)
from app.domains.experiments.domain.design_dates import (
    resolve_design_dates,
    validate_design_date_window,
)
from app.domains.experiments.domain.preview_validation import (
    resolve_metric_validation_end,
    validate_baseline_coverage,
    validate_confounder_paths,
    validate_existing_experiment,
    validate_expected_lag_days,
    validate_experiment_name,
    validate_outcome_metrics,
)
from app.domains.routines.dependencies import RoutineRepository

from ..dependencies import ExperimentPreviewReadSource, ExperimentRepository


def preview_experiment(
    repo: ExperimentRepository,
    read_source: ExperimentPreviewReadSource,
    experiment: Experiment,
    *,
    routine_repo: RoutineRepository,
) -> ExperimentPreviewResponse:
    """Validate an experiment spec and return issues without writing."""
    issues: list[ExperimentPreviewIssue] = []
    issues.extend(validate_experiment_name(experiment.name))

    design = experiment.design
    if design is None:
        issues.append(ExperimentPreviewIssue(
            level="error", message="Experiment design is required.",
        ))
        return ExperimentPreviewResponse(valid=False, issues=issues, experiment=experiment)

    date_resolution = resolve_design_dates(
        design,
        experiment.linked_routine_ids,
        routine_repo.get_routine,
    )
    design = date_resolution.design
    previewed_experiment = experiment.model_copy(update={"design": design}, deep=True)
    issues.extend(date_resolution.issues)
    if any(i.level == "error" for i in date_resolution.issues):
        return ExperimentPreviewResponse(
            valid=False,
            issues=issues,
            experiment=previewed_experiment,
        )

    date_validation = validate_design_date_window(design)
    issues.extend(date_validation.issues)
    if date_validation.window is None:
        return ExperimentPreviewResponse(
            valid=False,
            issues=issues,
            experiment=previewed_experiment,
        )

    window = date_validation.window
    b_start_str = window.baseline_start.isoformat()
    b_end_str = window.baseline_end.isoformat()

    all_metrics = read_source.list_daily_metrics()
    issues.extend(validate_baseline_coverage(
        all_metrics,
        baseline_start=b_start_str,
        baseline_end=b_end_str,
    ))
    validation_end = resolve_metric_validation_end(
        treatment_end=design.treatment_end_date,
        baseline_end=b_end_str,
        metrics=all_metrics,
    )
    issues.extend(validate_outcome_metrics(
        experiment.outcome_metrics,
        all_metrics,
        start_date=b_start_str,
        end_date=validation_end,
    ))
    issues.extend(validate_confounder_paths(
        experiment.confounder_watch,
        all_metrics,
        start_date=b_start_str,
        end_date=validation_end,
    ))
    issues.extend(validate_expected_lag_days(design.expected_lag_days))
    issues.extend(validate_existing_experiment(
        experiment.id,
        exists=repo.experiment_exists(experiment.id),
    ))

    has_errors = any(i.level == "error" for i in issues)
    return ExperimentPreviewResponse(
        valid=not has_errors,
        issues=issues,
        experiment=previewed_experiment,
    )
