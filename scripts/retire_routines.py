#!/usr/bin/env python3
"""Retire the v2 training routines and their card templates (status -> retired).

Idempotent: a second run reports 0 changes. Never touches card_logs.
Usage: cd backend && uv run python ../scripts/retire_routines.py
"""
# ruff: noqa: E402, I001
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from app.bootstrap.schema import init_storage
from app.domains.routines.adapters import (
    load_card_templates,
    load_routine_assignments,
    load_routine_schedules,
    save_card_template,
    save_routine_schedule,
)

RETIRE_ROUTINES = [
    "four-week-running-calibration-patched-routine",
    "four-week-running-meditation-transfer-routine",
    "four-week-running-support-calibration-routine",
    "four-week-strength-running-calibration-routine",
    "two-week-core-foundation-routine",
]


def main() -> None:
    init_storage()
    changed = 0
    retired_template_ids: set[str] = set()
    for routine in load_routine_schedules():
        if routine.id in RETIRE_ROUTINES and routine.status == "active":
            save_routine_schedule(routine.model_copy(update={"status": "retired"}))
            retired_template_ids.update(
                a.card_template_id for a in load_routine_assignments(routine.id)
            )
            changed += 1
    # retire templates referenced ONLY by retired routines
    active_template_ids = {
        a.card_template_id
        for r in load_routine_schedules()
        if r.status == "active"
        for a in load_routine_assignments(r.id)
    }
    t_changed = 0
    for template in load_card_templates():
        if (
            template.id in retired_template_ids
            and template.id not in active_template_ids
            and template.status == "active"
        ):
            save_card_template(template.model_copy(update={"status": "retired"}))
            t_changed += 1
    print(f"retired {changed} routines, {t_changed} card templates")


if __name__ == "__main__":
    main()
