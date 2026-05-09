"""Metric analysis read use cases for Garmin analytics routes.

Application functions load the needed marts and choose cache keys. The returned
chart series, distributions, and boxplots are computed in `domain.analysis`.
"""

from app.domains.garmin_analytics.application.dependencies import BiometricReadRepository
from app.domains.garmin_analytics.contracts import (
    BodyBatteryAnalysisResponse,
    HeartRateAnalysisResponse,
    HRDistributionResponse,
    HrvAnalysisResponse,
    SleepAnalysisResponse,
    StressAnalysisResponse,
)
from app.domains.garmin_analytics.domain.analysis.body_battery import (
    compute_body_battery_analysis,
)
from app.domains.garmin_analytics.domain.analysis.heart_rate import (
    compute_heart_rate_analysis,
    compute_hr_distribution,
)
from app.domains.garmin_analytics.domain.analysis.hrv import compute_hrv_analysis
from app.domains.garmin_analytics.domain.analysis.sleep import compute_sleep_analysis
from app.domains.garmin_analytics.domain.analysis.stress import compute_stress_analysis
from app.infra import cache


def load_sleep_analysis(repo: BiometricReadRepository) -> SleepAnalysisResponse:
    return cache.cached(
        cache.SLEEP_ANALYSIS,
        lambda: compute_sleep_analysis(repo.load_daily_metrics()),
    )


def load_stress_analysis(repo: BiometricReadRepository) -> StressAnalysisResponse:
    return cache.cached(
        cache.STRESS_ANALYSIS,
        lambda: compute_stress_analysis(repo.load_daily_metrics()),
    )


def load_body_battery_analysis(
    repo: BiometricReadRepository,
) -> BodyBatteryAnalysisResponse:
    return cache.cached(
        cache.BODY_BATTERY_ANALYSIS,
        lambda: compute_body_battery_analysis(repo.load_daily_metrics()),
    )


def load_heart_rate_analysis(repo: BiometricReadRepository) -> HeartRateAnalysisResponse:
    return cache.cached(
        cache.HR_ANALYSIS,
        lambda: compute_heart_rate_analysis(
            repo.load_wellness(),
            repo.load_sleep(),
            repo.load_daily_metrics(),
        ),
    )


def load_hr_distribution(
    repo: BiometricReadRepository,
    date: str,
) -> HRDistributionResponse:
    wellness_days = repo.load_wellness(date)
    if not wellness_days:
        return HRDistributionResponse(date=date, bins=[], sample_count=0)

    readings = [(r.value, r.timestamp) for r in wellness_days[0].heart_rate if r.value > 0]
    return HRDistributionResponse(
        date=date,
        bins=compute_hr_distribution(readings),
        sample_count=len(readings),
    )


def load_hrv_analysis(repo: BiometricReadRepository) -> HrvAnalysisResponse:
    return cache.cached(
        cache.HRV_ANALYSIS,
        lambda: compute_hrv_analysis(repo.load_daily_metrics()),
    )
