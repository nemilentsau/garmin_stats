"""Router registration for the FastAPI app."""

from fastapi import FastAPI

from app.core.profile.api import router as profile_router
from app.domains.artifacts.routes import (
    assistant_artifact_bundles_router,
    assistant_artifacts_router,
    cards_router,
)
from app.domains.assistant.api.threads import router as assistant_router
from app.domains.experiments.routes import experiments_router, target_metrics_router
from app.domains.garmin_analytics.routes import (
    body_battery_router,
    daily_aggregates_router,
    dashboard_router,
    heart_rate_router,
    hrv_router,
    pulse_ox_router,
    respiration_router,
    skin_temp_router,
    sleep_router,
    stress_router,
)
from app.domains.garmin_sync.routes import router as ingest_router
from app.domains.journal.api.checkins import router as checkins_router
from app.domains.journal.api.notes import router as notes_router
from app.domains.programs.routes import router as programs_router
from app.domains.routines.routes import routines_router, today_router
from app.realtime.routes import router as events_router


def register_routers(app: FastAPI) -> None:
    """Register all API routers."""
    app.include_router(ingest_router)
    app.include_router(dashboard_router)
    app.include_router(sleep_router)
    app.include_router(daily_aggregates_router)
    app.include_router(skin_temp_router)
    app.include_router(heart_rate_router)
    app.include_router(hrv_router)
    app.include_router(stress_router)
    app.include_router(body_battery_router)
    app.include_router(respiration_router)
    app.include_router(pulse_ox_router)
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
