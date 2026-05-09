"""Contracts for experiment definitions, exposures, and analysis."""

from __future__ import annotations

from typing import Literal

from app.contracts.base import AutoTotalResponse, DefaultsRequired

ExperimentStatus = Literal["draft", "active", "completed"]
ExperimentAdherenceState = Literal["full", "partial", "missed", "completed", "unknown"]
ExperimentReportConfidence = Literal["insufficient", "low", "moderate", "high"]
OutcomeMetricDirection = Literal["higher_is_better", "lower_is_better"]
ExperimentDesignType = Literal["ab_intervention"]


class OutcomeMetric(DefaultsRequired):
    path: str
    direction: OutcomeMetricDirection = "higher_is_better"
    min_effect_size: float = 0.2


class ExperimentDesign(DefaultsRequired):
    type: ExperimentDesignType = "ab_intervention"
    baseline_start_date: str | None = None
    baseline_end_date: str | None = None
    treatment_start_date: str | None = None
    treatment_end_date: str | None = None
    baseline_duration_days: int | None = None
    expected_lag_days: list[int] = [0]
    min_adherence_pct: float = 0.70


class Experiment(DefaultsRequired):
    id: str
    name: str
    status: ExperimentStatus = "draft"
    goal: str | None = None
    hypothesis: str | None = None
    design: ExperimentDesign | None = None
    linked_routine_ids: list[str] = []
    outcome_metrics: list[OutcomeMetric] = []
    confounder_watch: list[str] = []
    confounder_notes: str | None = None
    expected_lag_days: list[int] = []
    priority: int = 0


class ExperimentExposure(DefaultsRequired):
    id: str
    experiment_id: str
    date: str
    exposure_score: float | None = None
    adherence_state: ExperimentAdherenceState = "unknown"
    linked_routine_entry_ids: list[str] = []
    notes: str | None = None

    @staticmethod
    def auto_id(experiment_id: str, date: str) -> str:
        return f"exposure:auto:{experiment_id}:{date}"


class ExperimentMetricEffect(DefaultsRequired):
    metric: str
    baseline_value: float | None = None
    current_value: float | None = None
    delta_abs: float | None = None
    delta_pct: float | None = None
    sample_count: int = 0


class ExperimentReport(DefaultsRequired):
    id: str
    experiment_id: str
    report_date: str
    summary: str | None = None
    confidence: ExperimentReportConfidence = "insufficient"
    confounders: list[str] = []
    effects: list[ExperimentMetricEffect] = []


class MetricLagResult(DefaultsRequired):
    lag_days: int
    treatment_start_effective: str
    baseline_mean: float
    baseline_sd: float
    baseline_n: int
    treatment_mean: float
    treatment_sd: float
    treatment_n: int
    delta_abs: float
    delta_pct: float
    cohens_d: float
    hedges_g: float
    nap: float
    nap_interpretation: str
    p_value_permutation: float
    p_value_welch: float
    baseline_trend_slope: float
    baseline_trend_p: float
    autocorrelation_lag1_baseline: float
    autocorrelation_lag1_treatment: float
    direction_correct: bool


class MetricAnalysis(DefaultsRequired):
    path: str
    direction: str
    lag_results: list[MetricLagResult]
    best_lag: int
    best_result: MetricLagResult


class ConfounderCheck(DefaultsRequired):
    path: str
    source: str
    baseline_mean: float | None = None
    treatment_mean: float | None = None
    delta_pct: float | None = None
    is_significant: bool = False
    note: str = ""
    baseline_flag_days: int | None = None
    treatment_flag_days: int | None = None
    baseline_total_days: int | None = None
    treatment_total_days: int | None = None


class AdherenceDayEntry(DefaultsRequired):
    date: str
    state: ExperimentAdherenceState
    exposure_score: float | None = None


class ExperimentAnalysis(DefaultsRequired):
    experiment_id: str
    analysis_date: str
    phase: str
    days_in_baseline: int
    days_in_treatment: int
    adherence_rate: float
    adherence_by_day: list[AdherenceDayEntry]
    metrics: list[MetricAnalysis]
    confounders: list[ConfounderCheck]
    overall_confidence: ExperimentReportConfidence
    summary: str


class ExperimentWithAnalysis(DefaultsRequired):
    experiment: Experiment
    analysis: ExperimentAnalysis | None = None


class ExperimentPreviewIssue(DefaultsRequired):
    level: Literal["error", "warning"]
    message: str


class ExperimentPreviewResponse(DefaultsRequired):
    valid: bool
    issues: list[ExperimentPreviewIssue] = []
    experiment: Experiment | None = None


class ExperimentAnalysisRefreshResponse(DefaultsRequired):
    refreshed: int


class TargetMetricDefinition(DefaultsRequired):
    key: str
    label: str
    path: str
    unit: str


class ExperimentsResponse(AutoTotalResponse, items_field="experiments"):
    experiments: list[ExperimentWithAnalysis] = []
    total: int = 0


class TargetMetricsResponse(AutoTotalResponse, items_field="metrics"):
    metrics: list[TargetMetricDefinition] = []
    total: int = 0
