"""Experiment HTTP routes."""

from fastapi import APIRouter, HTTPException

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
    try:
        return get_experiment(experiment_id)
    except LookupError as err:
        raise HTTPException(status_code=404, detail=str(err)) from err


@router.post("", response_model=Experiment)
def post_experiment(experiment: Experiment):
    """Create an experiment."""
    return create_experiment(experiment)


@router.put("/{experiment_id}", response_model=Experiment)
def put_experiment(experiment_id: str, experiment: Experiment):
    """Replace an existing experiment."""
    try:
        return update_experiment(experiment_id, experiment)
    except LookupError as err:
        raise HTTPException(status_code=404, detail=str(err)) from err
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err
