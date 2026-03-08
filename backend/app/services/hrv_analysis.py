"""HRV analysis: nightly trend with 7-day MA, weekly boxplots."""

from datetime import date as date_type

from ..infra import cache
from ..infra.database import load_daily_metrics
from ..models import (
    DailyMetric,
    HrvAnalysisResponse,
    NightlyHrvTrendPoint,
    WeeklyHrvBox,
)


def _compute_nightly_hrv_trend(
    metrics: list[DailyMetric],
) -> list[NightlyHrvTrendPoint]:
    """Raw nightly HRV + 7-day trailing moving average."""
    points: list[NightlyHrvTrendPoint] = []
    nightly_values: list[float | None] = [m.hrv.nightly_avg for m in metrics]

    for i, m in enumerate(metrics):
        nightly = nightly_values[i]
        # 7-day trailing window: i-6 to i inclusive
        window_start = max(0, i - 6)
        window = [v for v in nightly_values[window_start : i + 1] if v is not None]
        ma7 = round(sum(window) / len(window), 1) if window else None
        points.append(
            NightlyHrvTrendPoint(
                date=m.date,
                nightly_avg=nightly,
                ma7=ma7,
            )
        )
    return points


def _compute_weekly_hrv_boxplots(
    metrics: list[DailyMetric],
) -> list[WeeklyHrvBox]:
    """Group nightly HRV by ISO week, compute 5-number summary."""
    weeks: dict[str, list[float]] = {}
    for m in metrics:
        if m.hrv.nightly_avg is None:
            continue
        try:
            d = date_type.fromisoformat(m.date)
        except ValueError:
            continue
        iso_year, iso_week, _ = d.isocalendar()
        key = f"{iso_year}-W{iso_week:02d}"
        weeks.setdefault(key, []).append(m.hrv.nightly_avg)

    result: list[WeeklyHrvBox] = []
    for week_key in sorted(weeks):
        vals = sorted(weeks[week_key])
        n = len(vals)
        if n == 0:
            continue

        def percentile(data: list[float], pct: float) -> float:
            k = (len(data) - 1) * pct / 100
            f = int(k)
            c = f + 1
            if c >= len(data):
                return float(data[f])
            return round(data[f] + (k - f) * (data[c] - data[f]), 1)

        result.append(
            WeeklyHrvBox(
                iso_week=week_key,
                min_ms=float(vals[0]),
                q1_ms=percentile(vals, 25),
                median_ms=percentile(vals, 50),
                q3_ms=percentile(vals, 75),
                max_ms=float(vals[-1]),
                day_count=n,
            )
        )
    return result


def load_hrv_analysis() -> HrvAnalysisResponse:
    """Load daily metrics and compute HRV analysis features (cached)."""
    return cache.cached(cache.HRV_ANALYSIS, _compute_hrv_analysis)


def _compute_hrv_analysis() -> HrvAnalysisResponse:
    metrics = load_daily_metrics()
    return HrvAnalysisResponse(
        nightly_trend=_compute_nightly_hrv_trend(metrics),
        weekly_boxplots=_compute_weekly_hrv_boxplots(metrics),
    )
