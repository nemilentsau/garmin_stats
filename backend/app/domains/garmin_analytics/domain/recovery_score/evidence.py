"""Assemble the recovery score series + evidence rows from daily metrics.

This composes the recovery-score domain into the data the dashboard overview shows:
- a per-day score series (raw + seeded MA7 + the typical band) over a display window;
- one evidence row per axis metric for the latest day (value, personal baseline, the
  raw per-metric z and its recovery direction, coverage, source type, tab link, and a
  short inline sparkline).

It deliberately returns plain dataclasses, not Pydantic; mapping to the API contract
happens in `domain/dashboard.py`. Source-type labels and tab links are fixed maps. The
metric extraction mirrors the persisted `DailyMetric` shape. Validated logic per the
2026-06-11 finding runs (see the sibling modules)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from app.domains.garmin_health.contracts import DailyMetric
from app.utils.numeric import optional_float, safe_avg

from .normalization import expanding_baseline_median, expanding_robust_z
from .smoothing import BAND_SEED_DAYS, SEED_DAYS, seeded_ma7, seeded_sd
from .thresholds import _BAND
from .weighting import RECOVERY_SIGNS, weighted_recovery_score

# Axis metrics in display order (resting HR, HR-avg, respiration, body battery, HRV,
# stress, sleep) — the seven inputs to the recovery score.
METRIC_GETTERS: dict[str, Callable[[DailyMetric], float | None]] = {
    "heart_rate_resting": lambda m: optional_float(m.heart_rate.resting),
    "heart_rate_avg": lambda m: m.heart_rate.avg,
    "respiration_avg": lambda m: m.respiration.avg,
    "body_battery_avg": lambda m: m.body_battery.avg,
    "hrv_nightly_avg": lambda m: m.hrv.nightly_avg,
    "stress_avg": lambda m: m.stress.avg,
    "sleep_score": lambda m: optional_float(m.sleep.score),
}

METRIC_LABELS: dict[str, str] = {
    "heart_rate_resting": "Resting HR",
    "heart_rate_avg": "HR Avg",
    "respiration_avg": "Respiration",
    "body_battery_avg": "Body Battery",
    "hrv_nightly_avg": "Nightly HRV",
    "stress_avg": "Stress",
    "sleep_score": "Sleep Score",
}

METRIC_UNITS: dict[str, str] = {
    "heart_rate_resting": "bpm",
    "heart_rate_avg": "bpm",
    "respiration_avg": "brpm",
    "body_battery_avg": "",
    "hrv_nightly_avg": "ms",
    "stress_avg": "",
    "sleep_score": "",
}

# native = source-native measurement; device = device-computed from native readings;
# derived = Garmin-proprietary composite (stress/BB/HRV/sleep share an HRV derivation).
SOURCE_TYPE: dict[str, str] = {
    "respiration_avg": "native",
    "heart_rate_resting": "device",
    "heart_rate_avg": "device",
    "stress_avg": "derived",
    "body_battery_avg": "derived",
    "hrv_nightly_avg": "derived",
    "sleep_score": "derived",
}

TAB_HREF: dict[str, str] = {
    "heart_rate_resting": "/heart-rate",
    "heart_rate_avg": "/heart-rate",
    "respiration_avg": "/respiration",
    "body_battery_avg": "/body-battery",
    "hrv_nightly_avg": "/hrv",
    "stress_avg": "/stress",
    "sleep_score": "/sleep",
}

_DISPLAY_DAYS = 366  # up to a full year of trajectory (frontend toggles 90/180/360)
_SPARKLINE_DAYS = 30


@dataclass(frozen=True, slots=True)
class SparkPoint:
    date: str
    value: float | None


@dataclass(frozen=True, slots=True)
class ScorePoint:
    date: str
    raw: float | None
    ma7: float | None
    band_lo: float | None
    band_hi: float | None
    baseline_lo: float
    baseline_hi: float


@dataclass(frozen=True, slots=True)
class EvidenceRowData:
    metric: str
    label: str
    source_type: str
    tab_href: str
    latest_value: float | None
    unit: str
    baseline: float | None
    delta_z: float | None  # raw z (metric vs its baseline, natural direction)
    delta_raw: float | None  # latest_value - baseline, raw units
    recovery_good: bool | None  # whether this move helps recovery (signed z > 0)
    coverage_ok: bool  # latest value present
    degraded: bool  # the latest day's composite ran on < 7 inputs
    sparkline: list[SparkPoint]  # recent raw values for the inline mini-chart


@dataclass(frozen=True, slots=True)
class DriverSeriesData:
    """Per-metric value/baseline/z over the display window, aligned to the score dates.

    Powers trajectory hover-brushing: the frontend joins these with the latest-day
    evidence metadata (label/unit/tab) to show 'what moved it' for any hovered day.
    """

    metric: str
    values: list[float | None]
    baselines: list[float | None]
    deltas_z: list[float | None]
    recovery_good: list[bool | None]


@dataclass(frozen=True, slots=True)
class RecoveryComputation:
    date: str
    score_z: float | None
    delta7_z: float | None
    delta1_z: float | None
    score_series: list[ScorePoint]
    evidence: list[EvidenceRowData]
    driver_series: list[DriverSeriesData]


def _band_edge(center: float | None, spread: float | None, sign: int) -> float | None:
    """ma7 +/- sd, or None if either is missing for this day."""
    if center is None or spread is None:
        return None
    return center + sign * spread


def _delta1(raw_scores: list[float | None], index: int) -> float | None:
    """Single-day change of the raw score (today minus yesterday), if both present."""
    if index < 1:
        return None
    today, yesterday = raw_scores[index], raw_scores[index - 1]
    if today is None or yesterday is None:
        return None
    return today - yesterday


def _delta7(raw_scores: list[float | None], index: int) -> float | None:
    """7-day mean ending at index minus the prior 7-day mean (>=5 valid days each)."""
    if index < 13:
        return None
    recent = [v for v in raw_scores[index - 6: index + 1] if v is not None]
    prior = [v for v in raw_scores[index - 13: index - 6] if v is not None]
    if len(recent) < 5 or len(prior) < 5:
        return None
    recent_avg, prior_avg = safe_avg(recent), safe_avg(prior)
    if recent_avg is None or prior_avg is None:
        return None
    return recent_avg - prior_avg


def compute_recovery(metrics: list[DailyMetric]) -> RecoveryComputation | None:
    """Compute the score series + latest-day evidence from ordered daily metrics."""
    if not metrics:
        return None

    series_by_metric = {
        key: [getter(metric) for metric in metrics]
        for key, getter in METRIC_GETTERS.items()
    }
    z_by_metric = {
        key: expanding_robust_z(series) for key, series in series_by_metric.items()
    }
    baseline_by_metric = {
        key: expanding_baseline_median(series)
        for key, series in series_by_metric.items()
    }

    n = len(metrics)
    raw_scores: list[float | None] = []
    input_counts: list[int] = []
    for i in range(n):
        raw_z = {key: z_by_metric[key][i] for key in METRIC_GETTERS}
        score, count = weighted_recovery_score(raw_z)
        raw_scores.append(score)
        input_counts.append(count)

    display_start = max(0, n - _DISPLAY_DAYS)
    # Two seeds: the 7d average and the 14d SD band need different left-edge fills.
    ma_seed = raw_scores[max(0, display_start - SEED_DAYS):display_start]
    sd_seed = raw_scores[max(0, display_start - BAND_SEED_DAYS):display_start]
    display = raw_scores[display_start:]
    ma7 = seeded_ma7(ma_seed, display)
    sd = seeded_sd(sd_seed, display)

    score_series = [
        ScorePoint(
            date=metrics[display_start + offset].date,
            raw=display[offset],
            ma7=ma7[offset],
            band_lo=_band_edge(ma7[offset], sd[offset], -1),
            band_hi=_band_edge(ma7[offset], sd[offset], +1),
            baseline_lo=-_BAND,
            baseline_hi=_BAND,
        )
        for offset in range(len(display))
    ]

    driver_series = [
        DriverSeriesData(
            metric=key,
            values=series_by_metric[key][display_start:],
            baselines=baseline_by_metric[key][display_start:],
            deltas_z=z_by_metric[key][display_start:],
            recovery_good=[
                None if z is None else (RECOVERY_SIGNS[key] * z) > 0
                for z in z_by_metric[key][display_start:]
            ],
        )
        for key in METRIC_GETTERS
    ]

    latest = n - 1
    spark_start = max(0, n - _SPARKLINE_DAYS)
    evidence = [
        _build_evidence_row(
            key=key,
            metrics=metrics,
            latest=latest,
            spark_start=spark_start,
            raw_value=series_by_metric[key][latest],
            baseline=baseline_by_metric[key][latest],
            raw_z=z_by_metric[key][latest],
            spark_values=series_by_metric[key][spark_start:],
            degraded=input_counts[latest] < len(METRIC_GETTERS),
        )
        for key in METRIC_GETTERS
    ]

    return RecoveryComputation(
        date=metrics[latest].date,
        score_z=raw_scores[latest],
        delta7_z=_delta7(raw_scores, latest),
        delta1_z=_delta1(raw_scores, latest),
        score_series=score_series,
        evidence=evidence,
        driver_series=driver_series,
    )


def _build_evidence_row(
    *,
    key: str,
    metrics: list[DailyMetric],
    latest: int,
    spark_start: int,
    raw_value: float | None,
    baseline: float | None,
    raw_z: float | None,
    spark_values: list[float | None],
    degraded: bool,
) -> EvidenceRowData:
    delta_raw: float | None = None
    if raw_value is not None and baseline is not None:
        delta_raw = raw_value - baseline
    recovery_good = None if raw_z is None else (RECOVERY_SIGNS[key] * raw_z) > 0
    spark_dates = [m.date for m in metrics[spark_start:]]
    sparkline = [
        SparkPoint(date=date, value=value)
        for date, value in zip(spark_dates, spark_values, strict=True)
    ]
    return EvidenceRowData(
        metric=key,
        label=METRIC_LABELS[key],
        source_type=SOURCE_TYPE[key],
        tab_href=TAB_HREF[key],
        latest_value=raw_value,
        unit=METRIC_UNITS[key],
        baseline=baseline,
        delta_z=raw_z,
        delta_raw=delta_raw,
        recovery_good=recovery_good,
        coverage_ok=raw_value is not None,
        degraded=degraded,
        sparkline=sparkline,
    )
