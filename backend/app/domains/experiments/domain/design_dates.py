"""Experiment design date resolution and validation.

This module owns the pure date policy for experiment previews and imports:
explicit baseline/treatment windows, routine-derived windows, and ordering
validation. Preview orchestration supplies routine lookup and read models, but
date mutation stays isolated here by returning copied design contracts.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date as date_type
from datetime import timedelta
from typing import Protocol

from app.domains.experiments.contracts import ExperimentDesign, ExperimentPreviewIssue


class RoutineDateWindow(Protocol):
    """Minimal routine schedule shape needed to derive treatment dates."""

    start_date: str
    end_date: str | None


RoutineLookup = Callable[[str], RoutineDateWindow | None]


@dataclass(frozen=True)
class DesignDateResolution:
    """Result of resolving missing design dates without mutating the caller."""

    design: ExperimentDesign
    issues: list[ExperimentPreviewIssue]


@dataclass(frozen=True)
class DesignDateWindow:
    """Parsed experiment date window used by preview data validation."""

    baseline_start: date_type
    baseline_end: date_type
    treatment_start: date_type
    treatment_end: date_type | None


@dataclass(frozen=True)
class DesignDateValidation:
    """Parsed date window plus ordering and parse issues."""

    window: DesignDateWindow | None
    issues: list[ExperimentPreviewIssue]


def resolve_design_dates(
    design: ExperimentDesign,
    linked_routine_ids: Sequence[str],
    routine_lookup: RoutineLookup,
) -> DesignDateResolution:
    """Return the design (copied with routine-derived dates) and any issues.

    Returns the input ``design`` unchanged when no resolution is needed or when
    a validation error blocks resolution.
    """
    issues: list[ExperimentPreviewIssue] = []

    has_dates = (
        design.baseline_start_date
        and design.baseline_end_date
        and design.treatment_start_date
    )
    if has_dates:
        return DesignDateResolution(design=design, issues=issues)

    if design.baseline_duration_days is None:
        issues.append(ExperimentPreviewIssue(
            level="error",
            message="Either provide explicit dates or baseline_duration_days.",
        ))
        return DesignDateResolution(design=design, issues=issues)

    if design.baseline_duration_days < 1:
        issues.append(ExperimentPreviewIssue(
            level="error",
            message="baseline_duration_days must be at least 1.",
        ))
        return DesignDateResolution(design=design, issues=issues)

    if not linked_routine_ids:
        issues.append(ExperimentPreviewIssue(
            level="error",
            message="baseline_duration_days requires a linked routine to derive dates.",
        ))
        return DesignDateResolution(design=design, issues=issues)

    routine_id = linked_routine_ids[0]
    routine = routine_lookup(routine_id)
    if routine is None:
        issues.append(ExperimentPreviewIssue(
            level="error",
            message=f"Linked routine '{routine_id}' not found. "
                    "Import and activate the routine before the experiment.",
        ))
        return DesignDateResolution(design=design, issues=issues)

    treatment_start = date_type.fromisoformat(routine.start_date)
    baseline_end = treatment_start - timedelta(days=1)
    baseline_start = baseline_end - timedelta(days=design.baseline_duration_days - 1)

    updates = {
        "baseline_start_date": baseline_start.isoformat(),
        "baseline_end_date": baseline_end.isoformat(),
        "treatment_start_date": treatment_start.isoformat(),
    }
    if routine.end_date and design.treatment_end_date is None:
        updates["treatment_end_date"] = routine.end_date

    return DesignDateResolution(
        design=design.model_copy(update=updates),
        issues=issues,
    )


def validate_design_date_window(design: ExperimentDesign) -> DesignDateValidation:
    """Parse and validate baseline/treatment date ordering."""
    issues: list[ExperimentPreviewIssue] = []

    if (
        not design.baseline_start_date
        or not design.baseline_end_date
        or not design.treatment_start_date
    ):
        issues.append(ExperimentPreviewIssue(
            level="error",
            message="Baseline start, baseline end, and treatment start dates are required.",
        ))
        return DesignDateValidation(window=None, issues=issues)

    try:
        b_start = date_type.fromisoformat(design.baseline_start_date)
        b_end = date_type.fromisoformat(design.baseline_end_date)
        t_start = date_type.fromisoformat(design.treatment_start_date)
    except ValueError as e:
        issues.append(ExperimentPreviewIssue(level="error", message=f"Invalid date: {e}"))
        return DesignDateValidation(window=None, issues=issues)

    if b_start >= b_end:
        issues.append(ExperimentPreviewIssue(
            level="error", message="Baseline start must be before baseline end.",
        ))
    if b_end >= t_start:
        issues.append(ExperimentPreviewIssue(
            level="error",
            message="Baseline end must be before treatment start.",
        ))

    t_end: date_type | None = None
    if design.treatment_end_date:
        try:
            t_end = date_type.fromisoformat(design.treatment_end_date)
            if t_start >= t_end:
                issues.append(ExperimentPreviewIssue(
                    level="error",
                    message="Treatment start must be before treatment end.",
                ))
        except ValueError as e:
            issues.append(ExperimentPreviewIssue(
                level="error", message=f"Invalid treatment end date: {e}",
            ))

    return DesignDateValidation(
        window=DesignDateWindow(
            baseline_start=b_start,
            baseline_end=b_end,
            treatment_start=t_start,
            treatment_end=t_end,
        ),
        issues=issues,
    )
