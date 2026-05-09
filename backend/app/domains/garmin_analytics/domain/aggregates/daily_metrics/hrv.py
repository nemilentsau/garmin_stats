"""HRV daily aggregate calculations."""

from app.domains.garmin_analytics.contracts import DailyHrvStats, DayHrv

UNFAVORABLE_HRV_STATUSES = {"Low", "Unbalanced"}


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


def is_balanced_hrv_status(raw: str | None) -> bool:
    return normalize_hrv_status(raw) == "Balanced"


def is_unfavorable_hrv_status(raw: str | None) -> bool:
    return normalize_hrv_status(raw) in UNFAVORABLE_HRV_STATUSES


def classify_hrv_recovery(*, delta: float | None, status: str | None) -> str | None:
    """Classify HRV recovery from nightly delta and Garmin status."""
    if delta is None:
        return None
    if delta <= -10 or is_unfavorable_hrv_status(status):
        return "suppressed"
    if delta <= -5:
        return "below_baseline"
    if delta >= 8:
        return "elevated"
    return "stable"


def compute_daily_hrv(hrv: DayHrv) -> DailyHrvStats:
    summary = hrv.hrv_summaries[0] if hrv.hrv_summaries else None
    return DailyHrvStats(
        weekly_avg=summary.weekly_average if summary else None,
        nightly_avg=summary.last_night_average if summary else None,
        status=normalize_hrv_status(summary.status) if summary else None,
    )
