"""Experiment service."""

from ..infra.database import (
    experiment_exists,
    load_experiment,
    load_experiments,
    save_experiment,
)
from ..models import Experiment, ExperimentsResponse


def list_experiments() -> ExperimentsResponse:
    """Return all experiments."""
    experiments = load_experiments()
    return ExperimentsResponse(experiments=experiments)


def get_experiment(experiment_id: str) -> Experiment:
    """Load a single experiment."""
    result = load_experiment(experiment_id)
    if result is None:
        raise LookupError(f"Experiment {experiment_id} not found")
    return result


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
