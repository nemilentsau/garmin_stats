"""Pure execution and tracked-run measurement policy."""

from statistics import fmean

from app.domains.training.contracts import (
    AllPredicate,
    AnyPredicate,
    Cmp,
    GateResult,
    Predicate,
    SegmentSpec,
    TrainingCardStatus,
    TrainingExecutionEvaluation,
    TrainingMeasurementAssessment,
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
        return TrainingExecutionEvaluation(status="completed", source="tracked_run", run_id=run_id)
    return TrainingExecutionEvaluation(status="pending", source="none")


def finalize_measurement(
    objective: TrainingMeasurementEvaluation,
    assessment: TrainingMeasurementAssessment | None,
    required_measurement: bool,
) -> TrainingMeasurementEvaluation:
    """Combine objective hard gates with the exact coach judgment.

    Objective evidence remains immutable in the returned projection. A known
    failed authored gate is terminal; otherwise the coach judgment supplies
    validity, while an absent judgment stays awaiting review.
    """
    hard_gate_failed = objective.status == "failed"
    status = (
        "failed"
        if hard_gate_failed
        else "awaiting_review"
        if assessment is None
        else assessment.status
    )
    return objective.model_copy(
        update={
            "status": status,
            "rationale": assessment.rationale if assessment is not None else None,
            "assessment_source_id": (assessment.source_id if assessment is not None else None),
            "estimator_eligible": status == "valid",
            "retry_required": (required_measurement and status in {"provisional", "failed"}),
        }
    )


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
    final20_hr = None if final_window is None else _mean_hr(evidence, window=final_window)
    strap_validity = (
        None if final_window is None else _strap_validity(evidence, window=final_window)
    )
    threshold_pace = (
        None if effort_window is None else _threshold_pace(evidence, window=effort_window)
    )
    stand_time = 0.0 if effort_window is None else _stand_time(evidence, window=effort_window)
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
    evaluated_roots = [
        _evaluate_predicate(predicate, signal_values) for predicate in card.contract.quality_gate
    ]
    gates = [gate for _, root_gates in evaluated_roots for gate in root_gates]
    warnings: list[TrainingMeasurementWarning] = []
    if stand_time > 0:
        warnings.append(
            TrainingMeasurementWarning(
                code="uninterrupted_effort",
                value=stand_time,
                message=f"{stand_time:g} seconds standing during the 30-minute effort.",
            )
        )
    unavailable_signals = sorted(
        {gate.signal for gate in gates if gate.result == "unknown" and gate.value is None}
    )
    warnings.extend(
        TrainingMeasurementWarning(
            code="signal_unavailable",
            message=(
                f"{signal} is not available from tracked data;"
                " assess this gate manually before accepting the measurement."
            ),
        )
        for signal in unavailable_signals
    )
    status = (
        "failed"
        if any(root_result == "fail" for root_result, _ in evaluated_roots)
        else "awaiting_review"
    )
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


def _series_covers(elapsed_s: list[int], *, window: tuple[float, float]) -> bool:
    """Return whether sample extent covers every second in a half-open window."""
    return bool(elapsed_s) and min(elapsed_s) <= window[0] and max(elapsed_s) >= window[1] - 1


def _mean_hr(evidence: TrainingRunEvidence, *, window: tuple[float, float]) -> int | None:
    if not _series_covers(evidence.elapsed_s, window=window):
        return None
    values = [
        heart_rate
        for elapsed, heart_rate in zip(evidence.elapsed_s, evidence.heart_rate_bpm, strict=False)
        if window[0] <= elapsed < window[1] and heart_rate is not None
    ]
    return None if not values else round(fmean(values))


def _strap_validity(evidence: TrainingRunEvidence, *, window: tuple[float, float]) -> float | None:
    if evidence.summary.hr_source != "strap" or not _series_covers(
        evidence.elapsed_s, window=window
    ):
        return None
    recorded: set[int] = set()
    with_hr: set[int] = set()
    for elapsed, heart_rate in zip(evidence.elapsed_s, evidence.heart_rate_bpm, strict=False):
        if window[0] <= elapsed < window[1]:
            recorded.add(elapsed)
            if heart_rate is not None:
                with_hr.add(elapsed)
    if not recorded:
        return None
    # Recording pauses remove seconds from the timeline entirely; strap quality
    # is dropout among the seconds the device actually recorded.
    return round(len(with_hr) / len(recorded), 3)


def _threshold_pace(evidence: TrainingRunEvidence, *, window: tuple[float, float]) -> float | None:
    start_distance = _distance_at(evidence, target_s=window[0])
    end_distance = _distance_at(evidence, target_s=window[1])
    if end_distance is None:
        # A run stopped exactly at the effort end has no sample after the
        # boundary; accept the last sample inside the same one-second
        # tolerance _series_covers already applies to coverage.
        end_distance = _distance_at(evidence, target_s=window[1] - 1)
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
        for elapsed, distance in zip(evidence.elapsed_s, evidence.distance_mi, strict=False)
        if distance is not None
    ]
    exact = next((distance for elapsed, distance in valid_points if elapsed == target_s), None)
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


def _stand_time(evidence: TrainingRunEvidence, *, window: tuple[float, float]) -> float:
    return sum(
        max(0.0, min(span.end_s, window[1]) - max(span.start_s, window[0]))
        for span in evidence.run_walk_spans
        if span.span_type == "stand"
    )


def _evaluate_predicate(
    predicate: Predicate,
    signal_values: dict[str, bool | int | float | str | None],
) -> tuple[GateResult, list[TrainingMeasurementGate]]:
    if isinstance(predicate, Cmp):
        gate = _evaluate_gate(predicate, signal_values.get(predicate.signal))
        return gate.result, [gate]
    if isinstance(predicate, (AllPredicate, AnyPredicate)):
        children = predicate.all if isinstance(predicate, AllPredicate) else predicate.any
        evaluated_children = [_evaluate_predicate(child, signal_values) for child in children]
        results = [result for result, _ in evaluated_children]
        gates = [gate for _, child_gates in evaluated_children for gate in child_gates]
        if isinstance(predicate, AllPredicate):
            if "fail" in results:
                return "fail", gates
            return ("unknown" if "unknown" in results else "pass"), gates
        if "pass" in results:
            return "pass", gates
        return ("unknown" if "unknown" in results else "fail"), gates

    child_result, gates = _evaluate_predicate(predicate.not_, signal_values)
    if child_result == "pass":
        return "fail", gates
    if child_result == "fail":
        return "pass", gates
    return "unknown", gates


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
