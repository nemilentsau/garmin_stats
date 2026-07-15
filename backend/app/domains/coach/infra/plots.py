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

PANEL_SPEC_VERSION = 3

_LINE_COLOR = "#2166ac"
_SECONDARY_COLOR = "#b2182b"
_TERTIARY_COLOR = "#5a8f29"
_SPAN_COLORS = {"run": "#d9edf7", "walk": "#fff0c2", "stand": "#eeeeee"}


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
    embedded = series.series
    candidates = [
        _Channel("Pace", "min/mi", series.pace_min_per_mi, _LINE_COLOR, True),
        _Channel("Heart rate", "bpm", embedded.heart_rate_bpm, _SECONDARY_COLOR),
        _Channel("Cadence", "spm", embedded.cadence_spm, _TERTIARY_COLOR),
        _Channel("Elevation", "ft", series.altitude_ft, "#6b6b6b"),
        _Channel("Power", "W", embedded.power_w, "#7b3294"),
        _Channel("Stride length", "m", series.step_length_m, "#008837"),
        _Channel(
            "Vertical oscillation",
            "cm",
            series.vertical_oscillation_cm,
            "#c51b7d",
        ),
        _Channel("Vertical ratio", "%", embedded.vertical_ratio_pct, "#de77ae"),
        _Channel("Ground contact time", "ms", embedded.stance_time_ms, "#8c510a"),
        _Channel(
            "Ground contact balance",
            "% left",
            embedded.stance_time_balance_pct,
            "#01665e",
        ),
        _Channel("Respiration", "brpm", embedded.respiration_rate_brpm, "#35978f"),
        _Channel("Stance time", "%", embedded.stance_time_pct, "#bf812d"),
        _Channel("Stamina", "%", embedded.stamina_pct, "#1b7837"),
        _Channel("Stamina potential", "%", embedded.stamina_potential_pct, "#5aae61"),
        _Channel("Performance condition", "score", embedded.performance_condition, "#762a83"),
        _Channel("Temperature", "°F", series.temperature_f, "#e66101"),
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


def render_library_panel(
    cache_dir: Path,
    detail: RunDetailResponse,
    series: RunSeriesResponse,
) -> Path:
    """Render or reuse the three-strip historical triage panel."""
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

    elapsed = series.series.elapsed_s
    channels = [
        _Channel("Pace", "min/mi", series.pace_min_per_mi, _LINE_COLOR, True),
        _Channel("Heart rate", "bpm", series.series.heart_rate_bpm, _SECONDARY_COLOR),
        _Channel("Cadence", "spm", series.series.cadence_spm, _TERTIARY_COLOR),
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
    """Render all present measured channels in pages of at most four strips."""
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
            _plot_channel(axis, series.series.elapsed_s, channel)
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
