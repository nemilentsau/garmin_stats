"""Experiment service."""

from ..infra.database import load_experiments, save_experiment
from ..models import Experiment, ExperimentsResponse


def list_experiments() -> ExperimentsResponse:
    """Return all experiments."""
    experiments = load_experiments()
    return ExperimentsResponse(experiments=experiments, total=len(experiments))


def get_experiment(experiment_id: str) -> Experiment:
    """Load a single experiment."""
    for experiment in load_experiments():
        if experiment.id == experiment_id:
            return experiment
    raise LookupError(f"Experiment {experiment_id} not found")


def create_experiment(experiment: Experiment) -> Experiment:
    """Create a new experiment."""
    save_experiment(experiment)
    return experiment


def update_experiment(experiment_id: str, experiment: Experiment) -> Experiment:
    """Replace an existing experiment."""
    if experiment.id != experiment_id:
        raise ValueError("Experiment id does not match path id")
    get_experiment(experiment_id)
    save_experiment(experiment)
    return experiment
