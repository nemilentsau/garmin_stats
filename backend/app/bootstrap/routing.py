"""Router registration for the FastAPI app."""

from fastapi import FastAPI

from app.core.profile.api import router as profile_router
from app.domains.artifacts.api.artifacts import router as assistant_artifacts_router
from app.domains.artifacts.api.bundles import router as assistant_artifact_bundles_router
from app.domains.artifacts.api.cards import router as cards_router
from app.domains.assistant.api.threads import router as assistant_router
from app.domains.experiments.api.experiments import router as experiments_router
from app.domains.experiments.api.target_metrics import router as target_metrics_router
from app.domains.garmin_analytics.api.biometrics import (
    daily_aggregates_router,
    hrv_router,
    skin_temp_router,
    sleep_router,
    wellness_router,
)
from app.domains.garmin_analytics.api.insights import (
    body_battery_router,
    heart_rate_router,
    stress_router,
)
from app.domains.garmin_analytics.api.overview import router as dashboard_router
from app.domains.garmin_sync.routes import router as ingest_router
from app.domains.journal.api.checkins import router as checkins_router
from app.domains.journal.api.notes import router as notes_router
from app.domains.programs.api.programs import router as programs_router
from app.domains.routines.api.routines import router as routines_router
from app.domains.routines.api.today import router as today_router

from ..routers.days import router as days_router
from ..routers.events import router as events_router


def register_routers(app: FastAPI) -> None:
    """Register all API routers."""
    app.include_router(ingest_router)
    app.include_router(dashboard_router)
    app.include_router(days_router)
    app.include_router(wellness_router)
    app.include_router(sleep_router)
    app.include_router(daily_aggregates_router)
    app.include_router(skin_temp_router)
    app.include_router(heart_rate_router)
    app.include_router(hrv_router)
    app.include_router(stress_router)
    app.include_router(body_battery_router)
    app.include_router(events_router)
    app.include_router(assistant_router)
    app.include_router(assistant_artifact_bundles_router)
    app.include_router(assistant_artifacts_router)
    app.include_router(cards_router)
    app.include_router(profile_router)
    app.include_router(routines_router)
    app.include_router(checkins_router)
    app.include_router(notes_router)
    app.include_router(experiments_router)
    app.include_router(target_metrics_router)
    app.include_router(programs_router)
    app.include_router(today_router)
