"""Experiment HTTP routes."""

from fastapi import APIRouter

from ..models import Experiment, ExperimentsResponse
from ..services.experiments import (
    create_experiment,
    get_experiment,
    list_experiments,
    update_experiment,
)

router = APIRouter(prefix="/api/experiments", tags=["experiments"])


@router.get("", response_model=ExperimentsResponse)
def get_experiments():
    """Return all experiments."""
    return list_experiments()


@router.get("/{experiment_id}", response_model=Experiment)
def get_experiment_detail(experiment_id: str):
    """Return a single experiment."""
    return get_experiment(experiment_id)


@router.post("", response_model=Experiment)
def post_experiment(experiment: Experiment):
    """Create an experiment."""
    return create_experiment(experiment)


@router.put("/{experiment_id}", response_model=Experiment)
def put_experiment(experiment_id: str, experiment: Experiment):
    """Replace an existing experiment."""
    return update_experiment(experiment_id, experiment)
