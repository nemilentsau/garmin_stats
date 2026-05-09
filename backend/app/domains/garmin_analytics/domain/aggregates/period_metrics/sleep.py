"""Sleep period summary calculations from raw assessments."""

from app.domains.garmin_analytics.contracts import PeriodSleepStats
from app.domains.garmin_health.contracts import DayData
from app.utils.numeric import safe_avg


def compute_period_sleep(days: list[DayData]) -> PeriodSleepStats:
    """Compute period sleep stats from raw sleep assessments."""
    scores: list[float] = []
    deep_scores: list[float] = []
    for day in days:
        for assessment in day.sleep.sleep_assessments:
            if assessment.overall_score is not None:
                scores.append(assessment.overall_score)
            if assessment.deep_sleep_score is not None:
                deep_scores.append(assessment.deep_sleep_score)

    return PeriodSleepStats(
        avg_score=safe_avg(scores),
        avg_deep_score=safe_avg(deep_scores),
        days_tracked=len(scores),
    )
