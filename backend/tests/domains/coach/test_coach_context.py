"""Equivalence-class tests for deterministic coach evidence summaries."""

from __future__ import annotations

from app.domains.coach.domain.context import (
    HistoricalRunContext,
    capabilities_markdown,
    compare_whole_session,
    digest_line,
    digest_markdown,
    laps_markdown,
    run_summary_markdown,
)
from app.domains.garmin_analytics.contracts import (
    LapDisplayRow,
    RunDetailResponse,
    RunDisplayStats,
    RunListItem,
)
from app.domains.garmin_health.contracts import (
    RunningActivityLap,
    RunningActivitySession,
    RunningTimeInZones,
)
from app.domains.training.contracts import (
    TrainingCardStatus,
    TrainingExecutionEvaluation,
    TrainingSegmentDisplay,
    TrainingTodayCard,
    V3Card,
)


def _card(
    segments: list[TrainingSegmentDisplay],
    *,
    notes: str | None = None,
    status: TrainingCardStatus = "completed",
    capture_rpe: bool = True,
) -> TrainingTodayCard:
    card = V3Card.model_validate(
        {
            "id": "run.easy",
            "bundle_id": "running.v3",
            "name": "Easy aerobic run",
            "contract": {"kind": "recovery", "load_ceiling": {}},
            "prescription": {
                "segments": [
                    {
                        "label": segment.label,
                        "distance_mi": segment.distance_mi,
                        "duration_min": segment.duration_min,
                        "intensity": {"zone": segment.zone},
                    }
                    for segment in segments
                ]
            },
        }
    )
    return TrainingTodayCard(
        occurrence_key="running.v3:run.easy:d01",
        date="2026-07-11",
        day=1,
        slot="morning",
        bundle_id="running.v3",
        bundle_name="Running",
        card=card,
        segments_display=segments,
        capture_rpe=capture_rpe,
        status=status,
        execution=TrainingExecutionEvaluation(
            status=status,
            source="none" if status == "pending" else "manual_log",
        ),
        notes=notes,
    )


def _detail(
    *,
    distance_mi: float | None = 6.2,
    timer_time_s: float | None = 3000,
    pace_min_per_mi: float | None = 8.1,
) -> RunDetailResponse:
    session = RunningActivitySession(
        id="run-1",
        source_file="run-1.fit",
        session_date="2026-07-11",
        start_time_local="2026-07-11T06:00:00",
        activity_name="Morning Run",
        timer_time_s=timer_time_s,
        avg_heart_rate_bpm=142,
        hr_source="strap",
        training_load=110,
        aerobic_training_effect=3.1,
        anaerobic_training_effect=0.2,
        vo2max=52,
        stamina_beginning_potential_pct=96,
        stamina_ending_potential_pct=78,
        stamina_min_pct=70,
        time_in_zones=RunningTimeInZones(time_in_hr_zone_s=[60, 1200, 1500, 240]),
        has_heart_rate=True,
        has_running_dynamics=True,
    )
    lap = RunningActivityLap(
        lap_index=1,
        timer_time_s=1500,
        avg_heart_rate_bpm=140,
        avg_cadence_spm=174,
    )
    return RunDetailResponse(
        session=session,
        laps=[lap],
        display=RunDisplayStats(
            distance_mi=distance_mi,
            pace_min_per_mi=pace_min_per_mi,
            total_ascent_ft=210,
            avg_temperature_f=72.5,
            stamina_beginning_potential_pct=96,
            stamina_ending_potential_pct=78,
            stamina_min_pct=70,
            lap_display=[
                LapDisplayRow(lap_index=1, distance_mi=3.1, pace_min_per_mi=8.0)
            ],
        ),
    )


def _context(
    *, card: TrainingTodayCard | None, detail: RunDetailResponse | None = None
) -> HistoricalRunContext:
    detail = detail or _detail()
    run = RunListItem(
        id=detail.session.id,
        session_date=detail.session.session_date,
        start_time_local=detail.session.start_time_local,
        activity_name=detail.session.activity_name,
        distance_mi=detail.display.distance_mi,
        timer_time_s=detail.session.timer_time_s,
        pace_min_per_mi=detail.display.pace_min_per_mi,
        avg_heart_rate_bpm=detail.session.avg_heart_rate_bpm,
        hr_source=detail.session.hr_source,
        training_load=detail.session.training_load,
        aerobic_training_effect=detail.session.aerobic_training_effect,
        has_heart_rate=detail.session.has_heart_rate,
        has_running_dynamics=detail.session.has_running_dynamics,
    )
    return HistoricalRunContext(
        run=run,
        detail=detail,
        training_card=card,
        comparison=compare_whole_session(detail=detail, training_card=card),
    )


def test_single_segment_distance_and_duration_are_compared_without_verdict():
    card = _card(
        [
            TrainingSegmentDisplay(
                label="Easy",
                detail="6 mi · 48 min · Z1-Z2",
                distance_mi=6,
                duration_min=48,
                zone="Z1-Z2",
            )
        ]
    )

    comparison = compare_whole_session(detail=_detail(), training_card=card)

    assert comparison.prescribed_distance_mi == 6
    assert comparison.prescribed_duration_min == 48
    assert comparison.actual_distance_mi == 6.2
    assert comparison.actual_duration_min == 50
    assert not hasattr(comparison, "verdict")


def test_multi_segment_intensity_is_described_without_whole_run_range_score():
    card = _card(
        [
            TrainingSegmentDisplay(
                label="Warm-up",
                detail="15 min · Z1-Z2",
                duration_min=15,
                zone="Z1-Z2",
            ),
            TrainingSegmentDisplay(
                label="Threshold",
                detail="20 min · Z4",
                duration_min=20,
                zone="Z4",
            ),
        ]
    )

    line = digest_line(_context(card=card))

    assert "Warm-up: 15 min · Z1-Z2" in line
    assert "Threshold: 20 min · Z4" in line
    assert "in-range" not in line
    assert "% compliant" not in line


def test_unplanned_run_has_actuals_and_no_prescribed_values():
    comparison = compare_whole_session(detail=_detail(), training_card=None)

    assert comparison.prescribed_distance_mi is None
    assert comparison.prescribed_duration_min is None
    assert comparison.actual_distance_mi == 6.2
    assert comparison.actual_duration_min == 50


def test_missing_run_fields_render_as_unknown_not_zero():
    detail = _detail(distance_mi=None, timer_time_s=None, pace_min_per_mi=None)

    line = digest_line(_context(card=None, detail=detail))

    assert "distance unknown" in line
    assert "duration unknown" in line
    assert "pace unknown" in line
    assert "0 mi" not in line


def test_digest_line_uses_existing_imperial_values_and_source_quality():
    line = digest_line(_context(card=None))

    assert "6.2 mi" in line
    assert "8.1 min/mi" in line
    assert "HR 142 bpm (strap)" in line
    assert "load 110" in line


def test_digest_preserves_all_twenty_runs_in_input_order():
    contexts = []
    for index in range(20):
        context = _context(card=None)
        run = context.run.model_copy(
            update={
                "id": f"run-{index:02d}",
                "session_date": f"2026-06-{index + 1:02d}",
            }
        )
        contexts.append(context.model_copy(update={"run": run}))

    digest = digest_markdown(contexts)

    lines = [line for line in digest.splitlines() if line.startswith("- ")]
    assert len(lines) == 20
    assert "run-00" in lines[0]
    assert "run-19" in lines[-1]


def test_digest_caps_each_line_and_preserves_full_note_in_run_summary():
    full_note = "Long note " + "x" * 900
    context = _context(card=_card([], notes=full_note))

    line = digest_line(context)
    summary = run_summary_markdown(context)

    assert len(line) <= 600
    assert full_note not in line
    assert "Long note" in line
    assert full_note in summary


def test_run_summary_contains_load_effect_stamina_zones_and_training_notes():
    context = _context(card=_card([], notes="Legs felt controlled", status="partial"))

    summary = run_summary_markdown(context)
    laps = laps_markdown(context)
    capabilities = capabilities_markdown()

    assert "Training load: 110" in summary
    assert "Aerobic training effect: 3.1" in summary
    assert "Stamina potential: 96% → 78%" in summary
    assert "HR zone seconds: 60, 1200, 1500, 240" in summary
    assert "Training status: partial" in summary
    assert "Legs felt controlled" in summary
    assert "3.1 mi" in laps
    assert "8 min/mi" in laps
    assert "Unavailable in v1" in capabilities
    assert "pace-at-fixed-HR" in capabilities
