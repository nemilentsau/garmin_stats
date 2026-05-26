#!/usr/bin/env python3
"""Freeze the persisted daily-metric mart to a flat CSV snapshot for analyst runs.

A finding rests on specific data. Re-running an analysis months later may produce
different numbers because the dataset grew; the snapshot lets a reviewer reproduce
the original numbers. This reuses the same path the dashboard and inspect_charts.py
use (`parse_all_days -> compute_daily_metrics`), so the snapshot matches the product's
source of statistical truth rather than re-aggregating from raw FIT files.

Output is CSV via the stdlib only (no pandas / pyarrow dependency). Nested per-metric
stats are flattened to `<metric>_<field>` columns (e.g. `hrv_nightly_avg`,
`heart_rate_resting`, `sleep_score`). List-valued fields (HR zones) are dropped.

Usage (from backend/, so the app package and its venv are importable):
    cd backend && uv run python ../.claude/skills/finding-analyst/scripts/export_snapshot.py \
        --out ../.claude/finding-runs/<run>/08-snapshot/daily.csv

    # restrict to a window
    ... --start 2026-02-01 --end 2026-03-15

A coverage/missingness summary is printed to stderr so it can be pasted into
02-data-profile.md.
"""

from __future__ import annotations

import argparse
import csv
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent.parent.parent
BACKEND_DIR = PROJECT_ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import get_app_config
from app.domains.garmin_health.domain.daily import compute_daily_metrics
from app.parser import parse_all_days


def _flatten(metric: dict) -> dict:
    """Flatten one DailyMetric.model_dump() to scalar `<metric>_<field>` columns.

    Nested stat blocks become `block_field`; top-level scalars keep their name;
    list fields (e.g. HR zones) are dropped — analyst runs needing zones read the
    model directly.
    """
    row: dict[str, object] = {}
    for key, value in metric.items():
        if isinstance(value, dict):
            for sub_key, sub_value in value.items():
                if isinstance(sub_value, (list, dict)):
                    continue
                row[f"{key}_{sub_key}"] = sub_value
        elif isinstance(value, list):
            continue
        else:
            row[key] = value
    return row


def _in_window(date_str: str, start: str | None, end: str | None) -> bool:
    if start and date_str < start:
        return False
    if end and date_str > end:
        return False
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True, help="Destination CSV path.")
    parser.add_argument("--start", help="Inclusive YYYY-MM-DD lower bound.")
    parser.add_argument("--end", help="Inclusive YYYY-MM-DD upper bound.")
    args = parser.parse_args()

    config = get_app_config()
    days = parse_all_days(config.data_dir)
    metrics = compute_daily_metrics(days)

    rows = [
        _flatten(m.model_dump())
        for m in metrics
        if _in_window(m.date, args.start, args.end)
    ]
    rows.sort(key=lambda r: r["date"])
    if not rows:
        print("No daily metrics in the requested window.", file=sys.stderr)
        return 1

    # Stable column order: date first, then the rest sorted for reproducibility.
    columns = ["date"] + sorted({c for r in rows for c in r} - {"date"})

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    _print_summary(rows, columns, args.out)
    return 0


def _print_summary(rows: list[dict], columns: list[str], out: Path) -> None:
    n = len(rows)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
    print(f"# snapshot frozen {stamp}", file=sys.stderr)
    print(f"wrote {n} rows to {out}", file=sys.stderr)
    print(f"date range {rows[0]['date']} .. {rows[-1]['date']}", file=sys.stderr)
    print("per-column missingness (None/empty):", file=sys.stderr)
    for col in columns:
        if col == "date":
            continue
        missing = sum(1 for r in rows if r.get(col) in (None, ""))
        if missing:
            print(f"  {col}: {missing}/{n} ({missing / n:.1%})", file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
