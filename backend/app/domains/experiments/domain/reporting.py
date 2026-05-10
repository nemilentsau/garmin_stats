"""Confidence and summary text policy for experiment reports.

Reporting policy turns metric effects, adherence, sample size, and confounder
checks into a confidence label and compact user-facing summary. Statistical
threshold constants stay close to this policy so report language does not drift.
"""

from __future__ import annotations

from app.domains.experiments.contracts import (
    ConfounderCheck,
    Experiment,
    ExperimentReportConfidence,
    MetricAnalysis,
)

from .statistics import NAP_LARGE, NAP_MEDIUM, P_HIGH, P_MODERATE

_MIN_DAYS_INSUFFICIENT = 7
_MIN_ADHERENCE_INSUFFICIENT = 0.50
_ADHERENCE_HIGH = 0.85
_ADHERENCE_MODERATE = 0.70
_BASELINE_HIGH = 21


def classify_confidence(
    metrics: list[MetricAnalysis],
    confounders: list[ConfounderCheck],
    adherence_rate: float,
    baseline_n: int,
    treatment_n: int,
) -> ExperimentReportConfidence:
    """Classify report confidence from samples, adherence, effects, and confounders."""
    if baseline_n < _MIN_DAYS_INSUFFICIENT or treatment_n < _MIN_DAYS_INSUFFICIENT:
        return "insufficient"
    if adherence_rate < _MIN_ADHERENCE_INSUFFICIENT:
        return "insufficient"

    best_results = [metric.best_result for metric in metrics]
    has_major_confounder = any(confounder.is_significant for confounder in confounders)
    best_nap = max((result.nap for result in best_results), default=0.5)
    best_p = min((result.p_value_permutation for result in best_results), default=1.0)

    if (
        best_nap >= NAP_LARGE
        and best_p < P_HIGH
        and adherence_rate >= _ADHERENCE_HIGH
        and not has_major_confounder
        and baseline_n >= _BASELINE_HIGH
    ):
        return "high"
    if (
        best_nap >= NAP_MEDIUM
        and best_p < P_MODERATE
        and adherence_rate >= _ADHERENCE_MODERATE
        and not has_major_confounder
    ):
        return "moderate"
    return "low"


def generate_summary(
    experiment: Experiment,
    confidence: ExperimentReportConfidence,
    metrics: list[MetricAnalysis],
    phase: str,
) -> str:
    """Generate a compact summary sentence for the primary outcome metric."""
    if not metrics:
        return f"Experiment '{experiment.name}' has no analysable metrics yet."

    primary = metrics[0]
    result = primary.best_result
    direction_word = "improved" if result.direction_correct else "worsened"

    if phase == "collecting_baseline":
        return f"Collecting baseline data for '{experiment.name}'."

    if confidence == "insufficient":
        return (
            f"Insufficient data for '{experiment.name}' — "
            f"{result.baseline_n} baseline days, {result.treatment_n} treatment days."
        )

    return (
        f"{primary.path} {direction_word} by {abs(result.delta_pct):.1f}% "
        f"(Hedges' g={result.hedges_g}, NAP={result.nap} "
        f"[{result.nap_interpretation}], p={result.p_value_permutation}). "
        f"Confidence: {confidence}."
    )
