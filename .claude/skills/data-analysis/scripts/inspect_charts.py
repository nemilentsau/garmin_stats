#!/usr/bin/env python3
"""
Generate static chart images for visual inspection.

Produces PNG charts matching what the frontend dashboards display,
so you can examine them with multimodal capabilities to catch:
- Wrong scales, flat lines, missing data gaps
- Outlier effects on averages
- Min/max bands obscuring meaningful variation
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

from app.parser import get_daily_aggregates, parse_wellness_data


def load_aggregates(data_dir: Path) -> dict:
    return get_daily_aggregates(data_dir)


def parse_dates(date_strings: list[str]) -> list[datetime]:
    return [datetime.strptime(d, "%Y-%m-%d") for d in date_strings]


def compute_iqr_bands(values_list: list[list[float]]) -> tuple[list, list, list, list, list]:
    """Compute median, IQR (25-75), and 10-90 percentile bands.

    Args:
        values_list: list of lists — one inner list of raw values per day.

    Returns:
        (medians, q25, q75, p10, p90) — each is a list of float|None per day.
    """
    medians, q25s, q75s, p10s, p90s = [], [], [], [], []
    for vals in values_list:
        if not vals:
            medians.append(None)
            q25s.append(None)
            q75s.append(None)
            p10s.append(None)
            p90s.append(None)
        else:
            arr = np.array(vals)
            medians.append(float(np.median(arr)))
            q25s.append(float(np.percentile(arr, 25)))
            q75s.append(float(np.percentile(arr, 75)))
            p10s.append(float(np.percentile(arr, 10)))
            p90s.append(float(np.percentile(arr, 90)))
    return medians, q25s, q75s, p10s, p90s


def plot_metric_with_bands(
    ax, dates, medians, q25, q75, p10, p90,
    avg_line=None, color="#dc2626", label="Median", title="", ylabel=""
):
    """Plot a metric with IQR band + 10-90 band + optional mean line."""
    valid = [(d, m, q2, q7, p1, p9) for d, m, q2, q7, p1, p9
             in zip(dates, medians, q25, q75, p10, p90)
             if m is not None]
    if not valid:
        ax.text(0.5, 0.5, "No data", transform=ax.transAxes, ha="center", va="center")
        ax.set_title(title)
        return

    vd, vm, vq2, vq7, vp1, vp9 = zip(*valid)

    # 10-90 percentile band (light)
    ax.fill_between(vd, vp1, vp9, alpha=0.1, color=color, label="10th-90th pctl")
    # IQR band (25-75)
    ax.fill_between(vd, vq2, vq7, alpha=0.25, color=color, label="IQR (25th-75th)")
    # Median line
    ax.plot(vd, vm, color=color, linewidth=1.5, label=label)

    # Optional mean line for comparison
    if avg_line:
        valid_avg = [(d, a) for d, a in zip(dates, avg_line) if a is not None]
        if valid_avg:
            ad, av = zip(*valid_avg)
            ax.plot(ad, av, color=color, linewidth=1, linestyle="--", alpha=0.5, label="Mean")

    ax.set_title(title, fontsize=11, fontweight="bold")
    ax.set_ylabel(ylabel, fontsize=9)
    ax.legend(fontsize=7, loc="upper right")
    ax.tick_params(axis="x", rotation=45, labelsize=7)
    ax.tick_params(axis="y", labelsize=8)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))


def generate_dashboard_charts(data_dir: Path, output_dir: Path):
    """Generate the main dashboard overview charts."""
    agg = load_aggregates(data_dir)
    dates = parse_dates(agg["days"])
    daily = agg["daily"]

    fig, axes = plt.subplots(3, 2, figsize=(16, 14))
    fig.suptitle("Dashboard Overview — Visual Inspection", fontsize=14, fontweight="bold")

    # Heart Rate — we need per-day raw values for proper IQR bands
    # For now, use the daily avg/min/max from aggregates (this shows the problem)
    avgs = [d["heart_rate"]["avg"] for d in daily]
    mins = [d["heart_rate"]["min"] for d in daily]
    maxs = [d["heart_rate"]["max"] for d in daily]
    resting = [d["heart_rate"]["resting"] for d in daily]

    ax = axes[0, 0]
    valid_hr = [(d, a, mn, mx) for d, a, mn, mx in zip(dates, avgs, mins, maxs) if a is not None]
    if valid_hr:
        hd, ha, hmn, hmx = zip(*valid_hr)
        ax.fill_between(hd, hmn, hmx, alpha=0.15, color="#dc2626", label="Min-Max range")
        ax.plot(hd, ha, color="#dc2626", linewidth=1.5, label="Daily Avg")
        valid_rest = [(d, r) for d, r in zip(dates, resting) if r is not None]
        if valid_rest:
            rd, rv = zip(*valid_rest)
            ax.plot(rd, rv, color="#16a34a", linewidth=1.5, label="Resting")
    ax.set_title("Heart Rate (bpm)", fontsize=11, fontweight="bold")
    ax.set_ylabel("bpm", fontsize=9)
    ax.legend(fontsize=7)
    ax.tick_params(axis="x", rotation=45, labelsize=7)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))

    # Stress
    stress_avgs = [d["stress"]["avg"] for d in daily]
    stress_mins = [d["stress"]["min"] for d in daily]
    stress_maxs = [d["stress"]["max"] for d in daily]
    ax = axes[0, 1]
    valid_s = [(d, a, mn, mx) for d, a, mn, mx in zip(dates, stress_avgs, stress_mins, stress_maxs) if a is not None]
    if valid_s:
        sd, sa, smn, smx = zip(*valid_s)
        ax.fill_between(sd, smn, smx, alpha=0.15, color="#ea580c", label="Min-Max range")
        ax.plot(sd, sa, color="#ea580c", linewidth=1.5, label="Daily Avg")
    ax.set_title("Stress (0-100)", fontsize=11, fontweight="bold")
    ax.set_ylabel("score", fontsize=9)
    ax.legend(fontsize=7)
    ax.tick_params(axis="x", rotation=45, labelsize=7)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))

    # SpO2
    spo2_avgs = [d["spo2"]["avg"] for d in daily]
    spo2_mins = [d["spo2"]["min"] for d in daily]
    ax = axes[1, 0]
    valid_o = [(d, a, mn) for d, a, mn in zip(dates, spo2_avgs, spo2_mins) if a is not None]
    if valid_o:
        od, oa, omn = zip(*valid_o)
        ax.plot(od, oa, color="#2563eb", linewidth=1.5, label="Daily Avg")
        ax.plot(od, omn, color="#dc2626", linewidth=1, linestyle="--", label="Daily Min")
        ax.axhline(y=90, color="#9ca3af", linewidth=0.8, linestyle=":", label="Concern threshold (90%)")
    ax.set_title("SpO2 (%)", fontsize=11, fontweight="bold")
    ax.set_ylabel("%", fontsize=9)
    ax.legend(fontsize=7)
    ax.tick_params(axis="x", rotation=45, labelsize=7)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))

    # Respiration
    resp_avgs = [d["respiration"]["avg"] for d in daily]
    resp_mins = [d["respiration"]["min"] for d in daily]
    resp_maxs = [d["respiration"]["max"] for d in daily]
    ax = axes[1, 1]
    valid_r = [(d, a, mn, mx) for d, a, mn, mx in zip(dates, resp_avgs, resp_mins, resp_maxs) if a is not None]
    if valid_r:
        rd, ra, rmn, rmx = zip(*valid_r)
        ax.fill_between(rd, rmn, rmx, alpha=0.15, color="#0d9488", label="Min-Max range")
        ax.plot(rd, ra, color="#0d9488", linewidth=1.5, label="Daily Avg")
    ax.set_title("Respiration (br/min)", fontsize=11, fontweight="bold")
    ax.set_ylabel("br/min", fontsize=9)
    ax.legend(fontsize=7)
    ax.tick_params(axis="x", rotation=45, labelsize=7)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))

    # HRV
    hrv_nightly = [d["hrv"]["nightly_avg"] for d in daily]
    hrv_weekly = [d["hrv"]["weekly_avg"] for d in daily]
    ax = axes[2, 0]
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
    ax = axes[2, 1]
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

    plt.tight_layout()
    output_path = output_dir / "dashboard_overview.png"
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {output_path}")


def generate_distribution_charts(data_dir: Path, output_dir: Path):
    """Generate distribution charts for key metrics — EDA view."""
    agg = load_aggregates(data_dir)
    daily = agg["daily"]

    fig, axes = plt.subplots(2, 3, figsize=(16, 8))
    fig.suptitle("Daily Metric Distributions — EDA Inspection", fontsize=14, fontweight="bold")

    metrics = [
        ("Heart Rate Avg (bpm)", [d["heart_rate"]["avg"] for d in daily], "#dc2626"),
        ("Stress Avg (0-100)", [d["stress"]["avg"] for d in daily], "#ea580c"),
        ("SpO2 Avg (%)", [d["spo2"]["avg"] for d in daily], "#2563eb"),
        ("Respiration Avg (br/min)", [d["respiration"]["avg"] for d in daily], "#0d9488"),
        ("HRV Nightly (ms)", [d["hrv"]["nightly_avg"] for d in daily], "#7c3aed"),
        ("Skin Temp Dev (\u00b0C)", [d["skin_temp"]["deviation"] for d in daily], "#d97706"),
    ]

    for ax, (title, values, color) in zip(axes.flat, metrics):
        valid = [v for v in values if v is not None]
        if valid:
            ax.hist(valid, bins=15, color=color, alpha=0.7, edgecolor="white")
            # Add summary stats
            mean = np.mean(valid)
            median = np.median(valid)
            std = np.std(valid)
            ax.axvline(mean, color="black", linewidth=1, linestyle="--", label=f"Mean: {mean:.1f}")
            ax.axvline(median, color="gray", linewidth=1, linestyle="-", label=f"Median: {median:.1f}")
            ax.set_xlabel(f"n={len(valid)}, sd={std:.1f}", fontsize=8)
            ax.legend(fontsize=7)
            # Check for missingness
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


def generate_minmax_vs_iqr_comparison(data_dir: Path, output_dir: Path):
    """Side-by-side comparison: min/max bands vs IQR bands for heart rate.

    This is the diagnostic chart that shows WHY min/max bands are bad.
    """
    agg = load_aggregates(data_dir)
    dates = parse_dates(agg["days"])
    daily = agg["daily"]

    avgs = [d["heart_rate"]["avg"] for d in daily]
    mins = [d["heart_rate"]["min"] for d in daily]
    maxs = [d["heart_rate"]["max"] for d in daily]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 5), sharey=True)
    fig.suptitle("Heart Rate: Min/Max Bands vs IQR Bands — Readability Comparison",
                 fontsize=13, fontweight="bold")

    # Left: min/max (current approach)
    valid = [(d, a, mn, mx) for d, a, mn, mx in zip(dates, avgs, mins, maxs) if a is not None]
    if valid:
        vd, va, vmn, vmx = zip(*valid)
        ax1.fill_between(vd, vmn, vmx, alpha=0.2, color="#dc2626", label="Min-Max")
        ax1.plot(vd, va, color="#dc2626", linewidth=1.5, label="Avg")
    ax1.set_title("Current: Min/Max Bands", fontsize=11)
    ax1.set_ylabel("bpm", fontsize=9)
    ax1.legend(fontsize=8)
    ax1.tick_params(axis="x", rotation=45, labelsize=7)
    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
    # Annotate the problem
    if valid:
        band_height = max(vmx) - min(vmn)
        avg_range = max(va) - min(va)
        ratio = band_height / avg_range if avg_range > 0 else float("inf")
        ax1.text(0.02, 0.02, f"Band height: {band_height:.0f} bpm\nAvg variation: {avg_range:.0f} bpm\nRatio: {ratio:.1f}x",
                 transform=ax1.transAxes, fontsize=8, va="bottom",
                 bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.8))

    # Right: simulated IQR (using approximate percentiles from daily avg±spread)
    # Since we only have daily aggregates, simulate IQR as avg±(avg-min)*0.4
    # This is approximate but shows the visual improvement
    iqr_lo = [a - (a - mn) * 0.4 if a and mn else None for a, mn in zip(avgs, mins)]
    iqr_hi = [a + (mx - a) * 0.4 if a and mx else None for a, mx in zip(avgs, maxs)]

    valid2 = [(d, a, lo, hi) for d, a, lo, hi in zip(dates, avgs, iqr_lo, iqr_hi) if a is not None]
    if valid2:
        vd2, va2, vlo, vhi = zip(*valid2)
        ax2.fill_between(vd2, vlo, vhi, alpha=0.25, color="#dc2626", label="~IQR (25th-75th)")
        ax2.plot(vd2, va2, color="#dc2626", linewidth=1.5, label="Avg")
    ax2.set_title("Better: IQR Bands (estimated)", fontsize=11)
    ax2.legend(fontsize=8)
    ax2.tick_params(axis="x", rotation=45, labelsize=7)
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
    if valid2:
        band2 = max(vhi) - min(vlo)
        ax2.text(0.02, 0.02, f"Band height: {band2:.0f} bpm\nAvg variation: {avg_range:.0f} bpm\nRatio: {band2/avg_range:.1f}x",
                 transform=ax2.transAxes, fontsize=8, va="bottom",
                 bbox=dict(boxstyle="round", facecolor="lightgreen", alpha=0.8))

    plt.tight_layout()
    output_path = output_dir / "minmax_vs_iqr.png"
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {output_path}")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Generate chart images for visual inspection")
    parser.add_argument("--data-dir", type=Path, default=PROJECT_ROOT / "data")
    parser.add_argument("--output-dir", type=Path, default=PROJECT_ROOT / ".claude" / "chart-inspections")
    parser.add_argument("--chart", choices=["all", "dashboard", "distributions", "minmax"],
                        default="all", help="Which charts to generate")
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)

    if args.chart in ("all", "dashboard"):
        generate_dashboard_charts(args.data_dir, args.output_dir)
    if args.chart in ("all", "distributions"):
        generate_distribution_charts(args.data_dir, args.output_dir)
    if args.chart in ("all", "minmax"):
        generate_minmax_vs_iqr_comparison(args.data_dir, args.output_dir)

    print(f"\nAll charts saved to: {args.output_dir}")
    print("Read the PNG files to visually inspect them.")


if __name__ == "__main__":
    main()
