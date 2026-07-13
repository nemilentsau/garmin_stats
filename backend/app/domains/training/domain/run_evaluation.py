"""Pure execution and tracked-run measurement policy."""

from collections.abc import Iterable
from statistics import fmean

from app.domains.training.contracts import (
    AllPredicate,
    AnyPredicate,
    Cmp,
    GateResult,
    NotPredicate,
    Predicate,
    SegmentSpec,
    TrainingCardStatus,
    TrainingExecutionEvaluation,
    TrainingMeasurementEvaluation,
    TrainingMeasurementGate,
    TrainingMeasurementObservations,
    TrainingMeasurementWarning,
    TrainingRunEvidence,
    V3Card,
)

_LTHR_CAPTURE_ID = "cap.lthr.final20_hr"
_LTHR_EFFORT_SECONDS = 30 * 60
_LTHR_FINAL_SECONDS = 20 * 60


def effective_execution(
    *, log_status: TrainingCardStatus, run_id: str | None
) -> TrainingExecutionEvaluation:
    """Resolve completion without changing the persisted card log.

    `run_id` is retained only when the tracked run is the evidence that
    completed an otherwise-pending card. Manual outcomes expose any separate
    run association through the card projection, not this evaluation.
    """
    if log_status != "pending":
        return TrainingExecutionEvaluation(status=log_status, source="manual_log")
    if run_id is not None:
        return TrainingExecutionEvaluation(
            status="completed", source="tracked_run", run_id=run_id
        )
    return TrainingExecutionEvaluation(status="pending", source="none")


def evaluate_run_measurement(
    *,
    card: V3Card,
    segments: list[SegmentSpec],
    evidence: TrainingRunEvidence,
) -> TrainingMeasurementEvaluation | None:
    """Evaluate objective evidence for the declared LTHR measurement protocol.

    This stage deliberately stops before subjective review. A known authored
    gate failure is terminal, while passes and unavailable signals remain
    awaiting review and cannot update an estimator.
    """
    if card.contract.kind != "measurement" or not any(
        field.id == _LTHR_CAPTURE_ID for field in card.capture
    ):
        return None

    effort_window = _lthr_effort_window(segments)
    final_window = (
        None
        if effort_window is None
        else (effort_window[1] - _LTHR_FINAL_SECONDS, effort_window[1])
    )
    final20_hr = (
        None if final_window is None else _mean_hr(evidence, window=final_window)
    )
    strap_validity = (
        None
        if final_window is None
        else _strap_validity(evidence, window=final_window)
    )
    threshold_pace = (
        None
        if effort_window is None
        else _threshold_pace(evidence, window=effort_window)
    )
    stand_time = (
        0.0 if effort_window is None else _stand_time(evidence, window=effort_window)
    )
    observations = TrainingMeasurementObservations(
        final20_hr_bpm=final20_hr,
        threshold_pace_min_per_mi=threshold_pace,
        strap_validity_pct=strap_validity,
        effort_stand_time_s=stand_time,
    )
    signal_values: dict[str, bool | int | float | str | None] = {
        "env.dew_point": evidence.dew_point_c,
        "strap.validity_pct": strap_validity,
    }
    gates = [
        _evaluate_gate(comparison, signal_values.get(comparison.signal))
        for predicate in card.contract.quality_gate
        for comparison in _comparison_leaves(predicate)
    ]
    warnings = (
        [
            TrainingMeasurementWarning(
                code="uninterrupted_effort",
                value=stand_time,
                message=f"{stand_time:g} seconds standing during the 30-minute effort.",
            )
        ]
        if stand_time > 0
        else []
    )
    status = "failed" if any(gate.result == "fail" for gate in gates) else "awaiting_review"
    return TrainingMeasurementEvaluation(
        status=status,
        run_id=evidence.summary.run_id,
        observations=observations,
        gates=gates,
        warnings=warnings,
    )


def _lthr_effort_window(segments: list[SegmentSpec]) -> tuple[float, float] | None:
    elapsed_s = 0.0
    for segment in segments:
        duration_s = (segment.duration_min or 0.0) * 60
        start_s = elapsed_s
        elapsed_s += duration_s
        if duration_s == _LTHR_EFFORT_SECONDS and segment.intensity.rpe is not None:
            return start_s, elapsed_s
    return None


def _series_covers(
    elapsed_s: list[int], *, window: tuple[float, float]
) -> bool:
    return bool(elapsed_s) and min(elapsed_s) <= window[0] and max(elapsed_s) >= window[1]


def _mean_hr(
    evidence: TrainingRunEvidence, *, window: tuple[float, float]
) -> int | None:
    if not _series_covers(evidence.elapsed_s, window=window):
        return None
    values = [
        heart_rate
        for elapsed, heart_rate in zip(
            evidence.elapsed_s, evidence.heart_rate_bpm, strict=False
        )
        if window[0] <= elapsed < window[1] and heart_rate is not None
    ]
    return None if not values else round(fmean(values))


def _strap_validity(
    evidence: TrainingRunEvidence, *, window: tuple[float, float]
) -> float | None:
    if evidence.summary.hr_source != "strap" or not _series_covers(
        evidence.elapsed_s, window=window
    ):
        return None
    covered_seconds = {
        elapsed
        for elapsed, heart_rate in zip(
            evidence.elapsed_s, evidence.heart_rate_bpm, strict=False
        )
        if window[0] <= elapsed < window[1] and heart_rate is not None
    }
    if not covered_seconds:
        return None
    return round(len(covered_seconds) / _LTHR_FINAL_SECONDS, 3)


def _threshold_pace(
    evidence: TrainingRunEvidence, *, window: tuple[float, float]
) -> float | None:
    start_distance = _distance_at(evidence, target_s=window[0])
    end_distance = _distance_at(evidence, target_s=window[1])
    if start_distance is None or end_distance is None:
        return None
    effort_distance = end_distance - start_distance
    if effort_distance <= 0:
        return None
    effort_minutes = (window[1] - window[0]) / 60
    return round(effort_minutes / effort_distance, 2)


def _distance_at(evidence: TrainingRunEvidence, *, target_s: float) -> float | None:
    valid_points = [
        (elapsed, distance)
        for elapsed, distance in zip(
            evidence.elapsed_s, evidence.distance_mi, strict=False
        )
        if distance is not None
    ]
    exact = next(
        (distance for elapsed, distance in valid_points if elapsed == target_s), None
    )
    if exact is not None:
        return exact
    before = max(
        ((elapsed, distance) for elapsed, distance in valid_points if elapsed < target_s),
        default=None,
    )
    after = min(
        ((elapsed, distance) for elapsed, distance in valid_points if elapsed > target_s),
        default=None,
    )
    if before is None or after is None or after[0] == before[0]:
        return None
    fraction = (target_s - before[0]) / (after[0] - before[0])
    return before[1] + fraction * (after[1] - before[1])


def _stand_time(
    evidence: TrainingRunEvidence, *, window: tuple[float, float]
) -> float:
    return sum(
        max(0.0, min(span.end_s, window[1]) - max(span.start_s, window[0]))
        for span in evidence.run_walk_spans
        if span.span_type == "stand"
    )


def _comparison_leaves(predicate: Predicate) -> Iterable[Cmp]:
    if isinstance(predicate, Cmp):
        yield predicate
    elif isinstance(predicate, (AllPredicate, AnyPredicate)):
        children = predicate.all if isinstance(predicate, AllPredicate) else predicate.any
        for child in children:
            yield from _comparison_leaves(child)
    elif isinstance(predicate, NotPredicate):
        yield from _comparison_leaves(predicate.not_)


def _evaluate_gate(
    comparison: Cmp, value: bool | int | float | str | None
) -> TrainingMeasurementGate:
    result: GateResult = (
        "unknown" if value is None else _compare(value, comparison.op, comparison.value)
    )
    return TrainingMeasurementGate(
        signal=comparison.signal,
        value=value,
        operator=comparison.op,
        threshold=comparison.value,
        result=result,
    )


def _compare(
    value: bool | int | float | str,
    operator: str,
    threshold: bool | int | float | str | list[bool | int | float | str],
) -> GateResult:
    try:
        if operator == "in":
            if not isinstance(threshold, list):
                return "unknown"
            passes = value in threshold
        elif operator == "==":
            passes = value == threshold
        elif isinstance(threshold, list):
            return "unknown"
        else:
            if isinstance(value, str):
                if not isinstance(threshold, str):
                    return "unknown"
                passes = _ordered_compare(value, operator, threshold)
            else:
                if isinstance(threshold, str):
                    return "unknown"
                passes = _ordered_compare(value, operator, threshold)
            if passes is None:
                return "unknown"
    except TypeError:
        return "unknown"
    return "pass" if passes else "fail"


def _ordered_compare(
    value: bool | int | float | str,
    operator: str,
    threshold: bool | int | float | str,
) -> bool | None:
    if isinstance(value, str):
        if not isinstance(threshold, str):
            return None
        if operator == "<":
            return value < threshold
        if operator == "<=":
            return value <= threshold
        if operator == ">":
            return value > threshold
        if operator == ">=":
            return value >= threshold
        return None
    if isinstance(threshold, str):
        return None
    if operator == "<":
        return value < threshold
    if operator == "<=":
        return value <= threshold
    if operator == ">":
        return value > threshold
    if operator == ">=":
        return value >= threshold
    return None
