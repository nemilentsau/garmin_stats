"""HRV daily aggregate calculations."""

from app.domains.garmin_analytics.contracts import DailyHrvStats, DayHrv

from .heart_rate import normalize_hrv_status


def compute_daily_hrv(hrv: DayHrv) -> DailyHrvStats:
    summary = hrv.hrv_summaries[0] if hrv.hrv_summaries else None
    return DailyHrvStats(
        weekly_avg=summary.weekly_average if summary else None,
        nightly_avg=summary.last_night_average if summary else None,
        status=normalize_hrv_status(summary.status) if summary else None,
    )
