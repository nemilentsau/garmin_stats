"""Render representative real-data coach plots and a source-value manifest."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import date
from pathlib import Path
from typing import cast

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.bootstrap.container import build_container  # noqa: E402
from app.domains.coach.infra.plots import (
    available_current_channels,
    render_current_run_stack,
    render_library_panel,
)  # noqa: E402


def _select_auto_ids(limit: int = 50) -> list[str]:
    gateway = build_container().coach_gateway
    runs = gateway.recent_runs(evidence_date=date.today().isoformat(), limit=limit)
    details = [(run.id, gateway.run_detail(run.id)) for run in runs]
    selected: list[str] = []

    strap = next(
        (
            run_id
            for run_id, detail in details
            if detail.session.hr_source == "strap" and detail.session.has_running_dynamics
        ),
        None,
    )
    if strap is not None:
        selected.append(strap)

    sparse = next(
        (
            run_id
            for run_id, detail in details
            if run_id not in selected
            and (detail.session.hr_source != "strap" or not detail.session.has_running_dynamics)
        ),
        None,
    )
    if sparse is not None:
        selected.append(sparse)

    remaining = [item for item in details if item[0] not in selected]
    lap_rich = max(remaining, key=lambda item: len(item[1].laps), default=(None, None))[0]
    if lap_rich is not None and lap_rich not in selected:
        selected.append(lap_rich)

    if not selected and runs:
        selected.append(runs[0].id)
    return selected


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", action="append", default=[])
    parser.add_argument("--auto-sample", action="store_true")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if not args.run_id and not args.auto_sample:
        parser.error("provide at least one --run-id or --auto-sample")

    explicit_ids = cast(list[str], args.run_id)
    run_ids: list[str] = list(
        dict.fromkeys([*explicit_ids, *(_select_auto_ids() if args.auto_sample else [])])
    )
    if not run_ids:
        raise SystemExit("No run sessions available for plot inspection")

    output_dir = cast(Path, args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    cache_dir = output_dir / "cache"
    gateway = build_container().coach_gateway
    manifest: list[dict[str, object]] = []
    for index, run_id in enumerate(run_ids, start=1):
        detail = gateway.run_detail(run_id)
        series = gateway.run_series(run_id)
        library_path = render_library_panel(cache_dir, detail, series)
        inspection_panel = output_dir / f"02-eda-{index:02d}-{run_id}-historical.png"
        shutil.copy2(library_path, inspection_panel)
        stack_paths = render_current_run_stack(cache_dir, detail, series)
        inspection_stacks: list[str] = []
        for page, stack_path in enumerate(stack_paths, start=1):
            destination = output_dir / (f"02-eda-{index:02d}-{run_id}-current-p{page:02d}.png")
            shutil.copy2(stack_path, destination)
            inspection_stacks.append(destination.name)
        manifest.append(
            {
                "run_id": run_id,
                "session_date": detail.session.session_date,
                "activity_name": detail.session.activity_name,
                "hr_source": detail.session.hr_source,
                "lap_count": len(detail.laps),
                "record_count": len(series.series.elapsed_s),
                "channels": available_current_channels(series),
                "display": detail.display.model_dump(mode="json"),
                "historical_panel": inspection_panel.name,
                "current_stack": inspection_stacks,
            }
        )
    (output_dir / "source-values.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Rendered {len(run_ids)} run(s) into {output_dir}")


if __name__ == "__main__":
    main()
