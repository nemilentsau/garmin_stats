# Routine Pivot — App Reframe and Implementation Roadmap

**Status:** Adopted (brainstorm session 2026-07-05)
**Date:** 2026-07-05
**Governed by:** `general_principles.md` (P1–P13); `schema_v3_spec.md`
**Scope:** Extends the v3 training-system pivot to the whole app. Names the two standing objectives, the survival rule for existing surfaces, and the build sequence from today through Block 1 adoption. The other two docs govern training content and schema; this one governs what the rest of the app becomes, and in what order.

---

## 1. Two standing objectives

The app stops being a recovery observatory. Every feature exists to serve one of two objectives:

**O1 — Training progression.** As specced: maximize weighted dS/dt over the state vector (S1 threshold pace at LTHR, S2 squat-pattern e1RM, S3 calf/soleus HSR e1RM, S4 upper physique proxy), subject to recovery constraints — HRV band, RHR band, tissue flags, sleep. Recovery metrics are constraints, never the objective (P1). Green constraint dashboards with flat S remain a failure state.

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

**D3 — One-off audit replaces the runtime linter, for Block 0 only.** The three Block 0 bundles are audited against `schema_v3_spec.md` §11, all twelve checks, before adoption. Named risk: reviewer discipline is the exact failure mode that produced v2's stacked hedges (§1.2 of the principles doc). Mitigations: the audit is the twelve checks applied mechanically, not judgment; a bundle that needs an exception fails and is re-authored — there are no waivers; and the real linter still gates Block 1.

**D4 — Morning-after calmness report (banked for Phase 3).** Cadence and construct are fixed now so Phase 3 starts from a decision, not a debate: one 1–5 scale rating yesterday's internal dialogue, answered each morning alongside the soreness check-in. Chosen over an evening report (end-of-day fatigue colors the answer; one habit surface beats two) and over episode logging (in-the-moment capture during rumination is precisely the moment it won't happen).

---

## 4. Phases

### Phase 0 — Block 0 on the current engine (now → first Monday after audit passes)

1. **Verify the capture-gap list** against the current engine. Expected gap: the morning check-in needs 0–3 soreness enums per owned tissue plus boolean pain flags; the checklist card is the closest surface but its items are checkbox+text today — small extension or disciplined convention, to be confirmed. Everything else runs on scheduling and notes discipline for four weeks: the LTHR test as a scheduled card with a backup day, branch deviations recorded in log notes.
2. **Author the three Block 0 bundles** (running / strength / support) per `general_principles.md` §3.2–3.4, under v3 discipline even though the wire format is v2: contracts stated on every card, single tissue ownership, required LTHR test day 12 with backup day 15, tendon HSR heavy from day 1, plyometrics held at primer tier, set×rep×load logged from day 1, baseline tags `heat-season` / `chronic-load` / `protocol-change`.
3. **Audit per D3.** Fix or re-author until all twelve checks pass.
4. **Adopt.** Plan of record: Block 0 starts Monday **2026-07-13**. (2026-07-06 only if authoring and audit complete today — not assumed.) Interregnum rules apply until the start date.

### Phase 1 — v3 engine build (during Block 0's four weeks)

Schema types, validator, signal registry, estimators (`e1rm.*`, `tonnage.*`, `pacehr.easy_hr_at_ref_pace` with heat correction, `load.day.total`), morning selection runtime, event log. Estimators built mid-block backfill from day-1 capture — that is what D2 buys. Open technical decisions stay where they are (`schema_v3_spec.md` §13). Exit criterion: Block 1 bundles compile, lint with zero errors, and execute on the engine. **Block 1 adopts the engine.**

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
