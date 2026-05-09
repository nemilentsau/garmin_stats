"""Experiment definition management use cases."""

from __future__ import annotations

from app.domains.experiments.contracts import (
    Experiment,
    ExperimentsResponse,
    ExperimentWithAnalysis,
)
from app.domains.routines.application.ports import RoutineRepository

from .analysis_cache import (
    load_current_analysis,
    persist_experiment_analysis,
    refresh_if_stale,
)
from .ports import ExperimentRepository
from .preview import preview_experiment


def list_experiments(repo: ExperimentRepository) -> ExperimentsResponse:
    """Return all experiments with their latest analysis."""
    experiments = repo.list_experiments()
    analyses_by_id = repo.list_all_experiment_analyses()
    items = [
        ExperimentWithAnalysis(
            experiment=experiment,
            analysis=refresh_if_stale(repo, experiment, analyses_by_id.get(experiment.id)),
        )
        for experiment in experiments
    ]
    return ExperimentsResponse(experiments=items)


def get_experiment(repo: ExperimentRepository, experiment_id: str) -> Experiment:
    """Load a single experiment."""
    result = repo.get_experiment(experiment_id)
    if result is None:
        raise LookupError(f"Experiment {experiment_id} not found")
    return result


def get_experiment_with_analysis(
    repo: ExperimentRepository,
    experiment_id: str,
) -> ExperimentWithAnalysis:
    """Load experiment plus latest analysis."""
    experiment = get_experiment(repo, experiment_id)
    analysis = load_current_analysis(repo, experiment)
    return ExperimentWithAnalysis(experiment=experiment, analysis=analysis)


def create_experiment(repo: ExperimentRepository, experiment: Experiment) -> Experiment:
    """Create a new experiment without validating or computing analysis."""
    repo.save_experiment(experiment)
    return experiment


def update_experiment(
    repo: ExperimentRepository,
    experiment_id: str,
    experiment: Experiment,
) -> Experiment:
    """Replace an existing experiment and refresh its cached analysis."""
    if experiment.id != experiment_id:
        raise ValueError("Experiment id does not match path id")
    if not repo.experiment_exists(experiment_id):
        raise LookupError(f"Experiment {experiment_id} not found")

    repo.save_experiment(experiment)
    persist_experiment_analysis(repo, experiment)
    return experiment


def import_experiment(
    repo: ExperimentRepository,
    experiment: Experiment,
    *,
    routine_repo: RoutineRepository,
) -> ExperimentWithAnalysis:
    """Validate, persist, and run initial analysis."""
    preview = preview_experiment(repo, experiment, routine_repo=routine_repo)
    if not preview.valid:
        msg = "; ".join(i.message for i in preview.issues if i.level == "error")
        raise ValueError(f"Experiment has validation errors: {msg}")

    experiment.status = "active"
    repo.save_experiment(experiment)
    analysis = persist_experiment_analysis(repo, experiment)

    return ExperimentWithAnalysis(experiment=experiment, analysis=analysis)
