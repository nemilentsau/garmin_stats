#!/usr/bin/env python3
"""Translate the Block 0 v3 bundles into one derived schema_version-2 import bundle.

Reads the canonical v3 sources in docs/routine-pivot/block0/ and writes
docs/routine_bundles/block0_v3_derived.json. The output is a build artifact:
regenerate on any source change, never hand-edit. Per-day variation lands in
each assignment's prescription_override_json; selection rules are rendered to
plain English for display; variant ids become variant_options for branch
logging. Asserts weekly run miles against lint_report.json so translation
drift fails loudly.

Usage: python3 scripts/translate_block0.py
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SRC = REPO / "docs" / "routine-pivot" / "block0"
OUT = REPO / "docs" / "routine_bundles" / "block0_v3_derived.json"

START_DATE = "2026-07-06"
END_DATE = "2026-08-02"
TISSUES = ["quad", "glute", "hamstring", "calf_achilles", "soleus", "tibialis_foot"]
POSITION = {"sup.daily": 0, "run": 1, "str": 10, "sup.hsr": 11}


def _load(name: str) -> dict:
    return json.loads((SRC / name).read_text(encoding="utf-8"))


def signal_name(sig: str) -> str:
    if sig.startswith("soreness."):
        return sig.split(".", 1)[1].replace("_", " ") + " soreness"
    if sig.startswith("flag.tissue."):
        return sig.split(".", 2)[2].replace("_", " ") + " flag"
    return {
        "hrv.dev_swc": "HRV (SWC units)",
        "rhr.delta_7d": "RHR delta (bpm)",
        "sleep.score": "sleep score",
        "env.dew_point": "dew point (°C)",
        "event.ev_lthr_test.completed": "LTHR test already completed",
    }.get(sig, sig)


def render_cmp(p: dict) -> str:
    name = signal_name(p["signal"])
    if p["op"] == "==" and p["value"] is True:
        return name
    if p["op"] == "==" and p["value"] is False:
        return f"not {name}"
    return f"{name} {p['op']} {p['value']}"


def render_pred(p: dict) -> str:
    if "all" in p:
        return " and ".join(render_pred(q) for q in p["all"])
    if "any" in p:
        return " or ".join(render_pred(q) for q in p["any"])
    if "not" in p:
        return f"not ({render_pred(p['not'])})"
    return render_cmp(p)


def render_rule(selection: dict, variants: list[dict], base_pres: dict | None = None) -> str:
    parts = [
        f"{cl['select'].capitalize().replace('_', ' ')} if {render_pred(cl['when'])}"
        for cl in selection["clauses"]
    ]
    parts.append(f"otherwise {selection['default']}")
    if selection.get("on_missing_signal") == "select_conservative":
        parts.append("missing data → conservative")
    text = "; ".join(parts) + "."
    extras = []
    if base_pres is not None:
        full = next((v for v in variants if v["id"] == "full"), None)
        full_pres = apply_patch(base_pres, (full or {}).get("prescription_patch"))
        full_mi = sum(s.get("distance_mi", 0) for s in full_pres.get("segments", []))
        for v in variants:
            if v["id"] == "full" or not v.get("prescription_patch"):
                continue
            merged = apply_patch(base_pres, v["prescription_patch"])
            mi = sum(s.get("distance_mi", 0) for s in merged.get("segments", []))
            if mi and abs(mi - full_mi) > 1e-9:
                extras.append(f"{v['id'].replace('_', ' ')} = {mi:g} mi")
    if extras:
        text += " (" + "; ".join(extras) + ")"
    return text


def seg_kind(label: str) -> str:
    low = label.lower()
    if "warmup" in low:
        return "warmup"
    if "cooldown" in low:
        return "cooldown"
    if "stride" in low or "primer" in low or "drill" in low:
        return "strides"
    return "main"


def seg_prescription(seg: dict) -> str:
    parts = []
    if seg.get("distance_mi"):
        parts.append(f"{seg['distance_mi']:g} mi")
    if seg.get("duration_min"):
        parts.append(f"{seg['duration_min']:g} min")
    intensity = seg.get("intensity") or {}
    if intensity.get("zone"):
        parts.append(intensity["zone"])
    elif intensity.get("rpe") is not None:
        parts.append(f"RPE {intensity['rpe']}")
    elif intensity.get("hr_range"):
        lo, hi = intensity["hr_range"]
        parts.append(f"HR {lo}–{hi}")
    return " · ".join(parts) or "—"


def run_segments(pres: dict, card_id: str) -> list[dict]:
    return [
        {
            "id": f"{card_id}.seg{i}",
            "label": s["label"],
            "kind": seg_kind(s["label"]),
            "detail": None,
            "prescription": seg_prescription(s),
        }
        for i, s in enumerate(pres.get("segments", []), 1)
    ]


def apply_patch(pres: dict, patch: dict | None) -> dict:
    """Index-merge segment patches, mirroring the v3 linter's apply_full_patch."""
    out = json.loads(json.dumps(pres))
    if patch and "segments" in patch:
        for i, p in enumerate(patch["segments"]):
            if i < len(out.get("segments", [])):
                out["segments"][i].update(p)
    return out


def set_scheme(x: dict) -> str:
    lo, hi = x["reps"]
    scheme = f"{x['sets']}×{lo}–{hi}" if lo != hi else f"{x['sets']}×{lo}"
    load = x.get("load") or {}
    if load.get("pct_e1rm"):
        scheme += f" @ {round(load['pct_e1rm'] * 100)}% e1RM"
    elif load.get("rpe") is not None:
        scheme += f" @ RPE {load['rpe']}"
    elif load.get("absolute_kg"):
        scheme += f" @ {load['absolute_kg']:g} kg"
    return scheme


def running_payload(card: dict) -> dict:
    instructions = []
    if card["contract"]["kind"] == "measurement":
        gates = "; ".join(render_cmp(g) for g in card["contract"]["quality_gate"])
        instructions.append(f"Measurement: {card['contract']['estimand']}. Gate: {gates}.")
    if card.get("display_notes"):
        instructions.append(card["display_notes"])
    return {
        "card_type": "running_workout",
        "workout_type": card["name"],
        "calibration_quality": card["contract"]["kind"] == "measurement",
        "instructions": " ".join(instructions) or None,
        "segments": run_segments(card["prescription"], card["id"]),
        "post_run_fields": [],
    }


def strength_payload(card: dict, exlib: dict) -> dict:
    return {
        "card_type": "strength_session",
        "session_focus": card["name"],
        "duration_minutes": card.get("est_duration_min"),
        "rir_guidance": "Prescriptions are RPE; log RIR (RIR ≈ 10 − RPE).",
        "instructions": card.get("display_notes"),
        "exercises": [
            {
                "id": x["exercise_id"],
                "label": exlib[x["exercise_id"]]["name"],
                "detail": x.get("tempo"),
                "set_scheme": set_scheme(x),
            }
            for x in card["prescription"]["exercises"]
        ],
        "rating_prompts": [],
    }


def checkin_payload() -> dict:
    items = [
        {
            "id": f"tissue.{t}",
            "label": t.replace("_", " / "),
            "detail": None,
            "kind": "tissue_check",
        }
        for t in TISSUES
    ]
    items.append({
        "id": "core_done",
        "label": "Habitual core + mobility done (≤15 min)",
        "detail": None,
        "kind": "checkbox",
    })
    return {
        "card_type": "checklist",
        "instructions": (
            "Morning check-in: rate soreness 0–3 per tissue; "
            "flag = pain above background noise. Rules read this — skipping it "
            "sends every card conservative."
        ),
        "items": items,
        "domain": "running",
    }


def _position(card_id: str) -> int:
    for prefix, pos in POSITION.items():
        if card_id.startswith(prefix):
            return pos
    return 5


def _sources() -> tuple[list[dict], dict, dict]:
    bundles = [_load("running_v3.json"), _load("strength_v3.json"), _load("support_v3.json")]
    exlib = {e["id"]: e for e in _load("exercise_library.json")["exercises"]}
    lint = _load("lint_report.json")
    return bundles, exlib, lint


def build_bundle() -> dict:
    bundles, exlib, _ = _sources()
    cards = {c["id"]: c for b in bundles for c in b["cards"]}

    templates = []
    for cid, card in cards.items():
        if cid == "sup.daily":
            payload = checkin_payload()
            slot = "morning"
        elif "exercises" in card["prescription"]:
            payload = strength_payload(card, exlib)
            slot = "midday"
        else:
            payload = running_payload(card)
            slot = "morning"
        templates.append({
            "id": cid,
            "name": card["name"],
            "slot_default": slot,
            "summary": f"{card['contract']['kind']} · est {card.get('est_duration_min', '?')} min",
            "tags": ["block0", "v3-derived", card["contract"]["kind"]],
            "payload": payload,
        })

    assignments = []
    for b in bundles:
        for a in b["assignments"]:
            card = cards[a["card_id"]]
            full = next(v for v in a["variants"] if v["id"] == "full")
            pres = apply_patch(card["prescription"], full.get("prescription_patch"))
            override: dict = {}
            if len(a["variants"]) >= 2:
                override["variant_options"] = [v["id"] for v in a["variants"]]
            if a["selection"]["clauses"]:
                override["selection_rule"] = render_rule(
                    a["selection"], a["variants"], card["prescription"]
                )
            if "segments" in card["prescription"] and card["id"] != "sup.daily":
                override["segments"] = run_segments(pres, card["id"])
            if a.get("key_session"):
                base = running_payload(card)["instructions"] or ""
                override["instructions"] = (base + " Key session — protect it.").strip()
            assignments.append({
                "id": f"{card['id']}.d{a['day']:02d}",
                "card_template_id": card["id"],
                "day": a["day"],
                "slot": a["slot"],
                "position": _position(card["id"]),
                "prescription_override_json": override,
            })

    assignments.sort(key=lambda x: (x["day"], x["slot"], x["position"]))
    return {
        "id": "block0-v3-derived",
        "name": "Block 0 — Calibration (derived from v3)",
        "schema_version": 2,
        "description": (
            "DERIVED ARTIFACT — generated by scripts/translate_block0.py from "
            "docs/routine-pivot/block0/. Do not hand-edit; regenerate instead."
        ),
        "card_templates": templates,
        "routine_specs": [{
            "id": "block0-calibration-routine",
            "name": "Block 0 — Calibration",
            "start_date": START_DATE,
            "end_date": END_DATE,
            "status": "active",
            "tags": ["block0", "v3-derived"],
            "notes": (
                "Window per docs/routine-pivot/block0/block0.json; "
                "week 1 burn-in, baselines from day 8."
            ),
            "assignments": assignments,
        }],
    }


def weekly_miles() -> dict[int, float]:
    bundles, _, _ = _sources()
    cards = {c["id"]: c for b in bundles for c in b["cards"]}
    miles: dict[int, float] = defaultdict(float)
    for b in bundles:
        if b["id"] != "running.v3":
            continue
        for a in b["assignments"]:
            full = next(v for v in a["variants"] if v["id"] == "full")
            pres = apply_patch(cards[a["card_id"]]["prescription"], full.get("prescription_patch"))
            miles[(a["day"] - 1) // 7 + 1] += sum(
                s.get("distance_mi", 0) for s in pres.get("segments", [])
            )
    return {w: round(m, 1) for w, m in sorted(miles.items())}


def main() -> None:
    _, _, lint = _sources()
    expected = {int(k): v for k, v in lint["week_run_miles"].items()}
    actual = weekly_miles()
    if actual != expected:
        raise SystemExit(f"weekly miles drift: derived {actual} != linted {expected}")
    bundle = build_bundle()
    OUT.write_text(json.dumps(bundle, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {OUT} ({len(bundle['card_templates'])} templates, "
          f"{len(bundle['routine_specs'][0]['assignments'])} assignments); "
          f"weekly miles {actual} == lint report")


if __name__ == "__main__":
    main()
