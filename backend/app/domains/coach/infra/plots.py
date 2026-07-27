"""Static, content-addressed run plots for coach evidence workspaces."""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from app.domains.coach.infra.paths import library_panel_path
from app.domains.garmin_analytics.contracts import RunDetailResponse, RunSeriesResponse

if TYPE_CHECKING:
    from matplotlib.axes import Axes
    from matplotlib.figure import Figure

PANEL_SPEC_VERSION = 5

_LINE_COLOR = "#2166ac"
_SECONDARY_COLOR = "#b2182b"
_TERTIARY_COLOR = "#5a8f29"
_SPAN_COLORS = {"run": "#d9edf7", "walk": "#fff0c2", "stand": "#eeeeee"}
_ZONE_COLORS = ["#dbe5ec", "#d8e8df", "#f0e8c9", "#f2dcc8", "#efd2cf"]


def _pyplot():
    """Import pyplot on first render; startup must not pay the matplotlib cost."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    return plt


@dataclass(frozen=True)
class _Channel:
    label: str
    unit: str
    values: Sequence[float | int | None]
    color: str
    invert: bool = False


def run_content_fingerprint(detail: RunDetailResponse, series: RunSeriesResponse) -> str:
    """Hash every source contract field so stale plots cannot be reused."""
    payload = detail.model_dump_json() + "\n" + series.model_dump_json()
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def _present(values: Sequence[float | int | None]) -> bool:
    return bool(values) and any(value is not None for value in values)


def _current_channels(series: RunSeriesResponse) -> list[_Channel]:
    chart = series.chart
    candidates = [
        _Channel("Pace", "min/mi", chart.pace_min_per_mi, _LINE_COLOR, True),
        _Channel("Heart rate", "bpm", chart.heart_rate_bpm, _SECONDARY_COLOR),
        _Channel("Cadence", "spm", chart.cadence_spm, _TERTIARY_COLOR),
        _Channel("Elevation", "ft", chart.altitude_ft, "#6b6b6b"),
        _Channel("Power", "W", chart.power_w, "#7b3294"),
        _Channel("Stride length", "m", chart.step_length_m, "#008837"),
        _Channel(
            "Vertical oscillation",
            "cm",
            chart.vertical_oscillation_cm,
            "#c51b7d",
        ),
        _Channel("Vertical ratio", "%", chart.vertical_ratio_pct, "#de77ae"),
        _Channel("Ground contact time", "ms", chart.ground_contact_time_ms, "#8c510a"),
        _Channel(
            "Ground contact balance",
            "% left",
            chart.ground_contact_balance_pct,
            "#01665e",
        ),
        _Channel("Respiration", "brpm", chart.respiration_rate_brpm, "#35978f"),
        _Channel("Stance time", "%", chart.stance_time_pct, "#bf812d"),
        _Channel("Stamina", "%", chart.stamina_pct, "#1b7837"),
        _Channel("Stamina potential", "%", chart.stamina_potential_pct, "#5aae61"),
        _Channel("Performance condition", "score", chart.performance_condition, "#762a83"),
        _Channel("Temperature", "°F", chart.temperature_f, "#e66101"),
    ]
    return [channel for channel in candidates if _present(channel.values)]


def available_current_channels(series: RunSeriesResponse) -> list[str]:
    """Return ordered labels for channels with at least one measured value."""
    return [channel.label for channel in _current_channels(series)]


def break_elapsed_gaps(
    elapsed: Sequence[int],
    values: Sequence[float | int | None],
    *,
    max_gap_s: int = 3,
) -> tuple[list[float], list[float]]:
    """Insert NaN separators where adjacent records are too far apart."""
    x: list[float] = []
    y: list[float] = []
    count = min(len(elapsed), len(values))
    for index in range(count):
        current_x = float(elapsed[index])
        if index > 0 and elapsed[index] - elapsed[index - 1] > max_gap_s:
            x.append(float(elapsed[index - 1] + 1))
            y.append(float("nan"))
        x.append(current_x)
        value = values[index]
        y.append(float("nan") if value is None else float(value))
    return x, y


def _plot_channel(axis: Axes, elapsed: list[int], channel: _Channel) -> None:
    x, y = break_elapsed_gaps(elapsed, channel.values)
    axis.plot(x, y, color=channel.color, linewidth=1.25)
    axis.set_ylabel(f"{channel.label}\n({channel.unit})", fontsize=8, rotation=0)
    axis.yaxis.set_label_coords(-0.09, 0.5)
    axis.tick_params(axis="both", labelsize=8, colors="#555555")
    axis.spines[["top", "right"]].set_visible(False)
    axis.spines[["left", "bottom"]].set_color("#cccccc")
    axis.grid(axis="y", color="#e6e6e6", linewidth=0.5)
    axis.margins(x=0, y=0.08)
    if channel.invert:
        axis.invert_yaxis()


def _annotate_timeline(
    axes: list[Axes], detail: RunDetailResponse, series: RunSeriesResponse
) -> None:
    for span in series.series.run_walk_spans:
        color = _SPAN_COLORS.get(span.span_type, "#eeeeee")
        for axis in axes:
            axis.axvspan(span.start_s, span.end_s, color=color, alpha=0.22, linewidth=0)
    for lap in detail.laps:
        if lap.start_s is None:
            continue
        for axis in axes:
            axis.axvline(lap.start_s, color="#777777", linewidth=0.7, alpha=0.55)


def _new_figure(strip_count: int) -> tuple[Figure, list[Axes]]:
    plt = _pyplot()
    figure, raw_axes = plt.subplots(
        strip_count,
        1,
        sharex=True,
        figsize=(10, max(2.4, strip_count * 1.75)),
        constrained_layout=True,
    )
    axes = [raw_axes] if strip_count == 1 else list(raw_axes)
    figure.patch.set_facecolor("white")
    return figure, axes


def _save_no_series(path: Path, detail: RunDetailResponse) -> None:
    plt = _pyplot()
    figure, axis = plt.subplots(figsize=(10, 2.4), constrained_layout=True)
    figure.patch.set_facecolor("white")
    axis.axis("off")
    axis.text(
        0.5,
        0.55,
        "No per-second series available",
        ha="center",
        va="center",
        fontsize=14,
        color="#444444",
    )
    axis.text(
        0.5,
        0.36,
        f"{detail.session.session_date} · {detail.session.activity_name or detail.session.id}",
        ha="center",
        va="center",
        fontsize=9,
        color="#777777",
    )
    figure.savefig(path, dpi=150, facecolor="white")
    plt.close(figure)


def _annotate_hr_zones(axis: Axes, series: RunSeriesResponse) -> None:
    evidence = series.heart_rate_evidence
    if evidence is None:
        return
    y_low, y_high = axis.get_ylim()
    for row in evidence.zones:
        if row.lower_bound is None:
            continue
        lower = float(row.lower_bound)
        upper = y_high if row.upper_bound is None else float(row.upper_bound + 1)
        if upper >= y_low and lower <= y_high:
            axis.axhspan(
                max(lower, y_low),
                min(upper, y_high),
                color=_ZONE_COLORS[(row.zone - 1) % len(_ZONE_COLORS)],
                alpha=0.35,
                linewidth=0,
                zorder=0,
            )
        axis.axhline(lower, color="#8b6f31", linewidth=0.75, alpha=0.7)
        if y_low <= lower <= y_high:
            axis.text(
                1.0,
                lower,
                f"Z{row.zone} · {row.lower_bound} bpm",
                transform=axis.get_yaxis_transform(),
                ha="right",
                va="bottom",
                fontsize=7,
                color="#705a2d",
            )


def _plot_hr_histogram(axis: Axes, series: RunSeriesResponse) -> None:
    evidence = series.heart_rate_evidence
    if evidence is None:
        axis.axis("off")
        axis.text(0.5, 0.5, "No heart-rate distribution", ha="center", va="center")
        return
    bpm = [row.bpm for row in evidence.histogram]
    percentages = [row.sample_pct for row in evidence.histogram]
    axis.bar(bpm, percentages, width=0.9, color="#b2182b", alpha=0.78)
    axis.set_title("Heart-rate sample distribution", fontsize=9, loc="left")
    axis.set_xlabel("Heart rate (bpm)", fontsize=8)
    axis.set_ylabel("Samples (%)", fontsize=8)
    axis.set_ylim(bottom=0)
    axis.tick_params(axis="both", labelsize=8, colors="#555555")
    axis.spines[["top", "right"]].set_visible(False)
    axis.spines[["left", "bottom"]].set_color("#cccccc")
    axis.grid(axis="y", color="#e6e6e6", linewidth=0.5)
    for row in evidence.zones:
        if row.lower_bound is None:
            continue
        axis.axvline(row.lower_bound, color="#8b6f31", linewidth=0.75, alpha=0.7)
        axis.text(
            row.lower_bound,
            0.98,
            f"Z{row.zone}",
            transform=axis.get_xaxis_transform(),
            ha="left",
            va="top",
            fontsize=7,
            color="#705a2d",
        )


def _render_intensity_composite(
    path: Path,
    detail: RunDetailResponse,
    series: RunSeriesResponse,
    *,
    include_cadence: bool,
) -> None:
    plt = _pyplot()
    evidence = series.heart_rate_evidence
    if evidence is None:
        _save_no_series(path, detail)
        return

    row_count = 3 if include_cadence and _present(series.chart.cadence_spm) else 2
    figure = plt.figure(
        figsize=(11, 6.5 if row_count == 3 else 5.4), constrained_layout=True
    )
    grid = figure.add_gridspec(row_count, 2, width_ratios=(2.25, 1.0))
    timeline_axes: list[Axes] = []
    pace_axis = figure.add_subplot(grid[0, 0])
    _plot_channel(
        pace_axis,
        series.chart.elapsed_s,
        _Channel("Pace", "min/mi", series.chart.pace_min_per_mi, _LINE_COLOR, True),
    )
    timeline_axes.append(pace_axis)

    hr_axis = figure.add_subplot(grid[1, 0], sharex=pace_axis)
    _plot_channel(
        hr_axis,
        series.chart.elapsed_s,
        _Channel("Heart rate", "bpm", series.chart.heart_rate_bpm, _SECONDARY_COLOR),
    )
    _annotate_hr_zones(hr_axis, series)
    timeline_axes.append(hr_axis)

    if row_count == 3:
        cadence_axis = figure.add_subplot(grid[2, 0], sharex=pace_axis)
        _plot_channel(
            cadence_axis,
            series.chart.elapsed_s,
            _Channel("Cadence", "spm", series.chart.cadence_spm, _TERTIARY_COLOR),
        )
        timeline_axes.append(cadence_axis)
    timeline_axes[-1].set_xlabel("Elapsed time (s)", fontsize=9)

    histogram_axis = figure.add_subplot(grid[:, 1])
    _plot_hr_histogram(histogram_axis, series)
    _annotate_timeline(timeline_axes, detail, series)
    stats = (
        f"Q1 {evidence.q1_bpm:g} · median {evidence.median_bpm:g} · "
        f"Q3 {evidence.q3_bpm:g} · P90 {evidence.p90_bpm:g} bpm · "
        f"coverage {evidence.coverage_pct:g}% "
        f"({evidence.present_samples}/{evidence.total_samples} samples)"
    )
    figure.suptitle(
        f"{detail.session.session_date} · {detail.session.activity_name or detail.session.id}\n"
        f"{stats}",
        fontsize=10,
        x=0.01,
        ha="left",
    )
    figure.savefig(path, dpi=150, facecolor="white")
    plt.close(figure)


def render_library_panel(
    cache_dir: Path,
    detail: RunDetailResponse,
    series: RunSeriesResponse,
) -> Path:
    """Render or reuse the historical intensity-evidence panel."""
    plt = _pyplot()
    cache_dir.mkdir(parents=True, exist_ok=True)
    fingerprint = run_content_fingerprint(detail, series)
    path = library_panel_path(
        cache_dir,
        detail.session.id,
        fingerprint,
        spec_version=PANEL_SPEC_VERSION,
    )
    if path.is_file():
        return path

    if series.heart_rate_evidence is not None:
        _render_intensity_composite(
            path, detail, series, include_cadence=True
        )
        return path

    elapsed = series.chart.elapsed_s
    channels = [
        _Channel("Pace", "min/mi", series.chart.pace_min_per_mi, _LINE_COLOR, True),
        _Channel("Heart rate", "bpm", series.chart.heart_rate_bpm, _SECONDARY_COLOR),
        _Channel("Cadence", "spm", series.chart.cadence_spm, _TERTIARY_COLOR),
    ]
    if not elapsed or not any(_present(channel.values) for channel in channels):
        _save_no_series(path, detail)
        return path

    figure, axes = _new_figure(3)
    for axis, channel in zip(axes, channels, strict=True):
        _plot_channel(axis, elapsed, channel)
    _annotate_timeline(axes, detail, series)
    axes[-1].set_xlabel("Elapsed time (s)", fontsize=9)
    figure.suptitle(
        f"{detail.session.session_date} · {detail.session.activity_name or detail.session.id}",
        fontsize=11,
        x=0.01,
        ha="left",
    )
    figure.savefig(path, dpi=150, facecolor="white")
    plt.close(figure)
    return path


def render_current_run_stack(
    output_dir: Path,
    detail: RunDetailResponse,
    series: RunSeriesResponse,
) -> list[Path]:
    """Render intensity evidence first, then remaining channels in four-strip pages."""
    plt = _pyplot()
    output_dir.mkdir(parents=True, exist_ok=True)
    fingerprint = run_content_fingerprint(detail, series)
    channels = _current_channels(series)
    if not channels:
        path = output_dir / (
            f"current-{detail.session.id}-{fingerprint}-v{PANEL_SPEC_VERSION}-p01.png"
        )
        if not path.is_file():
            _save_no_series(path, detail)
        return [path]

    paths: list[Path] = []
    if series.heart_rate_evidence is not None:
        intensity_path = output_dir / (
            f"current-{detail.session.id}-{fingerprint}-v{PANEL_SPEC_VERSION}-intensity.png"
        )
        paths.append(intensity_path)
        if not intensity_path.is_file():
            _render_intensity_composite(
                intensity_path, detail, series, include_cadence=False
            )
        channels = [
            channel
            for channel in channels
            if channel.label not in {"Pace", "Heart rate"}
        ]

    for page_index, offset in enumerate(range(0, len(channels), 4), start=1):
        page_channels = channels[offset : offset + 4]
        path = output_dir / (
            f"current-{detail.session.id}-{fingerprint}-v{PANEL_SPEC_VERSION}-p{page_index:02d}.png"
        )
        paths.append(path)
        if path.is_file():
            continue
        figure, axes = _new_figure(len(page_channels))
        for axis, channel in zip(axes, page_channels, strict=True):
            _plot_channel(axis, series.chart.elapsed_s, channel)
        _annotate_timeline(axes, detail, series)
        axes[-1].set_xlabel("Elapsed time (s)", fontsize=9)
        figure.suptitle(
            f"Current run · {detail.session.session_date} · page {page_index}",
            fontsize=11,
            x=0.01,
            ha="left",
        )
        figure.savefig(path, dpi=100, facecolor="white")
        plt.close(figure)
    return paths
