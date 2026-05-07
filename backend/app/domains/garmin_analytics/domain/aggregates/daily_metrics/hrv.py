"""HRV daily aggregate calculations."""

from app.domains.garmin_analytics.contracts import DailyHrvStats, DayHrv


def normalize_hrv_status(raw: str | None) -> str:
    """Normalize Garmin HRV status strings to clean labels."""
    if not raw:
        return "Unknown"
    value = raw.lower()
    if value == "none":
        return "Unknown"
    # "unbalanced" check must precede "balanced" since the latter is a substring.
    if "unbalanced" in value:
        return "Unbalanced"
    if "balanced" in value:
        return "Balanced"
    if "low" in value:
        return "Low"
    if "high" in value:
        return "High"
    return raw.title()


def compute_daily_hrv(hrv: DayHrv) -> DailyHrvStats:
    summary = hrv.hrv_summaries[0] if hrv.hrv_summaries else None
    return DailyHrvStats(
        weekly_avg=summary.weekly_average if summary else None,
        nightly_avg=summary.last_night_average if summary else None,
        status=normalize_hrv_status(summary.status) if summary else None,
    )
