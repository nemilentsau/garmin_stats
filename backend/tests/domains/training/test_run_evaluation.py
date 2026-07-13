"""Pure execution and measurement evaluation for scheduled training cards."""

from collections.abc import Sequence

import pytest

from app.domains.training.contracts import (
    AllPredicate,
    AnalysisContract,
    AnyPredicate,
    CaptureField,
    Cmp,
    DoseSpec,
    MeasurementContract,
    NotPredicate,
    Predicate,
    RecoveryContract,
    SegmentIntensity,
    SegmentPrescription,
    SegmentSpec,
    TrainingCardStatus,
    TrainingRunActivitySummary,
    TrainingRunEvidence,
    TrainingRunWalkSpan,
    V3Card,
)
from app.domains.training.domain.run_evaluation import (
    effective_execution,
    evaluate_run_measurement,
)


def _segments() -> list[SegmentSpec]:
    return [
        SegmentSpec(
            label="warmup",
            intensity=SegmentIntensity(zone="Z1-Z2"),
            duration_min=15,
        ),
        SegmentSpec(
            label="30 min max sustainable effort",
            intensity=SegmentIntensity(rpe=9),
            duration_min=30,
        ),
        SegmentSpec(
            label="cooldown",
            intensity=SegmentIntensity(zone="Z1"),
            duration_min=10,
        ),
    ]


def _card(
    *,
    measurement: bool = True,
    capture_id: str = "cap.lthr.final20_hr",
    gates: list[Predicate] | None = None,
) -> V3Card:
    segments = _segments()
    quality_gate: list[Predicate]
    if gates is None:
        quality_gate = [
            Cmp(signal="env.dew_point", op="<=", value=22),
            Cmp(signal="strap.validity_pct", op=">=", value=0.95),
        ]
    else:
        quality_gate = list(gates)
    contract = (
        MeasurementContract(
            kind="measurement",
            estimand="LTHR (bpm), heat-season conditions; threshold pace secondary",
            quality_gate=quality_gate,
            on_fail="retry_backup",
        )
        if measurement
        else RecoveryContract(
            kind="recovery", load_ceiling=DoseSpec(duration_min=55)
        )
    )
    return V3Card(
        id="not-a-date-or-special-name",
        bundle_id="running.v3",
        name="Ordinary-looking run",
        contract=contract,
        prescription=SegmentPrescription(segments=segments),
        capture=[
            CaptureField(
                id=capture_id,
                type="number",
                contract=AnalysisContract(
                    model_id="est.lthr", decision_informed="zone anchoring"
                ),
            )
        ],
    )


def _evidence(
    *,
    end_s: int = 3300,
    hr_source: str | None = "strap",
    dew_point_c: float | None = 20,
    heart_rate_bpm: Sequence[int | None] | None = None,
    distance_mi: Sequence[float | None] | None = None,
    spans: list[TrainingRunWalkSpan] | None = None,
) -> TrainingRunEvidence:
    elapsed_s = list(range(end_s + 1))
    return TrainingRunEvidence(
        summary=TrainingRunActivitySummary(
            run_id="r1",
            session_date="2026-07-13",
            start_time_local="2026-07-13T06:00:00",
            hr_source=hr_source,
        ),
        elapsed_s=elapsed_s,
        distance_mi=list(distance_mi)
        if distance_mi is not None
        else [second * (4.2 / 1800) for second in elapsed_s],
        heart_rate_bpm=list(heart_rate_bpm)
        if heart_rate_bpm is not None
        else [160 for _ in elapsed_s],
        run_walk_spans=spans or [],
        dew_point_c=dew_point_c,
    )


def _gate_result(evaluation, signal: str) -> str:
    return next(gate.result for gate in evaluation.gates if gate.signal == signal)


def _not(predicate: Predicate) -> NotPredicate:
    return NotPredicate.model_validate({"not": predicate})


@pytest.mark.parametrize("status", ["completed", "partial", "skipped"])
def test_manual_status_remains_authoritative_when_run_is_associated(
    status: TrainingCardStatus,
):
    execution = effective_execution(log_status=status, run_id="r1")

    assert execution.status == status
    assert execution.source == "manual_log"
    assert execution.run_id is None


def test_pending_status_becomes_completed_when_run_is_associated():
    execution = effective_execution(log_status="pending", run_id="r1")

    assert execution.status == "completed"
    assert execution.source == "tracked_run"
    assert execution.run_id == "r1"


def test_pending_status_remains_pending_without_associated_run():
    execution = effective_execution(log_status="pending", run_id=None)

    assert execution.status == "pending"
    assert execution.source == "none"
    assert execution.run_id is None


def test_declared_lthr_capture_computes_exact_windows_and_stays_awaiting_review():
    evaluation = evaluate_run_measurement(
        card=_card(), segments=_segments(), evidence=_evidence()
    )

    assert evaluation is not None
    assert evaluation.observations.final20_hr_bpm == 160
    assert evaluation.observations.threshold_pace_min_per_mi == 7.14
    assert evaluation.observations.strap_validity_pct == 1.0
    assert evaluation.observations.effort_stand_time_s == 0
    assert evaluation.status == "awaiting_review"
    assert evaluation.estimator_eligible is False
    assert evaluation.retry_required is False
    assert _gate_result(evaluation, "env.dew_point") == "pass"
    assert _gate_result(evaluation, "strap.validity_pct") == "pass"


def test_lthr_selection_uses_contract_and_capture_instead_of_card_name_or_id():
    selected = evaluate_run_measurement(
        card=_card(), segments=_segments(), evidence=_evidence()
    )
    wrong_capture = evaluate_run_measurement(
        card=_card(capture_id="cap.run.rpe"),
        segments=_segments(),
        evidence=_evidence(),
    )
    non_measurement = evaluate_run_measurement(
        card=_card(measurement=False), segments=_segments(), evidence=_evidence()
    )

    assert selected is not None
    assert wrong_capture is None
    assert non_measurement is None


@pytest.mark.parametrize(
    ("covered_seconds", "expected_validity", "expected_result", "expected_status"),
    [
        (1141, 0.951, "pass", "awaiting_review"),
        (1140, 0.95, "pass", "awaiting_review"),
        (1139, 0.949, "fail", "failed"),
    ],
)
def test_strap_coverage_boundary_controls_authored_gate(
    covered_seconds: int,
    expected_validity: float,
    expected_result: str,
    expected_status: str,
):
    evidence = _evidence()
    for second in range(1500 + covered_seconds, 2700):
        evidence.heart_rate_bpm[second] = None

    evaluation = evaluate_run_measurement(
        card=_card(), segments=_segments(), evidence=evidence
    )

    assert evaluation is not None
    assert evaluation.observations.strap_validity_pct == expected_validity
    assert _gate_result(evaluation, "strap.validity_pct") == expected_result
    assert evaluation.status == expected_status


@pytest.mark.parametrize(
    "evidence",
    [
        _evidence(hr_source="wrist"),
        _evidence(heart_rate_bpm=[None] * 3301),
        _evidence(end_s=2600),
    ],
    ids=["wrist-hr", "no-hr", "short-stream"],
)
def test_indeterminable_strap_coverage_is_an_unknown_gate(
    evidence: TrainingRunEvidence,
):
    evaluation = evaluate_run_measurement(
        card=_card(), segments=_segments(), evidence=evidence
    )

    assert evaluation is not None
    assert evaluation.observations.strap_validity_pct is None
    assert _gate_result(evaluation, "strap.validity_pct") == "unknown"
    assert evaluation.status == "awaiting_review"


def test_missing_dew_point_is_an_unknown_gate():
    evaluation = evaluate_run_measurement(
        card=_card(), segments=_segments(), evidence=_evidence(dew_point_c=None)
    )

    assert evaluation is not None
    assert _gate_result(evaluation, "env.dew_point") == "unknown"
    assert evaluation.status == "awaiting_review"


def test_final20_window_is_complete_without_an_out_of_window_sample():
    evaluation = evaluate_run_measurement(
        card=_card(), segments=_segments(), evidence=_evidence(end_s=2699)
    )

    assert evaluation is not None
    assert evaluation.observations.final20_hr_bpm == 160
    assert evaluation.observations.strap_validity_pct == 1.0
    assert _gate_result(evaluation, "strap.validity_pct") == "pass"


def test_final20_hr_averages_non_null_samples_and_rounds_to_whole_bpm():
    evidence = _evidence()
    for second in range(1500, 2100):
        evidence.heart_rate_bpm[second] = 159
    for second in range(2100, 2700):
        evidence.heart_rate_bpm[second] = 160
    evidence.heart_rate_bpm[1700] = None
    evidence.heart_rate_bpm[2300] = None

    evaluation = evaluate_run_measurement(
        card=_card(), segments=_segments(), evidence=evidence
    )

    assert evaluation is not None
    assert evaluation.observations.final20_hr_bpm == 160


def test_exact_effort_boundary_distance_samples_compute_threshold_pace():
    evidence = _evidence(distance_mi=[None] * 3301)
    evidence.distance_mi[900] = 2.0
    evidence.distance_mi[2700] = 6.2

    evaluation = evaluate_run_measurement(
        card=_card(), segments=_segments(), evidence=evidence
    )

    assert evaluation is not None
    assert evaluation.observations.threshold_pace_min_per_mi == 7.14


def test_effort_boundary_distance_is_linearly_interpolated():
    evidence = _evidence(distance_mi=[None] * 3301)
    for second in (899, 901, 2699, 2701):
        evidence.distance_mi[second] = second * (4.2 / 1800)

    evaluation = evaluate_run_measurement(
        card=_card(), segments=_segments(), evidence=evidence
    )

    assert evaluation is not None
    assert evaluation.observations.threshold_pace_min_per_mi == 7.14


@pytest.mark.parametrize("missing_side", ["before-start", "after-end"])
def test_pace_is_unavailable_without_valid_samples_surrounding_each_boundary(
    missing_side: str,
):
    evidence = _evidence(distance_mi=[None] * 3301)
    evidence.distance_mi[901] = 2.1
    evidence.distance_mi[2699] = 6.1
    if missing_side != "before-start":
        evidence.distance_mi[899] = 1.9
    if missing_side != "after-end":
        evidence.distance_mi[2701] = 6.3

    evaluation = evaluate_run_measurement(
        card=_card(), segments=_segments(), evidence=evidence
    )

    assert evaluation is not None
    assert evaluation.observations.threshold_pace_min_per_mi is None


def test_stand_spans_are_clipped_to_effort_and_exposed_as_a_warning():
    spans = [
        TrainingRunWalkSpan(span_type="stand", start_s=800, end_s=1000),
        TrainingRunWalkSpan(span_type="stand", start_s=1200, end_s=1250),
        TrainingRunWalkSpan(span_type="walk", start_s=1300, end_s=1400),
        TrainingRunWalkSpan(span_type="stand", start_s=2600, end_s=2800),
        TrainingRunWalkSpan(span_type="stand", start_s=2800, end_s=2900),
    ]

    evaluation = evaluate_run_measurement(
        card=_card(), segments=_segments(), evidence=_evidence(spans=spans)
    )

    assert evaluation is not None
    assert evaluation.observations.effort_stand_time_s == 250
    assert [warning.code for warning in evaluation.warnings] == [
        "uninterrupted_effort"
    ]
    assert evaluation.warnings[0].value == 250
    assert evaluation.status == "awaiting_review"


@pytest.mark.parametrize(
    ("operator", "threshold", "dew_point", "expected"),
    [
        ("<", 21, 20, "pass"),
        ("<", 20, 20, "fail"),
        ("<=", 20, 20, "pass"),
        ("<=", 19, 20, "fail"),
        (">", 19, 20, "pass"),
        (">", 20, 20, "fail"),
        (">=", 20, 20, "pass"),
        (">=", 21, 20, "fail"),
        ("==", 20, 20, "pass"),
        ("==", 21, 20, "fail"),
        ("in", [19, 20], 20, "pass"),
        ("in", [18, 19], 20, "fail"),
    ],
)
def test_authored_comparison_operators_are_evaluated_generically(
    operator: str,
    threshold: int | list[int],
    dew_point: int,
    expected: str,
):
    gate = Cmp.model_validate(
        {"signal": "env.dew_point", "op": operator, "value": threshold}
    )

    evaluation = evaluate_run_measurement(
        card=_card(gates=[gate]),
        segments=_segments(),
        evidence=_evidence(dew_point_c=dew_point),
    )

    assert evaluation is not None
    assert evaluation.gates[0].operator == operator
    assert evaluation.gates[0].threshold == threshold
    assert evaluation.gates[0].value == dew_point
    assert evaluation.gates[0].result == expected


@pytest.mark.parametrize(
    ("predicate", "expected_leaf_results", "expected_status"),
    [
        (
            AllPredicate(
                all=[
                    Cmp(signal="env.dew_point", op="<=", value=22),
                    Cmp(signal="future.signal", op="==", value=1),
                ]
            ),
            ["pass", "unknown"],
            "awaiting_review",
        ),
        (
            AllPredicate(
                all=[
                    Cmp(signal="env.dew_point", op=">", value=22),
                    Cmp(signal="future.signal", op="==", value=1),
                ]
            ),
            ["fail", "unknown"],
            "failed",
        ),
        (
            AnyPredicate(
                any=[
                    Cmp(signal="env.dew_point", op="<=", value=22),
                    Cmp(signal="env.dew_point", op=">", value=22),
                ]
            ),
            ["pass", "fail"],
            "awaiting_review",
        ),
        (
            AnyPredicate(
                any=[
                    Cmp(signal="env.dew_point", op=">", value=22),
                    Cmp(signal="future.signal", op="==", value=1),
                ]
            ),
            ["fail", "unknown"],
            "awaiting_review",
        ),
        (
            AnyPredicate(
                any=[
                    Cmp(signal="env.dew_point", op=">", value=22),
                    Cmp(signal="env.dew_point", op="==", value=21),
                ]
            ),
            ["fail", "fail"],
            "failed",
        ),
        (
            _not(Cmp(signal="env.dew_point", op=">", value=22)),
            ["fail"],
            "awaiting_review",
        ),
        (
            _not(Cmp(signal="env.dew_point", op="<=", value=22)),
            ["pass"],
            "failed",
        ),
        (
            _not(Cmp(signal="future.signal", op="==", value=1)),
            ["unknown"],
            "awaiting_review",
        ),
    ],
    ids=[
        "all-pass-unknown",
        "all-fail-unknown",
        "any-pass-fail",
        "any-fail-unknown",
        "any-all-fail",
        "not-fail",
        "not-pass",
        "not-unknown",
    ],
)
def test_root_predicate_semantics_control_hard_gate_failure(
    predicate: Predicate,
    expected_leaf_results: list[str],
    expected_status: str,
):
    evaluation = evaluate_run_measurement(
        card=_card(gates=[predicate]),
        segments=_segments(),
        evidence=_evidence(),
    )

    assert evaluation is not None
    assert [gate.result for gate in evaluation.gates] == expected_leaf_results
    assert evaluation.status == expected_status


def test_unknown_signal_and_missing_series_are_represented_without_failure():
    evidence = TrainingRunEvidence(
        summary=TrainingRunActivitySummary(
            run_id="r1",
            session_date="2026-07-13",
            start_time_local="2026-07-13T06:00:00",
            hr_source="strap",
        ),
        elapsed_s=[],
        distance_mi=[],
        heart_rate_bpm=[],
        run_walk_spans=[],
    )
    evaluation = evaluate_run_measurement(
        card=_card(gates=[Cmp(signal="future.signal", op="==", value=1)]),
        segments=_segments(),
        evidence=evidence,
    )

    assert evaluation is not None
    assert evaluation.observations.final20_hr_bpm is None
    assert evaluation.observations.threshold_pace_min_per_mi is None
    assert evaluation.observations.strap_validity_pct is None
    assert evaluation.gates[0].value is None
    assert evaluation.gates[0].result == "unknown"
    assert evaluation.status == "awaiting_review"
