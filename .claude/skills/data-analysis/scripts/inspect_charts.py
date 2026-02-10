#!/usr/bin/env python3
"""
Generate static chart images for visual inspection.

Produces PNG charts matching what the frontend dashboards display,
so you can examine them with multimodal capabilities to catch:
- Wrong scales, flat lines, missing data gaps
- Outlier effects on averages
- IQR bands that are too wide or too narrow
- Data that didn't load or was filtered incorrectly

Usage:
    cd backend && uv run python ../.claude/skills/data-analysis/scripts/inspect_charts.py [--output-dir /tmp/charts]

Then read the generated PNGs to visually inspect them.
"""

import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
PROJECT_ROOT = SKILL_DIR.parent.parent.parent
BACKEND_DIR = PROJECT_ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))

import matplotlib
matplotlib.use("Agg")  # Non-interactive backend
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
from datetime import datetime

from app.parser import parse_all_days
from app.stats import compute_daily_aggregates


def load_aggregates(data_dir: Path) -> dict:
    days = parse_all_days(data_dir)
    response = compute_daily_aggregates(days)
    return response.model_dump()


def parse_dates(date_strings: list[str]) -> list[datetime]:
    return [datetime.strptime(d, "%Y-%m-%d") for d in date_strings]


def plot_metric_with_iqr(
    ax, dates, avgs, q1s, q3s,
    color="#dc2626", label="Avg", title="", ylabel=""
):
    """Plot a metric with IQR band (Q1-Q3) from pre-computed API data."""
    valid = [(d, a, lo, hi) for d, a, lo, hi in zip(dates, avgs, q1s, q3s)
             if a is not None and lo is not None and hi is not None]
    if not valid:
        ax.text(0.5, 0.5, "No data", transform=ax.transAxes, ha="center", va="center")
        ax.set_title(title)
        return

    vd, va, vlo, vhi = zip(*valid)

    # IQR band (25-75)
    ax.fill_between(vd, vlo, vhi, alpha=0.25, color=color, label="IQR (25th-75th)")
    # Average line
    ax.plot(vd, va, color=color, linewidth=1.5, label=label)

    # Annotate band ratio
    band_height = max(vhi) - min(vlo)
    avg_range = max(va) - min(va)
    if avg_range > 0:
        ratio = band_height / avg_range
        ax.text(0.02, 0.02, f"Band: {band_height:.0f}, Avg var: {avg_range:.0f}, Ratio: {ratio:.1f}x",
                transform=ax.transAxes, fontsize=7, va="bottom",
                bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.8))

    ax.set_title(title, fontsize=11, fontweight="bold")
    ax.set_ylabel(ylabel, fontsize=9)
    ax.legend(fontsize=7, loc="upper right")
    ax.tick_params(axis="x", rotation=45, labelsize=7)
    ax.tick_params(axis="y", labelsize=8)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))


def generate_dashboard_charts(data_dir: Path, output_dir: Path):
    """Generate the main dashboard overview charts using IQR bands from API."""
    agg = load_aggregates(data_dir)
    dates = parse_dates(agg["days"])
    daily = agg["daily"]

    fig, axes = plt.subplots(4, 2, figsize=(16, 18))
    fig.suptitle("Dashboard Overview — IQR Bands", fontsize=14, fontweight="bold")

    # Heart Rate
    ax = axes[0, 0]
    avgs = [d["heart_rate"]["avg"] for d in daily]
    q1s = [d["heart_rate"]["q1"] for d in daily]
    q3s = [d["heart_rate"]["q3"] for d in daily]
    resting = [d["heart_rate"]["resting"] for d in daily]
    plot_metric_with_iqr(ax, dates, avgs, q1s, q3s,
                         color="#dc2626", label="Daily Avg", title="Heart Rate (bpm)", ylabel="bpm")
    valid_rest = [(d, r) for d, r in zip(dates, resting) if r is not None]
    if valid_rest:
        rd, rv = zip(*valid_rest)
        ax.plot(rd, rv, color="#16a34a", linewidth=1.5, label="Resting")
        ax.legend(fontsize=7)

    # Stress
    plot_metric_with_iqr(axes[0, 1], dates,
                         [d["stress"]["avg"] for d in daily],
                         [d["stress"]["q1"] for d in daily],
                         [d["stress"]["q3"] for d in daily],
                         color="#ea580c", label="Daily Avg", title="Stress (0-100)", ylabel="score")

    # Body Battery
    plot_metric_with_iqr(axes[1, 0], dates,
                         [d["body_battery"]["avg"] for d in daily],
                         [d["body_battery"]["q1"] for d in daily],
                         [d["body_battery"]["q3"] for d in daily],
                         color="#059669", label="Daily Avg", title="Body Battery (0-100)", ylabel="score")

    # Respiration
    ax = axes[1, 1]
    plot_metric_with_iqr(ax, dates,
                         [d["respiration"]["avg"] for d in daily],
                         [d["respiration"]["q1"] for d in daily],
                         [d["respiration"]["q3"] for d in daily],
                         color="#0d9488", label="Daily Avg", title="Respiration (br/min)", ylabel="br/min")
    ax.axhline(y=14, color="#9ca3af", linewidth=0.8, linestyle=":", label="Elevated (14)")
    ax.legend(fontsize=7)

    # SpO2 — IQR band + min line
    ax = axes[2, 0]
    spo2_avgs = [d["spo2"]["avg"] for d in daily]
    spo2_q1s = [d["spo2"]["q1"] for d in daily]
    spo2_q3s = [d["spo2"]["q3"] for d in daily]
    spo2_mins = [d["spo2"]["min"] for d in daily]
    plot_metric_with_iqr(ax, dates, spo2_avgs, spo2_q1s, spo2_q3s,
                         color="#2563eb", label="Daily Avg", title="SpO2 (%)", ylabel="%")
    valid_mn = [(d, mn) for d, mn in zip(dates, spo2_mins) if mn is not None]
    if valid_mn:
        md, mv = zip(*valid_mn)
        ax.plot(md, mv, color="#dc2626", linewidth=1, linestyle="--", label="Daily Min")
    ax.axhline(y=90, color="#9ca3af", linewidth=0.8, linestyle=":", label="Concern (90%)")
    ax.legend(fontsize=7)

    # HRV
    hrv_nightly = [d["hrv"]["nightly_avg"] for d in daily]
    hrv_weekly = [d["hrv"]["weekly_avg"] for d in daily]
    ax = axes[2, 1]
    valid_h = [(d, n) for d, n in zip(dates, hrv_nightly) if n is not None]
    if valid_h:
        hd, hn = zip(*valid_h)
        ax.plot(hd, hn, color="#7c3aed", linewidth=1.5, label="Nightly Avg")
    valid_hw = [(d, w) for d, w in zip(dates, hrv_weekly) if w is not None]
    if valid_hw:
        hwd, hwv = zip(*valid_hw)
        ax.plot(hwd, hwv, color="#a78bfa", linewidth=1.5, linestyle="--", label="Weekly Avg")
    ax.set_title("HRV (ms)", fontsize=11, fontweight="bold")
    ax.set_ylabel("ms", fontsize=9)
    ax.legend(fontsize=7)
    ax.tick_params(axis="x", rotation=45, labelsize=7)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))

    # Skin Temp
    skin_dev = [d["skin_temp"]["deviation"] for d in daily]
    skin_7d = [d["skin_temp"]["deviation_7_day"] for d in daily]
    ax = axes[3, 0]
    valid_st = [(d, v) for d, v in zip(dates, skin_dev) if v is not None]
    if valid_st:
        std, stv = zip(*valid_st)
        ax.plot(std, stv, color="#d97706", linewidth=1.5, label="Deviation")
    valid_st7 = [(d, v) for d, v in zip(dates, skin_7d) if v is not None]
    if valid_st7:
        st7d, st7v = zip(*valid_st7)
        ax.plot(st7d, st7v, color="#f59e0b", linewidth=1.5, linestyle="--", label="7-day smoothed")
    ax.axhline(y=0, color="#9ca3af", linewidth=0.8, linestyle=":")
    ax.set_title("Skin Temp Deviation (\u00b0C)", fontsize=11, fontweight="bold")
    ax.set_ylabel("\u00b0C", fontsize=9)
    ax.legend(fontsize=7)
    ax.tick_params(axis="x", rotation=45, labelsize=7)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))

    # Sleep Score with 7-day rolling average
    sleep_scores = [d["sleep"]["score"] for d in daily]
    ax = axes[3, 1]
    valid_sl = [(d, s) for d, s in zip(dates, sleep_scores) if s is not None]
    if valid_sl:
        sld, slv = zip(*valid_sl)
        ax.plot(sld, slv, color="#4f46e5", linewidth=1.5, label="Sleep Score")
        # 7-day rolling average
        smoothed = []
        for i in range(len(sleep_scores)):
            window = [v for v in sleep_scores[max(0, i - 6):i + 1] if v is not None]
            smoothed.append(np.mean(window) if len(window) >= 3 else None)
        valid_sm = [(d, s) for d, s in zip(dates, smoothed) if s is not None]
        if valid_sm:
            smd, smv = zip(*valid_sm)
            ax.plot(smd, smv, color="#818cf8", linewidth=1.5, linestyle="--", label="7-Day Avg")
    ax.set_title("Sleep Score", fontsize=11, fontweight="bold")
    ax.set_ylabel("score", fontsize=9)
    ax.legend(fontsize=7)
    ax.tick_params(axis="x", rotation=45, labelsize=7)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))

    plt.tight_layout()
    output_path = output_dir / "dashboard_overview.png"
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {output_path}")


def generate_distribution_charts(data_dir: Path, output_dir: Path):
    """Generate distribution charts for key metrics — EDA view."""
    agg = load_aggregates(data_dir)
    daily = agg["daily"]

    fig, axes = plt.subplots(2, 4, figsize=(20, 8))
    fig.suptitle("Daily Metric Distributions — EDA Inspection", fontsize=14, fontweight="bold")

    metrics = [
        ("Heart Rate Avg (bpm)", [d["heart_rate"]["avg"] for d in daily], "#dc2626"),
        ("Stress Avg (0-100)", [d["stress"]["avg"] for d in daily], "#ea580c"),
        ("Body Battery Avg", [d["body_battery"]["avg"] for d in daily], "#059669"),
        ("SpO2 Avg (%)", [d["spo2"]["avg"] for d in daily], "#2563eb"),
        ("Respiration Avg (br/min)", [d["respiration"]["avg"] for d in daily], "#0d9488"),
        ("HRV Nightly (ms)", [d["hrv"]["nightly_avg"] for d in daily], "#7c3aed"),
        ("Sleep Score", [d["sleep"]["score"] for d in daily], "#4f46e5"),
        ("Skin Temp Dev (\u00b0C)", [d["skin_temp"]["deviation"] for d in daily], "#d97706"),
    ]

    for ax, (title, values, color) in zip(axes.flat, metrics):
        valid = [v for v in values if v is not None]
        if valid:
            ax.hist(valid, bins=15, color=color, alpha=0.7, edgecolor="white")
            mean = np.mean(valid)
            median = np.median(valid)
            std = np.std(valid)
            ax.axvline(mean, color="black", linewidth=1, linestyle="--", label=f"Mean: {mean:.1f}")
            ax.axvline(median, color="gray", linewidth=1, linestyle="-", label=f"Median: {median:.1f}")
            ax.set_xlabel(f"n={len(valid)}, sd={std:.1f}", fontsize=8)
            ax.legend(fontsize=7)
            total = len(values)
            missing = total - len(valid)
            if missing > 0:
                pct = missing / total * 100
                ax.text(0.98, 0.98, f"{missing} missing ({pct:.0f}%)",
                        transform=ax.transAxes, ha="right", va="top",
                        fontsize=7, color="red")
        else:
            ax.text(0.5, 0.5, "No data", transform=ax.transAxes, ha="center", va="center")
        ax.set_title(title, fontsize=10, fontweight="bold")
        ax.tick_params(labelsize=8)

    plt.tight_layout()
    output_path = output_dir / "distributions.png"
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {output_path}")


def generate_iqr_vs_minmax_comparison(data_dir: Path, output_dir: Path):
    """Side-by-side comparison: min/max bands vs IQR bands for heart rate.

    Uses real Q1/Q3 from the API (not simulated).
    """
    agg = load_aggregates(data_dir)
    dates = parse_dates(agg["days"])
    daily = agg["daily"]

    avgs = [d["heart_rate"]["avg"] for d in daily]
    mins = [d["heart_rate"]["min"] for d in daily]
    maxs = [d["heart_rate"]["max"] for d in daily]
    q1s = [d["heart_rate"]["q1"] for d in daily]
    q3s = [d["heart_rate"]["q3"] for d in daily]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 5), sharey=True)
    fig.suptitle("Heart Rate: Min/Max Bands vs IQR Bands — Readability Comparison",
                 fontsize=13, fontweight="bold")

    # Left: min/max (old approach)
    valid = [(d, a, mn, mx) for d, a, mn, mx in zip(dates, avgs, mins, maxs) if a is not None]
    avg_range = 1  # fallback
    if valid:
        vd, va, vmn, vmx = zip(*valid)
        ax1.fill_between(vd, vmn, vmx, alpha=0.2, color="#dc2626", label="Min-Max")
        ax1.plot(vd, va, color="#dc2626", linewidth=1.5, label="Avg")
        band_height = max(vmx) - min(vmn)
        avg_range = max(va) - min(va)
        ratio = band_height / avg_range if avg_range > 0 else float("inf")
        ax1.text(0.02, 0.02, f"Band: {band_height:.0f} bpm\nAvg var: {avg_range:.0f} bpm\nRatio: {ratio:.1f}x",
                 transform=ax1.transAxes, fontsize=8, va="bottom",
                 bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.8))
    ax1.set_title("Old: Min/Max Bands", fontsize=11)
    ax1.set_ylabel("bpm", fontsize=9)
    ax1.legend(fontsize=8)
    ax1.tick_params(axis="x", rotation=45, labelsize=7)
    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))

    # Right: real IQR from API
    valid2 = [(d, a, lo, hi) for d, a, lo, hi in zip(dates, avgs, q1s, q3s)
              if a is not None and lo is not None and hi is not None]
    if valid2:
        vd2, va2, vlo, vhi = zip(*valid2)
        ax2.fill_between(vd2, vlo, vhi, alpha=0.25, color="#dc2626", label="IQR (25th-75th)")
        ax2.plot(vd2, va2, color="#dc2626", linewidth=1.5, label="Avg")
        band2 = max(vhi) - min(vlo)
        ratio2 = band2 / avg_range if avg_range > 0 else float("inf")
        ax2.text(0.02, 0.02, f"Band: {band2:.0f} bpm\nAvg var: {avg_range:.0f} bpm\nRatio: {ratio2:.1f}x",
                 transform=ax2.transAxes, fontsize=8, va="bottom",
                 bbox=dict(boxstyle="round", facecolor="lightgreen", alpha=0.8))
    ax2.set_title("New: IQR Bands (real Q1/Q3)", fontsize=11)
    ax2.legend(fontsize=8)
    ax2.tick_params(axis="x", rotation=45, labelsize=7)
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))

    plt.tight_layout()
    output_path = output_dir / "minmax_vs_iqr.png"
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {output_path}")


def generate_correlation_matrix(data_dir: Path, output_dir: Path):
    """Generate cross-metric correlation matrix and scatter plots for EDA."""
    agg = load_aggregates(data_dir)
    daily = agg["daily"]

    metric_defs = [
        ("HR Avg", [d["heart_rate"]["avg"] for d in daily]),
        ("Stress", [d["stress"]["avg"] for d in daily]),
        ("Body Battery", [d["body_battery"]["avg"] for d in daily]),
        ("SpO2", [d["spo2"]["avg"] for d in daily]),
        ("Respiration", [d["respiration"]["avg"] for d in daily]),
        ("HRV Nightly", [d["hrv"]["nightly_avg"] for d in daily]),
        ("Sleep Score", [d["sleep"]["score"] for d in daily]),
    ]

    names = [m[0] for m in metric_defs]
    arrays = [np.array([v if v is not None else np.nan for v in m[1]]) for m in metric_defs]
    n = len(names)

    # Compute pairwise Pearson correlations (skipping NaN pairs)
    corr = np.full((n, n), np.nan)
    for i in range(n):
        for j in range(n):
            mask = ~np.isnan(arrays[i]) & ~np.isnan(arrays[j])
            if mask.sum() >= 5:
                corr[i, j] = np.corrcoef(arrays[i][mask], arrays[j][mask])[0, 1]

    fig, axes = plt.subplots(1, 2, figsize=(16, 6),
                             gridspec_kw={"width_ratios": [1, 1.4]})
    fig.suptitle("Cross-Metric Correlations — EDA", fontsize=14, fontweight="bold")

    # Left: heatmap
    ax = axes[0]
    im = ax.imshow(corr, cmap="RdBu_r", vmin=-1, vmax=1, aspect="auto")
    ax.set_xticks(range(n))
    ax.set_yticks(range(n))
    ax.set_xticklabels(names, rotation=45, ha="right", fontsize=8)
    ax.set_yticklabels(names, fontsize=8)
    for i in range(n):
        for j in range(n):
            if not np.isnan(corr[i, j]):
                color = "white" if abs(corr[i, j]) > 0.6 else "black"
                ax.text(j, i, f"{corr[i, j]:.2f}", ha="center", va="center",
                        fontsize=7, color=color)
    fig.colorbar(im, ax=ax, shrink=0.8, label="Pearson r")
    ax.set_title("Correlation Matrix", fontsize=11)

    # Right: scatter plots for strongest correlations (top 4 by |r|, excluding diagonal)
    pairs = []
    for i in range(n):
        for j in range(i + 1, n):
            if not np.isnan(corr[i, j]):
                pairs.append((abs(corr[i, j]), corr[i, j], i, j))
    pairs.sort(reverse=True)
    top_pairs = pairs[:4]

    axes[1].remove()
    # Create 2x2 sub-axes in the right half using absolute positions
    sub_positions = [
        [0.55, 0.55, 0.20, 0.30],
        [0.78, 0.55, 0.20, 0.30],
        [0.55, 0.12, 0.20, 0.30],
        [0.78, 0.12, 0.20, 0.30],
    ]
    colors = ["#dc2626", "#2563eb", "#059669", "#7c3aed"]

    for idx, (abs_r, r, i, j) in enumerate(top_pairs):
        ax_sub = fig.add_axes(sub_positions[idx])
        mask = ~np.isnan(arrays[i]) & ~np.isnan(arrays[j])
        ax_sub.scatter(arrays[i][mask], arrays[j][mask], s=15, alpha=0.6,
                       color=colors[idx], edgecolors="white", linewidth=0.3)
        ax_sub.set_xlabel(names[i], fontsize=7)
        ax_sub.set_ylabel(names[j], fontsize=7)
        ax_sub.set_title(f"r = {r:.2f}", fontsize=9, fontweight="bold")
        ax_sub.tick_params(labelsize=6)
    output_path = output_dir / "correlations.png"
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {output_path}")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Generate chart images for visual inspection")
    parser.add_argument("--data-dir", type=Path, default=PROJECT_ROOT / "data")
    parser.add_argument("--output-dir", type=Path, default=PROJECT_ROOT / ".claude" / "chart-inspections")
    parser.add_argument("--chart", choices=["all", "dashboard", "distributions", "minmax", "correlations"],
                        default="all", help="Which charts to generate")
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)

    if args.chart in ("all", "dashboard"):
        generate_dashboard_charts(args.data_dir, args.output_dir)
    if args.chart in ("all", "distributions"):
        generate_distribution_charts(args.data_dir, args.output_dir)
    if args.chart in ("all", "minmax"):
        generate_iqr_vs_minmax_comparison(args.data_dir, args.output_dir)
    if args.chart in ("all", "correlations"):
        generate_correlation_matrix(args.data_dir, args.output_dir)

    print(f"\nAll charts saved to: {args.output_dir}")
    print("Read the PNG files to visually inspect them.")


if __name__ == "__main__":
    main()
