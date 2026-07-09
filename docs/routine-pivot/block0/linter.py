#!/usr/bin/env python3
"""v3 linter: compiles the integrated schedule and enforces L1-L12."""
import json, re, sys, itertools
from collections import defaultdict

B = "/home/claude/v3/build"
load = lambda n: json.load(open(f"{B}/{n}"))

registry = load("registry.json")
block = load("block0.json")
bundles = {bid: load(f"{bid.replace('.v3','_v3')}.json") for bid in block["bundle_ids"]}
exlib = {e["id"]: e for e in load("exercise_library.json")["exercises"]}

SLOT_HOUR = {"morning": 7, "midday": 13, "evening": 19}
errors, warnings = [], []
def err(rule, msg): errors.append(f"[{rule}][ERROR] {msg}")
def warn(rule, msg): warnings.append(f"[{rule}][WARN ] {msg}")

signals = {s["id"] for s in registry["signals"]}
estimators = {e["id"]: e for e in registry["estimators"]}
est_out = {e["output_signal"] for e in registry["estimators"]}
state_ids = {s["id"] for s in registry["state_vector"]}

cards = {}
for b in bundles.values():
    for c in b["cards"]:
        cards[c["id"]] = c

# ---------- compile ----------
schedule = []  # entries: day, slot, bundle, card, assignment
for bid, b in bundles.items():
    for a in b["assignments"]:
        if a["card_id"] not in cards:
            err("L1", f"{bid}: assignment day {a['day']} references unknown card {a['card_id']}")
            continue
        schedule.append({"day": a["day"], "slot": a["slot"], "bundle": bid,
                         "card": cards[a["card_id"]], "assign": a})
schedule.sort(key=lambda e: (e["day"], SLOT_HOUR.get(e["slot"], 99)))

def seg_miles(pres):
    return sum(s.get("distance_mi", 0) for s in pres.get("segments", []))

def apply_full_patch(card, assign):
    """Resolve the full-variant prescription (volume-only patches on 'full')."""
    full = next(v for v in assign["variants"] if v["id"] == "full")
    pres = json.loads(json.dumps(card["prescription"]))
    patch = full.get("prescription_patch")
    if patch and "segments" in patch:
        for i, p in enumerate(patch["segments"]):
            if i < len(pres.get("segments", [])):
                pres["segments"][i].update(p)
    return pres

def entry_minutes(e):
    c = e["card"]
    if c.get("est_duration_min"):
        base = c["est_duration_min"]
        # scale run cards whose full variant overrides distance
        if "segments" in c["prescription"] and any(s.get("distance_mi") for s in c["prescription"]["segments"]):
            base_mi = seg_miles(c["prescription"])
            full_mi = seg_miles(apply_full_patch(c, e["assign"]))
            if base_mi > 0 and full_mi > 0:
                return base * full_mi / base_mi
        return base
    return 0

compiled = {"days": []}
week_miles = defaultdict(float)
week_minutes = defaultdict(lambda: defaultdict(float))  # week -> bundle -> min
for day in range(1, block["window"]["days"] + 1):
    day_entries = [e for e in schedule if e["day"] == day]
    tissues = set()
    run_mi = 0.0
    for e in day_entries:
        pres = apply_full_patch(e["card"], e["assign"])
        if "segments" in pres and e["bundle"] == "running.v3":
            run_mi += seg_miles(pres)
        for x in pres.get("exercises", []):
            tissues.update(x.get("targets", []))
            tissues.update(x.get("involves", []))
        wk = (day - 1) // 7 + 1
        week_minutes[wk][e["bundle"]] += entry_minutes(e)
    wk = (day - 1) // 7 + 1
    week_miles[wk] += run_mi
    compiled["days"].append({"day": day, "run_miles": round(run_mi, 1),
                             "tissues_loaded": sorted(tissues),
                             "entries": [{"slot": e["slot"], "bundle": e["bundle"],
                                          "card": e["card"]["id"]} for e in day_entries]})
json.dump(compiled, open(f"{B}/compiled_schedule.json", "w"), indent=2)

# ---------- L1 contract completeness ----------
REQ = {"overload": ["adaptation", "progression_driver", "state_ref"],
       "maintenance": ["preserves", "minimum_effective_dose", "intensity_floor"],
       "measurement": ["estimand", "quality_gate", "on_fail"],
       "recovery": ["load_ceiling"]}
for cid, c in cards.items():
    k = c.get("contract", {}).get("kind")
    if k not in REQ:
        err("L1", f"{cid}: missing or unknown contract kind {k}"); continue
    for f in REQ[k]:
        if f not in c["contract"]:
            err("L1", f"{cid}: contract kind {k} missing field {f}")
    sr = c["contract"].get("state_ref") or c["contract"].get("preserves")
    if sr and sr not in state_ids:
        err("L1", f"{cid}: contract references unknown state component {sr}")

# ---------- L2 ownership ----------
tissue_owner = {}
for bid, b in bundles.items():
    for t in b.get("owns", []):
        if t in tissue_owner:
            err("L2", f"tissue {t} owned by both {tissue_owner[t]} and {bid}")
        tissue_owner[t] = bid
for bid, b in bundles.items():
    for c in b["cards"]:
        for x in c["prescription"].get("exercises", []):
            for t in x.get("targets", []):
                own = tissue_owner.get(t)
                if own is None:
                    err("L2", f"{c['id']}: targets unowned tissue {t}")
                elif own != bid:
                    err("L2", f"{c['id']} ({bid}) targets {t} owned by {own}")

# ---------- L3 budgets ----------
for bid, b in bundles.items():
    for bud in b.get("declared_budgets", []):
        for wk in range(1, 5):
            m = week_minutes[wk][bid]
            if m > bud["minutes_max"] + 1e-6:
                err("L3", f"{bid} week {wk}: scheduled {m:.0f} min > declared max {bud['minutes_max']}")
            if bud.get("minutes_min") and m < bud["minutes_min"] - 1e-6:
                err("L3", f"{bid} week {wk}: scheduled {m:.0f} min < declared min {bud['minutes_min']}")

# ---------- L4 prose conditionals ----------
BAD = re.compile(r"\b(if|unless|only if|skip|instead|optional|coordinate)\b", re.I)
for cid, c in cards.items():
    note = c.get("display_notes", "")
    if note and BAD.search(note):
        err("L4", f"{cid}: display_notes contains conditional/coordination language: '{note[:60]}...'")

# ---------- L5 scheduling constraints ----------
def entries_matching(forbid):
    out = []
    for e in schedule:
        c = e["card"]
        if forbid.get("contract_kind") and c["contract"]["kind"] not in forbid["contract_kind"]:
            continue
        if forbid.get("targets"):
            tg = set()
            for x in c["prescription"].get("exercises", []):
                tg.update(x.get("targets", []))
            if not tg & set(forbid["targets"]):
                continue
        out.append(e)
    return out

def hours(e): return (e["day"] - 1) * 24 + SLOT_HOUR.get(e["slot"], 12)

for sc in block.get("scheduling_constraints", []):
    ref = sc["reference"]
    if ref.get("per_tissue_duplicate"):
        # no tissue targeted by two overload cards on the same day
        per_day = defaultdict(lambda: defaultdict(list))
        for e in schedule:
            if e["card"]["contract"]["kind"] != "overload": continue
            for x in e["card"]["prescription"].get("exercises", []):
                for t in x.get("targets", []):
                    per_day[e["day"]][t].append(e["card"]["id"])
        for day, tmap in per_day.items():
            for t, cl in tmap.items():
                if len(set(cl)) > 1:
                    err("L5", f"{sc['id']}: day {day} tissue {t} targeted by multiple overloads {sorted(set(cl))}")
        continue
    refs = [e for e in schedule if e["card"]["id"] == ref.get("card_id")]
    cand = entries_matching(sc["forbid"])
    for r in refs:
        for e in cand:
            if e is r or e["card"]["id"] == ref.get("card_id"): continue
            dt = hours(r) - hours(e)
            if sc["relation"] == "within_hours_before" and 0 < dt <= sc["hours"]:
                err("L5", f"{sc['id']}: {e['card']['id']} (day {e['day']} {e['slot']}) within {sc['hours']}h before {r['card']['id']} (day {r['day']})")
            if sc["relation"] == "same_day_as" and e["day"] == r["day"]:
                err("L5", f"{sc['id']}: {e['card']['id']} same day as {r['card']['id']} (day {r['day']})")

# ---------- L6 measurement integrity + signal closure ----------
for ev in block.get("measurement_events", []):
    if ev["required"] and not ev.get("backup_days"):
        err("L6", f"event {ev['id']}: required but no backup_days")
    if ev["card_id"] not in cards:
        err("L6", f"event {ev['id']}: unknown card {ev['card_id']}")
cap_fields = {}
for cid, c in cards.items():
    for cp in c.get("capture", []):
        cap_fields[cp["id"]] = cp
        m = cp.get("contract", {}).get("model_id")
        if not m:
            err("L6", f"{cid}: capture field {cp['id']} missing AnalysisContract")
        elif m not in estimators:
            err("L6", f"{cid}: capture {cp['id']} references unknown estimator {m}")
for e in registry["estimators"]:
    if e["output_signal"] not in signals:
        err("L6", f"estimator {e['id']} outputs unregistered signal {e['output_signal']}")
# signal consumption: rules + constraints + state + quality gates + criteria + review
consumed = set()
def walk_pred(p):
    if not isinstance(p, dict): return
    if "signal" in p: consumed.add(p["signal"])
    for key in ("all", "any"):
        for q in p.get(key, []): walk_pred(q)
    if "not" in p: walk_pred(p["not"])
for b in bundles.values():
    for a in b["assignments"]:
        for cl in a["selection"]["clauses"]: walk_pred(cl["when"])
for cid, c in cards.items():
    for g in c["contract"].get("quality_gate", []): walk_pred(g)
for cr in block["exit_criteria"]: walk_pred(cr["predicate"])
for cs in registry["objective"]["constraints"]: consumed.add(cs["signal"])
for sc_ in registry["state_vector"]: consumed.add(sc_["signal"])
for rs in block["review_specs"]:
    for cd in rs["computed"]:
        if cd["estimator_id"] in estimators:
            consumed.add(estimators[cd["estimator_id"]]["output_signal"])
for e in registry["estimators"]:
    for inp in e["inputs"]:
        if inp in signals: consumed.add(inp)   # signals feeding models are consumed
orphan_signals = signals - consumed - est_out  # unconsumed AND not produced-for-state
strictly_orphan = {s for s in signals if s not in consumed}
for s in sorted(strictly_orphan):
    err("L6", f"signal {s} is never consumed by any rule, constraint, state, gate, criterion, or review")
# estimator inputs that are capture fields must exist (garmin.*/env.*/compiled.* are ambient)
AMBIENT = ("garmin.", "env.", "compiled.", "load.")
for e in registry["estimators"]:
    for inp in e["inputs"]:
        if inp.startswith("cap.") and "*" not in inp and inp not in cap_fields:
            err("L6", f"estimator {e['id']} input {inp} not captured by any card")

# ---------- L7 state coverage ----------
scheduled_cards = {e["card"]["id"] for e in schedule}
for sc_ in registry["state_vector"]:
    est = estimators.get(sc_["estimator_id"])
    if not est:
        err("L7", f"state {sc_['id']}: unknown estimator {sc_['estimator_id']}"); continue
    covered = False
    for inp in est["inputs"]:
        if not inp.startswith("cap."):
            covered = True; continue
        for cid, c in cards.items():
            ids = [cp["id"] for cp in c.get("capture", [])]
            if (inp in ids or any(inp.rstrip("*") in i for i in ids)) and cid in scheduled_cards:
                covered = True
    if not covered:
        err("L7", f"state {sc_['id']} has no scheduled capture in this block")

# ---------- L8 load rollup ----------
for e in schedule:
    pres = e["card"]["prescription"]
    ok = ("segments" in pres and all(("duration_min" in s or "distance_mi" in s) for s in pres["segments"])) \
         or ("exercises" in pres and all(("sets" in x and "reps" in x and "load" in x) for x in pres["exercises"]))
    if not ok:
        err("L8", f"{e['card']['id']} day {e['day']}: prescription not resolvable to load units")

# ---------- L9 identity coherence ----------
if block["identity"] == "measurement":
    flat = [week_miles[w] for w in block.get("flat_weeks", [])]
    if flat:
        mean = sum(flat) / len(flat)
        for w, m in zip(block["flat_weeks"], flat):
            if abs(m - mean) / mean > 0.03:
                err("L9", f"measurement block: week {w} run volume {m:.1f} mi deviates >3% from flat mean {mean:.1f}")
    # novel overloads must ramp
    for cid, c in cards.items():
        ct = c["contract"]
        if ct["kind"] == "overload" and ct["adaptation"] == "tendon_stiffness" and "ramp" not in ct:
            err("L9", f"{cid}: novel tendon overload in measurement block without declared ramp")

# ---------- L10 anti-theater ----------
INTENSITY_KEYS = {"pct_e1rm", "rpe", "zone"}
for b in bundles.values():
    for a in b["assignments"]:
        vids = [v["id"] for v in a["variants"]]
        if "full" not in vids:
            err("L10", f"{a['card_id']} day {a['day']}: no 'full' variant")
        if a["selection"]["default"] != "full":
            err("L10", f"{a['card_id']} day {a['day']}: default path is '{a['selection']['default']}', must be 'full'")
        for v in a["variants"]:
            if v["id"] == "skip": continue
            if v["stimulus_fraction"] < 0.5:
                err("L10", f"{a['card_id']} day {a['day']}: variant {v['id']} stimulus_fraction {v['stimulus_fraction']} < 0.5")
            if v["id"] == "full" and v.get("prescription_patch"):
                for s in v["prescription_patch"].get("segments", []):
                    if set(s.keys()) & {"intensity"}:
                        err("L10", f"{a['card_id']} day {a['day']}: full-variant patch modifies intensity")
        # rules may never select 'plus'
        for cl in a["selection"]["clauses"]:
            if cl["select"] == "plus":
                err("L10", f"{a['card_id']} day {a['day']}: rule selects 'plus'; plus is override-only")
        card = cards[a["card_id"]]
        if card["contract"]["kind"] == "overload" and "ramp" in card["contract"]:
            if "endpoint" not in card["contract"]["ramp"]:
                err("L10", f"{a['card_id']}: ramp without endpoint")
    for c in b["cards"]:
        if c["contract"]["kind"] == "maintenance":
            fl = c["contract"]["intensity_floor"]
            # (variants for these cards are volume patches only; enforced above)
            if not fl.get("metric"):
                err("L10", f"{c['id']}: maintenance intensity_floor malformed")

# ---------- L11 novelty ----------
novel = 3  # new lifting structure, HSR loading, plyo primer formalization
if novel > 2 and "protocol-change" not in block["baseline_tags"]:
    warn("L11", "week 1 introduces >2 novel elements without protocol-change tag")

# ---------- L12 exit criteria ----------
if not block.get("exit_criteria"):
    err("L12", "block missing exit_criteria")
if block["identity"] == "measurement":
    if not block.get("extension_rules"):
        err("L12", "measurement block missing extension_rules")
    for r in block.get("extension_rules", []):
        if "cap_total_extension_days" not in r:
            err("L12", f"extension rule {r.get('when_failed')} missing cap")

# ---------- report ----------
report = {"errors": errors, "warnings": warnings,
          "week_run_miles": {w: round(m, 1) for w, m in sorted(week_miles.items())},
          "week_minutes_by_bundle": {w: {b: round(m) for b, m in d.items()}
                                     for w, d in sorted(week_minutes.items())}}
json.dump(report, open(f"{B}/lint_report.json", "w"), indent=2)
print(f"ERRORS: {len(errors)}")
for x in errors: print(" ", x)
print(f"WARNINGS: {len(warnings)}")
for x in warnings: print(" ", x)
print("weekly miles:", dict(report["week_run_miles"]))
print("weekly minutes:", json.dumps(report["week_minutes_by_bundle"], indent=1))
sys.exit(1 if errors else 0)
