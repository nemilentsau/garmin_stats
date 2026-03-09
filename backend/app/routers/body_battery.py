"""Body Battery HTTP routes."""

from fastapi import APIRouter

from ..models import BodyBatteryAnalysisResponse
from ..services.body_battery_analysis import load_body_battery_analysis

router = APIRouter(prefix="/api/body-battery", tags=["body-battery"])


@router.get("/analysis", response_model=BodyBatteryAnalysisResponse)
def get_body_battery_analysis():
    """Return period-level body battery analysis (trend, weekly boxplots)."""
    return load_body_battery_analysis()
