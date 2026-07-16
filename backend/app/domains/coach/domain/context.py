"""Deterministic descriptive summaries over existing application read models."""

from __future__ import annotations

from app.contracts.base import StrictDefaultsRequired
from app.domains.garmin_analytics.contracts import (
    RunDetailResponse,
    RunListItem,
)
from app.domains.garmin_health.contracts import DailyMetric
from app.domains.training.contracts import (
    RecoveryContract,
    SegmentPrescription,
    TrainingTodayCard,
)

_DIGEST_LINE_MAX = 600
_NOTE_EXCERPT_MAX = 160


class WholeSessionComparison(StrictDefaultsRequired):
    prescribed_distance_mi: float | None = None
    estimated_duration_min: float | None = None
    actual_distance_mi: float | None = None
    actual_duration_min: float | None = None


class HistoricalRunContext(StrictDefaultsRequired):
    run: RunListItem
    detail: RunDetailResponse
    training_card: TrainingTodayCard | None = None
    morning_metric: DailyMetric | None = None
    comparison: WholeSessionComparison


def _sum_present(values: list[float | None]) -> float | None:
    present = [value for value in values if value is not None]
    return None if not present else round(sum(present), 2)


def compare_whole_session(
    *,
    detail: RunDetailResponse,
    training_card: TrainingTodayCard | None,
) -> WholeSessionComparison:
    """Compare only whole-session distance/duration without assigning a verdict."""
    segments = [] if training_card is None else training_card.segments_display
    timer_time_s = detail.session.timer_time_s
    return WholeSessionComparison(
        prescribed_distance_mi=_sum_present(
            [segment.distance_mi for segment in segments]
        ),
        estimated_duration_min=(
            None
            if training_card is None
            else training_card.est_duration_min
            if training_card.est_duration_min is not None
            else _sum_present([segment.duration_min for segment in segments])
        ),
        actual_distance_mi=detail.display.distance_mi,
        actual_duration_min=(
            None if timer_time_s is None else round(timer_time_s / 60, 1)
        ),
    )


def _number(value: float | int | None) -> str:
    if value is None:
        return "unknown"
    if float(value).is_integer():
        return str(int(value))
    return f"{value:g}"


def _comparison_text(comparison: WholeSessionComparison) -> str:
    distance = (
        f"distance {_number(comparison.actual_distance_mi)} mi"
        if comparison.actual_distance_mi is not None
        else "distance unknown"
    )
    duration = (
        f"duration {_number(comparison.actual_duration_min)} min"
        if comparison.actual_duration_min is not None
        else "duration unknown"
    )
    target_parts: list[str] = []
    if comparison.prescribed_distance_mi is not None:
        target_parts.append(f"prescribed {_number(comparison.prescribed_distance_mi)} mi")
    if comparison.estimated_duration_min is not None:
        target_parts.append(f"estimated {_number(comparison.estimated_duration_min)} min")
    target = "unplanned" if not target_parts else " / ".join(target_parts)
    return f"{distance}; {duration}; {target}"


def _cap(text: str, maximum: int) -> str:
    if len(text) <= maximum:
        return text
    return text[: maximum - 1].rstrip() + "…"


def _intensity_interpretation(card: TrainingTodayCard) -> list[str]:
    """Describe only calibrated comparisons supported by the imported card."""
    lines = ["", "## Intensity interpretation"]
    prescription = card.card.prescription
    if isinstance(prescription, SegmentPrescription):
        hr_ranges = [
            segment.intensity.hr_range
            for segment in prescription.segments
            if segment.intensity.hr_range is not None
        ]
        authored_zones = list(
            dict.fromkeys(
                segment.intensity.zone
                for segment in prescription.segments
                if segment.intensity.zone is not None
            )
        )
    else:
        hr_ranges = []
        authored_zones = []

    if hr_ranges:
        lines.extend(
            f"- Authored HR target: {low}–{high} bpm" for low, high in hr_ranges
        )
        lines.append("- Direct HR comparison: available")
    elif authored_zones:
        lines.append(
            "- Authored target: "
            + ", ".join(authored_zones)
            + " (uncalibrated training label)"
        )
        lines.append(
            "- Direct Garmin-zone compliance: unavailable; "
            "no zone-system mapping was imported"
        )
    else:
        lines.append("- Authored HR target: none")
        lines.append("- Direct HR comparison: unavailable")

    contract = card.card.contract
    if isinstance(contract, RecoveryContract) and contract.load_ceiling.rpe_max is not None:
        ceiling = contract.load_ceiling.rpe_max
        observed = None if card.capture is None else card.capture.rpe
        exceedance = (
            "not established"
            if observed is None
            else "yes"
            if observed > ceiling
            else "no"
        )
        lines.append(
            f"- RPE ceiling: {_number(ceiling)}; "
            f"observed RPE: {_number(observed)}; exceedance: {exceedance}"
        )
    return lines


def digest_line(context: HistoricalRunContext) -> str:
    """Render one bounded historical-run line from existing display fields."""
    run = context.run
    parts = [
        f"- {run.session_date} {run.id}",
        run.activity_name or "Unnamed run",
        _comparison_text(context.comparison),
        (
            f"pace {_number(run.pace_min_per_mi)} min/mi"
            if run.pace_min_per_mi is not None
            else "pace unknown"
        ),
        (
            f"HR {run.avg_heart_rate_bpm} bpm ({run.hr_source or 'source unknown'})"
            if run.avg_heart_rate_bpm is not None
            else "HR unknown"
        ),
        f"load {_number(run.training_load)}",
        f"aerobic effect {_number(run.aerobic_training_effect)}",
    ]
    card = context.training_card
    if card is not None:
        parts.append(f"training {card.status}")
        if card.segments_display:
            parts.append(
                "segments "
                + "; ".join(
                    f"{segment.label}: {segment.detail}"
                    for segment in card.segments_display
                )
            )
        if card.notes:
            parts.append(f"note {_cap(card.notes, _NOTE_EXCERPT_MAX)}")
    return _cap(" | ".join(parts), _DIGEST_LINE_MAX)


def digest_markdown(contexts: list[HistoricalRunContext]) -> str:
    """Render every supplied run in caller-provided chronology."""
    return "# Recent run digest\n\n" + "\n".join(
        digest_line(context) for context in contexts
    )


def run_summary_markdown(context: HistoricalRunContext) -> str:
    """Render medium-detail run evidence with imperial display values first."""
    session = context.detail.session
    display = context.detail.display
    lines = [
        f"# {session.activity_name or 'Run'} — {session.session_date}",
        "",
        "## Display evidence (imperial)",
        f"- Distance: {_number(display.distance_mi)} mi",
        f"- Pace: {_number(display.pace_min_per_mi)} min/mi",
        f"- Duration: {_number(context.comparison.actual_duration_min)} min",
        f"- Elevation gain: {_number(display.total_ascent_ft)} ft",
        f"- Temperature: {_number(display.avg_temperature_f)} °F",
        f"- Average HR: {_number(session.avg_heart_rate_bpm)} bpm",
        f"- HR source: {session.hr_source or 'unknown'}",
        f"- Training load: {_number(session.training_load)}",
        f"- Aerobic training effect: {_number(session.aerobic_training_effect)}",
        f"- Anaerobic training effect: {_number(session.anaerobic_training_effect)}",
        f"- VO2max: {_number(session.vo2max)}",
        (
            "- Stamina potential: "
            f"{_number(display.stamina_beginning_potential_pct)}% → "
            f"{_number(display.stamina_ending_potential_pct)}%"
        ),
        f"- Stamina minimum: {_number(display.stamina_min_pct)}%",
        "",
        "## Heart-rate zones",
        *(
            ["- Unknown"]
            if not display.heart_rate_zones
            else [
                f"- {zone.label}: {_number(zone.duration_s)} s"
                for zone in display.heart_rate_zones
            ]
        ),
        "",
        "## Whole-session comparison",
        f"- {_comparison_text(context.comparison)}",
    ]
    card = context.training_card
    if card is not None:
        lines.extend(_intensity_interpretation(card))
        lines.extend(
            [
                "",
                "## Training association",
                f"- Occurrence: {card.occurrence_key}",
                f"- Training status: {card.status}",
                f"- Variant: {card.variant_taken or 'unknown'}",
                f"- Captured RPE: {_number(None if card.capture is None else card.capture.rpe)}",
                "- Prescription: "
                + (
                    "; ".join(
                        f"{segment.label}: {segment.detail}"
                        for segment in card.segments_display
                    )
                    or "none"
                ),
                f"- Notes: {card.notes or 'none'}",
            ]
        )
    return "\n".join(lines) + "\n"


def laps_markdown(context: HistoricalRunContext) -> str:
    """Render lap evidence with existing imperial lap projections."""
    display_by_index = {
        lap.lap_index: lap for lap in context.detail.display.lap_display
    }
    lines = ["# Laps", ""]
    if not context.detail.laps:
        return "# Laps\n\nNo lap data.\n"
    for lap in context.detail.laps:
        display = display_by_index.get(lap.lap_index)
        lines.append(
            "- Lap "
            f"{lap.lap_index}: "
            f"{_number(None if display is None else display.distance_mi)} mi; "
            f"{_number(None if display is None else display.pace_min_per_mi)} min/mi; "
            f"HR {_number(lap.avg_heart_rate_bpm)} bpm; "
            f"cadence {_number(lap.avg_cadence_spm)} spm"
        )
    return "\n".join(lines) + "\n"


def capabilities_markdown() -> str:
    """Describe the evidence boundary the model must obey."""
    return """# Evidence capabilities

Authoritative existing evidence: run/session/lap/series fields; imperial display projections;
time in zones; training load/effect; stamina; VO2max; training association/status/notes/RPE;
recovery state/change/evidence; daily metrics and user-authored check-ins/notes.

Descriptive v1 transformations: whole-session distance/duration comparison,
missingness/source labels, compact formatting, backend-owned heart-rate sample
distributions, and plot rendering. Garmin time-in-zone buckets remain descriptive;
authored zone labels are not mapped to Garmin zones unless imported evidence says so.

Unavailable in v1: heat-adjusted fitness, pace-at-fixed-HR adaptation, causal lifting
interference, plateau detection, predicted recovery, segment-matched compliance, and any
undeclared estimator. Treat apparent patterns as observations or hypotheses, not facts.
"""
