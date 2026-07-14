"""Experiment design date validation for explicit baseline/treatment windows."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date as date_type

from app.domains.experiments.contracts import ExperimentDesign, ExperimentPreviewIssue


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
