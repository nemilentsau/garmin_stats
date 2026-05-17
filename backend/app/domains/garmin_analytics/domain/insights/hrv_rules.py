"""Named HRV insight rules for the selected-day composer.

The public composer in `hrv.py` owns loading selected-day context and response
assembly. This module owns the ordered message rules so threshold policy stays
small, testable, and independent from raw row or repository concerns.
"""

from collections.abc import Callable
from dataclasses import dataclass

from app.domains.garmin_analytics.contracts import (
    HrvDataQuality,
    HrvInsight,
    HrvLongBaseline,
    HrvRecovery,
    HrvStreak,
    HrvTrajectory,
)
from app.domains.garmin_health.contracts import DailyMetric
from app.domains.garmin_health.domain.daily_metrics import is_balanced_hrv_status

_BAD_HRV_STATUSES = frozenset({"Low", "Unbalanced"})
_LOW_RECOVERY_STATUSES = frozenset({"suppressed", "below_baseline"})

_RECOVERY_STATUS_MESSAGES: dict[str, tuple[str, str, str]] = {
    "suppressed": ("warning", "HRV appears suppressed", "Nightly HRV is below expected levels."),
    "below_baseline": ("caution", "HRV is below baseline", "Nightly HRV is mildly below baseline."),
    "elevated": ("good", "HRV is above baseline", "Nightly HRV is above baseline."),
}


@dataclass(frozen=True, slots=True)
class InsightContext:
    """Selected-day data needed by ordered HRV message rules."""

    selected: DailyMetric
    recovery: HrvRecovery
    quality: HrvDataQuality
    resting_delta: float | None
    overnight_stdev: float | None = None
    streak: HrvStreak | None = None
    long_baseline: HrvLongBaseline | None = None
    trajectory: HrvTrajectory | None = None


def recovery_status_rule(ctx: InsightContext) -> HrvInsight | None:
    """Describe the selected day's HRV level versus its recent baseline."""
    message = _RECOVERY_STATUS_MESSAGES.get(ctx.recovery.status or "")
    if message is None:
        return None
    level, title, fallback_detail = message
    delta = ctx.recovery.delta_nightly_from_baseline
    detail = (
        f"Nightly HRV is {delta:+.1f} ms versus the prior 7-day baseline."
        if delta is not None
        else fallback_detail
    )
    return HrvInsight(level=level, title=title, detail=detail)


def acute_weekly_gap_rule(ctx: InsightContext) -> HrvInsight | None:
    """Warn when the selected nightly HRV is well below its weekly average."""
    if ctx.recovery.acute_gap_vs_weekly is None or ctx.recovery.acute_gap_vs_weekly > -8:
        return None
    return HrvInsight(
        level="caution",
        title="Acute recovery is below weekly trend",
        detail=(
            f"Nightly HRV is {ctx.recovery.acute_gap_vs_weekly:+.1f} ms versus weekly average, "
            "which can indicate short-term strain."
        ),
    )


def overnight_volatility_rule(ctx: InsightContext) -> HrvInsight | None:
    """Flag high overnight HRV variance when recovery is already low."""
    if (
        ctx.overnight_stdev is None
        or ctx.overnight_stdev <= 25
        or ctx.recovery.status not in _LOW_RECOVERY_STATUSES
    ):
        return None
    return HrvInsight(
        level="caution",
        title="High overnight HRV volatility",
        detail=(
            f"Overnight HRV stdev is {ctx.overnight_stdev:.1f} ms, suggesting irregular "
            "autonomic activity alongside suppressed recovery."
        ),
    )


def low_status_streak_rule(ctx: InsightContext) -> HrvInsight | None:
    """Warn on three or more consecutive days of low/unbalanced HRV status."""
    if (
        ctx.streak is None
        or ctx.streak.current_status not in _BAD_HRV_STATUSES
        or ctx.streak.streak_days < 3
    ):
        return None
    return HrvInsight(
        level="warning",
        title="Extended low HRV streak",
        detail=(
            f"{ctx.streak.streak_days} consecutive days of "
            f"{ctx.streak.current_status} HRV status. "
            "Consider reviewing recent stressors, sleep, or training load."
        ),
    )


def falling_trajectory_rule(ctx: InsightContext) -> HrvInsight | None:
    """Warn when overnight HRV falls while selected-day recovery is low."""
    if (
        ctx.trajectory is None
        or ctx.trajectory.direction != "falling"
        or ctx.recovery.status not in _LOW_RECOVERY_STATUSES
    ):
        return None
    return HrvInsight(
        level="warning",
        title="HRV declined through the night",
        detail="HRV declined through the night, suggesting disrupted recovery.",
    )


def long_baseline_rule(ctx: InsightContext) -> HrvInsight | None:
    """Flag recent 7-day HRV baseline deterioration versus the 30-day baseline."""
    if (
        ctx.long_baseline is None
        or ctx.long_baseline.delta_7d_vs_30d is None
        or ctx.long_baseline.baseline_30d is None
        or ctx.long_baseline.delta_7d_vs_30d >= -5
    ):
        return None
    return HrvInsight(
        level="caution",
        title="7-day baseline is trending below 30-day average",
        detail=(
            f"Recent 7-day baseline is {ctx.long_baseline.delta_7d_vs_30d:+.1f} ms versus "
            f"30-day average of {ctx.long_baseline.baseline_30d:.1f} ms."
        ),
    )


def sleep_recovery_rule(ctx: InsightContext) -> HrvInsight | None:
    """Warn when low sleep score aligns with lower-than-baseline HRV."""
    sleep_score = ctx.selected.sleep.score
    if (
        sleep_score is None
        or sleep_score >= 70
        or ctx.recovery.status not in _LOW_RECOVERY_STATUSES
    ):
        return None
    return HrvInsight(
        level="warning",
        title="Sleep and HRV both indicate reduced recovery",
        detail=f"Sleep score is {sleep_score}, aligning with lower-than-baseline HRV.",
    )


def resting_hr_divergence_rule(ctx: InsightContext) -> HrvInsight | None:
    """Warn when resting HR rises while HRV is below baseline."""
    if (
        ctx.resting_delta is None
        or ctx.resting_delta < 4
        or ctx.recovery.status not in _LOW_RECOVERY_STATUSES
    ):
        return None
    return HrvInsight(
        level="warning",
        title="Resting HR and HRV are diverging unfavorably",
        detail=(
            f"Resting HR is +{ctx.resting_delta:.1f} bpm versus recent baseline "
            "while HRV is below baseline."
        ),
    )


def stable_recovery_rule(ctx: InsightContext) -> HrvInsight | None:
    """Emit the positive stable message only when no cautionary rule fired."""
    sleep_score = ctx.selected.sleep.score
    if (
        sleep_score is None
        or sleep_score < 80
        or not ctx.selected.hrv.status
        or not is_balanced_hrv_status(ctx.selected.hrv.status)
    ):
        return None
    return HrvInsight(
        level="good",
        title="HRV recovery signals look stable",
        detail="Balanced HRV status and strong sleep score suggest good recovery.",
    )


def low_coverage_rule(ctx: InsightContext) -> HrvInsight | None:
    """Report low selected-day HRV sample coverage after health-state rules."""
    if ctx.quality.sample_count >= 20:
        return None
    return HrvInsight(
        level="info",
        title="Low HRV sample coverage",
        detail=(
            f"Only {ctx.quality.sample_count} intraday HRV values "
            "were available for this day."
        ),
    )


_CAUTIONARY_RULES: tuple[Callable[[InsightContext], HrvInsight | None], ...] = (
    recovery_status_rule,
    acute_weekly_gap_rule,
    overnight_volatility_rule,
    low_status_streak_rule,
    falling_trajectory_rule,
    long_baseline_rule,
    sleep_recovery_rule,
    resting_hr_divergence_rule,
)


def build_hrv_insights(ctx: InsightContext) -> list[HrvInsight]:
    """Apply ordered HRV insight rules for a selected day."""
    insights = [
        insight
        for rule in _CAUTIONARY_RULES
        if (insight := rule(ctx)) is not None
    ]
    if not insights and (stable_insight := stable_recovery_rule(ctx)) is not None:
        insights.append(stable_insight)
    if coverage_insight := low_coverage_rule(ctx):
        insights.append(coverage_insight)
    return insights
