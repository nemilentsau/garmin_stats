"""Sleep daily aggregate calculations."""

from app.domains.garmin_health.contracts import DailySleepStats, DaySleep


def compute_daily_sleep(sleep: DaySleep) -> DailySleepStats:
    assessment = sleep.sleep_assessments[0] if sleep.sleep_assessments else None
    return DailySleepStats(
        score=assessment.overall_score if assessment else None,
        deep_score=assessment.deep_sleep_score if assessment else None,
        rem_score=assessment.rem_sleep_score if assessment else None,
    )
