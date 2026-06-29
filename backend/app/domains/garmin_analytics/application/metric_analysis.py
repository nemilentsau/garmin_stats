"""Metric analysis read use cases for Garmin analytics routes.

Application functions load the needed marts and choose cache keys. The returned
chart series, distributions, and boxplots are computed in `domain.analysis`.
"""

from app.domains.garmin_analytics.application.dependencies import BiometricReadRepository
from app.domains.garmin_analytics.contracts import (
    BASELINE_WINDOW_DEFAULT,
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
from app.domains.garmin_analytics.domain.analysis.hrv import (
    compute_nightly_hrv_trend,
    compute_pattern_windows,
)
from app.domains.garmin_analytics.domain.analysis.sleep import compute_sleep_analysis
from app.domains.garmin_analytics.domain.analysis.stress import compute_stress_analysis
from app.infra import cache


def load_sleep_analysis(repo: BiometricReadRepository) -> SleepAnalysisResponse:
    """Load cached sleep trend and weekly distribution analysis."""
    return cache.cached(
        cache.SLEEP_ANALYSIS,
        lambda: compute_sleep_analysis(repo.load_daily_metrics()),
    )


def load_stress_analysis(repo: BiometricReadRepository) -> StressAnalysisResponse:
    """Load cached stress trend and weekly distribution analysis."""
    return cache.cached(
        cache.STRESS_ANALYSIS,
        lambda: compute_stress_analysis(repo.load_daily_metrics()),
    )


def load_body_battery_analysis(
    repo: BiometricReadRepository,
) -> BodyBatteryAnalysisResponse:
    """Load cached Body Battery trend and weekly distribution analysis."""
    return cache.cached(
        cache.BODY_BATTERY_ANALYSIS,
        lambda: compute_body_battery_analysis(repo.load_daily_metrics()),
    )


def load_heart_rate_analysis(repo: BiometricReadRepository) -> HeartRateAnalysisResponse:
    """Load cached heart-rate trend, circadian, and distribution analysis."""
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
    """Load one day's heart-rate readings as histogram bins."""
    wellness_days = repo.load_wellness(date)
    if not wellness_days:
        return HRDistributionResponse(date=date, bins=[], sample_count=0)

    readings = [(r.value, r.timestamp) for r in wellness_days[0].heart_rate if r.value > 0]
    return HRDistributionResponse(
        date=date,
        bins=compute_hr_distribution(readings),
        sample_count=len(readings),
    )


def load_hrv_analysis(
    repo: BiometricReadRepository, baseline: int = BASELINE_WINDOW_DEFAULT
) -> HrvAnalysisResponse:
    """Load cached HRV trend and weekday-pattern analysis.

    The nightly trend's band depends on the baseline window, so it is cached per window.
    The weekday pattern windows are baseline-independent, so they are cached once under a
    single key and reused across windows — avoiding the triple compute and storage the old
    combined per-window key incurred. Generation-based invalidation in ``cache.cached`` still
    refreshes both on re-ingest.

    The mart is read ONCE here and fed to both cache-miss computes, so the per-window trend and
    the shared weekday patterns in a single response always come from one metrics snapshot. The
    two computes are cached under separate keys; reading the mart inside each lambda instead would
    let a re-ingest (``cache.invalidate``) land between them and return a response that mixes two
    ingest generations (trend from before, patterns from after). ``load_daily_metrics`` is itself
    cached, so this single eager read is one dict lookup on the hot path.
    """
    metrics = repo.load_daily_metrics()
    trend = cache.cached(
        f"{cache.HRV_TREND}:{baseline}",
        lambda: compute_nightly_hrv_trend(metrics, window=baseline),
    )
    patterns = cache.cached(
        cache.HRV_PATTERNS,
        lambda: compute_pattern_windows(metrics),
    )
    return HrvAnalysisResponse(nightly_trend=trend, pattern_windows=patterns)
