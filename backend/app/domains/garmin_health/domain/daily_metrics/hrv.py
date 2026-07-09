"""HRV daily metric calculations."""

from app.domains.garmin_health.contracts import DailyHrvStats, DayHrv

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
    """Return whether a raw Garmin HRV status normalizes to Balanced."""
    return normalize_hrv_status(raw) == "Balanced"


def is_unfavorable_hrv_status(raw: str | None) -> bool:
    """Return whether a raw Garmin HRV status indicates low recovery."""
    return normalize_hrv_status(raw) in UNFAVORABLE_HRV_STATUSES


def classify_hrv_recovery(*, delta: float | None) -> str | None:
    """Classify HRV recovery from the nightly-vs-recent-baseline delta alone.

    Tonight's verdict is a "today" signal — it reflects tonight versus the recent
    baseline only. Garmin's multi-day status is a separate trend signal and is
    deliberately NOT folded in here (see docs/reference/HRV_TAB_REFACTOR.md, "Trend vs Today").
    """
    if delta is None:
        return None
    if delta <= -10:
        return "suppressed"
    if delta <= -5:
        return "below_baseline"
    if delta >= 8:
        return "elevated"
    return "stable"


def compute_daily_hrv(hrv: DayHrv) -> DailyHrvStats:
    """Compute persisted daily HRV stats from the first overnight summary."""
    summary = hrv.hrv_summaries[0] if hrv.hrv_summaries else None
    return DailyHrvStats(
        weekly_avg=summary.weekly_average if summary else None,
        nightly_avg=summary.last_night_average if summary else None,
        status=normalize_hrv_status(summary.status) if summary else None,
    )
