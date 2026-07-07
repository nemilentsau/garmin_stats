# Routine Pivot — App Reframe and Implementation Roadmap

**Status:** Adopted (brainstorm session 2026-07-05); **revised 2026-07-07** to align with the authored Block 0 artifacts
**Date:** 2026-07-05 (rev. 2026-07-07)
**Governed by:** `general_principles.md` (P1–P13); `schema_v3_spec.md`; **`block0/` artifacts (bundles, registry, block definition)**
**Scope:** Extends the v3 training-system pivot to the whole app. Names the two standing objectives, the survival rule for existing surfaces, and the build sequence through Block 1 adoption.

**Source-of-truth rule:** the two governing markdowns and the `block0/` artifacts are canonical. This roadmap is subordinate — when it conflicts with them, the roadmap is amended (as in this revision), never the reverse. App code and surfaces bend to the artifacts; deleting app pieces that conflict is expected, not exceptional.

**Rev. 2026-07-07 deltas** (after extracting `block0/` — authored in the same external session as the governing docs, previously opaque inside a zip):
- Block 0 bundles already exist **in v3 wire format** (`running.v3`, `strength.v3`, `support.v3`), plus `block0.json`, `registry.json` (signals, estimators, 5-component state vector, objective), `exercise_library.json`, a draft `linter.py`, and its outputs. Phase 0 no longer authors anything — it **derives** app-side execution from these sources.
- Block 0's window is pinned by `block0.json`: **2026-07-06 → 2026-08-02**. The 2026-07-13 plan-of-record start is superseded. Week 1 is burn-in (baselines compute from day 8), which absorbs app-side catch-up in the first days.
- The §11 audit (D3) is partially discharged: `linter.py` was reviewed (implements L1–L12; soft spots noted below) and its run reproduced byte-identically (0 errors, 0 warnings). Independent spot-checks remain, since the linter shares authorship with the bundles it passed.
- The state vector has five components (S5 = hip-hinge e1RM) and S1's signal is currently `pacehr.easy_hr_at_ref_pace` (proxy until the LTHR test anchors true threshold pace) — Phase 1 follows `registry.json`, not the four-component sketch in the schema spec.

---

## 1. Two standing objectives

The app stops being a recovery observatory. Every feature exists to serve one of two objectives:

**O1 — Training progression.** As specced: maximize weighted dS/dt over the state vector (S1 threshold pace at LTHR, S2 squat-pattern e1RM, S3 calf/soleus HSR e1RM, S4 upper physique proxy, S5 hip-hinge e1RM — weights and bands per `block0/registry.json`), subject to recovery constraints — HRV band, RHR band, tissue flags, sleep. Recovery metrics are constraints, never the objective (P1). Green constraint dashboards with flat S remain a failure state.

**O2 — Mind calmness.** Reduce rumination and adversarial internal dialogue. The primary outcome is subjective: a morning-after self-report (one 1–5 scale rating yesterday's mind), captured on the same morning check-in surface as soreness and tissue flags. Physiology (daytime stress, nightly HRV, RHR) is corroborating evidence only, and any physiological readout used for O2 must be conditioned on training load — a hard development block depresses HRV with zero change in mind state, and an unconditioned calmness metric would report "meditation stopped working" every Block 1.

**Why the machinery differs.** Training dose-response is well characterized, so O1 runs on continuous state estimation (estimators, signals, selection rules). Calmness interventions are genuinely uncertain — which practice, what dose — so O2 runs on the A/B experiments engine, with the morning-after report promoted to a first-class outcome metric. Same measurement discipline, different instruments.

---

## 2. The surface-survival rule (P7, generalized)

P7 governs capture fields; the same closure test now governs the app. Every surface, score, card, and metric names (a) the objective it serves and (b) the decision its output informs. Anything that cannot answer both is demoted or deleted.

Applied to what exists today:

| Surface | Verdict |
|---|---|
| Recovery score | Demoted to the O1 constraint strip: band status plus which constraint fired. Not the home page. |
| Per-metric tabs (HR, HRV, sleep, stress, …) | Drill-downs entered from a fired constraint or flag, not primary navigation. |
| SpO2 / skin temp / respiration tabs | Health flags only; standalone surfaces demoted. |
| Card ratings no model reads | Deleted (already done for the breath card; same test applies everywhere). |
| Experiments engine | Retained and promoted: O2's measurement layer. |
| Routines/cards engine | Retained: execution layer for both objectives; migrates to v3 schema per the phases below. |

---

## 3. Sequencing decisions

**D1 — Training track first, calmness second.** O1 is fully specced and its v2 predecessor is already terminated — the interregnum is running now. O2 needs design work, and current meditation practice continues as-is without harm. No dependency runs from O2 to O1.

**D2 — Block 0 before the v3 engine.** The razor: capture cannot be backfilled; analysis can. The only thing that must exist on day 1 is capture, and it largely does — strength set×rep×load logging, post-run fields including dew point, chest-strap HR. Block 0 is deliberately the least adaptive block the system will ever run (flat volume, stationary weekly covariates), so it needs the least runtime machinery of any block. The selection-rule engine earns its keep in Block 1, not Block 0.

**D3 — One-off audit replaces the runtime linter, for Block 0 only.** The three Block 0 bundles are audited against `schema_v3_spec.md` §11, all twelve checks, before adoption. Named risk: reviewer discipline is the exact failure mode that produced v2's stacked hedges (§1.2 of the principles doc). Mitigations: the audit is the twelve checks applied mechanically, not judgment; a bundle that needs an exception fails and is re-authored — there are no waivers; and the real linter still gates Block 1. *(Rev. 2026-07-07: a draft `linter.py` shipped with the bundles and its 0/0 report reproduces byte-identically; because it shares authorship with the bundles, the audit's remaining job is spot-checking its three soft rules — see Phase 0 step 3.)*

**D4 — Morning-after calmness report (banked for Phase 3).** Cadence and construct are fixed now so Phase 3 starts from a decision, not a debate: one 1–5 scale rating yesterday's internal dialogue, answered each morning alongside the soreness check-in. Chosen over an evening report (end-of-day fatigue colors the answer; one habit surface beats two) and over episode logging (in-the-moment capture during rumination is precisely the moment it won't happen).

---

## 4. Phases

### Phase 0 — Block 0 on the current engine (revised: translate, don't author; already in-window)

Block 0 is live per `block0.json` (started 2026-07-06). Phase 0 is now the fastest honest path to the cards appearing on the Today board and capture flowing:

1. **Translate v3 → current-engine import bundles.** Mechanically derive schema-v2 bundles (card templates + dated assignments from the compiled 28-day schedule, day 1 = 2026-07-06) from the three v3 sources. The v3 files stay canonical; the derived v2 bundles are build artifacts — regenerate on any source change, never hand-edit. Prescriptions map to existing card types (running_workout, strength_session, checklist for the morning check-in). Selection rules cannot execute on the v2 engine: for Block 0 they run as human discipline off `schedule_overview.md`'s plain-English rendering, with branches recorded in log notes (accepted in D2 — this block is the least adaptive the system will run).
2. **Morning check-in capture**: the support bundle's daily check-in card specifies the capture (soreness 0–3 across six tissues, boolean tissue flags, core_done). The checklist card is the closest existing surface (checkbox+text) — a disciplined convention now, a typed extension only if week-1 use shows the convention corrupts the data.
3. **Finish the audit per D3 (revised).** Done: `linter.py` reviewed; lint run reproduced byte-identically (0 errors / 0 warnings; weekly miles 49.0/49.5/49.0/32.8; budgets within declarations). Remaining: independent spot-checks of rules where the linter is soft — L11 novelty is hardcoded (`novel = 3`) rather than computed; L9's no-unramped-novel-overload check only covers `tendon_stiffness`; L7's coverage test passes on any ambient (non-capture) estimator input. Spot-check those three by hand against the compiled schedule before trusting the report fully.
4. **Adopt in-place.** No interregnum: the window is running, week 1 is burn-in, baselines compute from day 8 (2026-07-13). App-side execution should be live well before day 8 so the baseline window starts with full capture.

### Phase 1 — v3 engine build (during Block 0's four weeks)

Schema types, validator, signal registry, estimators, morning selection runtime, event log — now with concrete starting points from `block0/`: the validator ports `linter.py` (review-hardening the three soft spots above) instead of starting from scratch; the signal registry, estimator DAG (15 estimators, `est.*` IDs), state vector (S1–S5), and objective/constraint bands implement `registry.json` verbatim. Estimators built mid-block backfill from day-1 capture — that is what D2 buys; the activity FIT download pipeline (PR #64) supplies the raw running/strength data the `est.pacehr`, `est.day_rollup`, and e1RM estimators consume. Open technical decisions stay where they are (`schema_v3_spec.md` §13). Exit criterion: Block 1 bundles compile, lint with zero errors, and execute on the engine. **Block 1 adopts the engine.**

### Phase 2 — Dashboard reframe (overlaps Phase 1; no Block 0 dependency)

The training-state lane — S1–S4 trends plus the constraint strip — becomes the primary surface; the §2 demotions are applied. Design goes through the usual dashboard/UX skills; this doc fixes only the information hierarchy: state first, constraints second, drill-downs on demand.

### Phase 3 — Calmness track (after Block 1 adopts the engine)

Wire the D4 report as a real capture field with an analysis contract — model: calmness trend conditioned on training load and prior-day session type; decision informed: which practice and dose to run next, via experiments. Promote it into the experiment target-metric registry as a first-class outcome. Only then redesign meditation/breath routine content. Until Phase 3, meditation runs unchanged.

---

## 5. Non-goals

- No v2 salvage beyond the salvage list in `general_principles.md` §3.4.
- No calmness-side routine redesign before the sensor exists — P6 applies to minds as much as tissues: unsensed values get traded away silently.
- No new metric surfaces "while we're at it": every addition goes through the §2 survival rule.

---

This doc retires when Phase 0 completes: after Block 0 is adopted, the principles and schema specs govern and this file is history.
