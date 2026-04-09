"""Router registration for the FastAPI app."""

from fastapi import FastAPI

from ..routers.assistant import router as assistant_router
from ..routers.assistant_artifact_bundles import router as assistant_artifact_bundles_router
from ..routers.assistant_artifacts import router as assistant_artifacts_router
from ..routers.body_battery import router as body_battery_router
from ..routers.cards import router as cards_router
from ..routers.checkins import router as checkins_router
from ..routers.daily_aggregates import router as daily_aggregates_router
from ..routers.dashboard import router as dashboard_router
from ..routers.days import router as days_router
from ..routers.events import router as events_router
from ..routers.experiments import router as experiments_router
from ..routers.heart_rate import router as heart_rate_router
from ..routers.hrv import router as hrv_router
from ..routers.ingest import router as ingest_router
from ..routers.notes import router as notes_router
from ..routers.profile import router as profile_router
from ..routers.programs import router as programs_router
from ..routers.routines import router as routines_router
from ..routers.skin_temp import router as skin_temp_router
from ..routers.sleep import router as sleep_router
from ..routers.stress import router as stress_router
from ..routers.target_metrics import router as target_metrics_router
from ..routers.today import router as today_router
from ..routers.wellness import router as wellness_router


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
