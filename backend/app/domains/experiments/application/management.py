"""Experiment definition management use cases.

This module owns CRUD-style experiment workflows plus the import path that
validates a spec, activates it, and creates the initial cached analysis.
"""

from __future__ import annotations

from app.domains.experiments.contracts import (
    Experiment,
    ExperimentsResponse,
    ExperimentWithAnalysis,
)

from ..dependencies import ExperimentAnalysisReadSource, ExperimentRepository
from .analysis_cache import (
    load_current_analysis,
    persist_experiment_analysis,
    refresh_if_stale,
)
from .preview import preview_experiment


def list_experiments(
    repo: ExperimentRepository,
    read_source: ExperimentAnalysisReadSource,
) -> ExperimentsResponse:
    """Return all experiments with refreshed cached analysis where needed."""
    experiments = repo.list_experiments()
    analyses_by_id = repo.list_all_experiment_analyses()
    items = [
        ExperimentWithAnalysis(
            experiment=experiment,
            analysis=refresh_if_stale(
                repo,
                read_source,
                experiment,
                analyses_by_id.get(experiment.id),
            ),
        )
        for experiment in experiments
    ]
    return ExperimentsResponse(experiments=items)


def get_experiment(repo: ExperimentRepository, experiment_id: str) -> Experiment:
    """Load one experiment definition or raise when it is missing."""
    result = repo.get_experiment(experiment_id)
    if result is None:
        raise LookupError(f"Experiment {experiment_id} not found")
    return result


def get_experiment_with_analysis(
    repo: ExperimentRepository,
    read_source: ExperimentAnalysisReadSource,
    experiment_id: str,
) -> ExperimentWithAnalysis:
    """Load one experiment with its current cached analysis snapshot."""
    experiment = get_experiment(repo, experiment_id)
    analysis = load_current_analysis(repo, read_source, experiment)
    return ExperimentWithAnalysis(experiment=experiment, analysis=analysis)


def create_experiment(repo: ExperimentRepository, experiment: Experiment) -> Experiment:
    """Create an experiment definition without validation or analysis."""
    repo.save_experiment(experiment)
    return experiment


def update_experiment(
    repo: ExperimentRepository,
    read_source: ExperimentAnalysisReadSource,
    experiment_id: str,
    experiment: Experiment,
) -> Experiment:
    """Replace an existing experiment and refresh its cached analysis."""
    if experiment.id != experiment_id:
        raise ValueError("Experiment id does not match path id")
    if not repo.experiment_exists(experiment_id):
        raise LookupError(f"Experiment {experiment_id} not found")

    repo.save_experiment(experiment)
    persist_experiment_analysis(repo, read_source, experiment)
    return experiment


def import_experiment(
    repo: ExperimentRepository,
    read_source: ExperimentAnalysisReadSource,
    experiment: Experiment,
) -> ExperimentWithAnalysis:
    """Validate a spec, persist it as active, and create initial analysis."""
    preview = preview_experiment(
        repo,
        read_source,
        experiment,
    )
    if not preview.valid:
        msg = "; ".join(i.message for i in preview.issues if i.level == "error")
        raise ValueError(f"Experiment has validation errors: {msg}")

    resolved = preview.experiment or experiment
    resolved.status = "active"
    repo.save_experiment(resolved)
    analysis = persist_experiment_analysis(repo, read_source, resolved)

    return ExperimentWithAnalysis(experiment=resolved, analysis=analysis)
