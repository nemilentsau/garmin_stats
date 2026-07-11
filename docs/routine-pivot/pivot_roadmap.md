# Routine Pivot — Roadmap

**Status:** Active. This file answers two questions: *where are we* and *what happens next.* History lives in the changelog at the bottom, not inline.
**Governed by:** `general_principles.md` (P1–P13), `schema_v3_spec.md`, and the `block0/` artifacts — those are canonical; this roadmap bends to them, never the reverse.

---

## Where things stand (2026-07-09)

- **Block 0 is live in the app** (window 2026-07-06 → 2026-08-02, currently week 1 burn-in; baselines compute from day 8 = 07-13). The six canonical artifacts were uploaded through `Training → Import`, linted 0/0, stored verbatim, and execute on the Today board.
- **Capture is flowing**: per-set strength logs, tissue check-in (soreness 0–3 + flags), run RPE, and `variant_taken` branch logging. Selection rules display in English; the human selects (accepted for this block).
- **Card surface redesigned (2026-07-11)**: the training API now emits structured prescription fields (`reps_low/high`, `load_kind/value`, segment `distance/duration/zone`) + a last-logged load anchor instead of pre-flattened strings ("prescription seam", merged to `main`), and the Today execution card is a read-primary whole-session table — collapsible per-exercise logging, a plain variant badge, "next-move" faces, structured run segments (frontend on branch `feat/workout-card-redesign`, unpushed). This is UI/capture polish adjacent to — not a substitute for — the estimator work below.
- **Import is the only ingress** — enforced in code and CLAUDE.md. Everything v2 was deleted from the DB; meditation/breath bundle files remain in `docs/routine_bundles/` for re-import whenever wanted.
- **Activity FIT files download** from Garmin Connect on every sync into `data/garmin_activities/` — but nothing parses them yet.
- **The app computes no training signals yet.** It collects; it does not yet estimate. That is the next step.

## Next steps — in this order

1. **Parse the workout files** (running + strength, session grain first). Specs already written: `docs/future/RUNNING_ACTIVITY_SCHEMA.md`, `docs/future/STRENGTH_ACTIVITY_SCHEMA.md`. Turns every downloaded FIT into per-session data: pace, HR, time-in-zone, strap validity. Idempotent ingest wired into sync/startup like wellness archives.
2. **Compute the signals and estimators** — `block0/registry.json` implemented verbatim: HRV/RHR/sleep baselines with SWC bands (from the 400 days of wellness already in the DB), e1RM per lift + tonnage + planned-vs-executed (from the set logs capturing since day 1), easy-pace HR with first heat-correction fit, zone minutes, `load.day.total`. Nightly batch after sync; estimators backfill from stored capture — nothing is lost by building this in week 2. **Deliverable that matters: the weekly review (interference check, HSR tolerance, tonnage ratio) computes itself.**
3. **Dashboard reframe** — the training-state lane (S1–S5 trends) plus the constraint strip becomes the primary surface; recovery demotes to guardrails; metric tabs become drill-downs (the §2 demotions). Deliberately AFTER step 2: the lanes render the signals step 2 creates.
4. **Selection runtime + event log** — the app evaluates the morning rules itself (check-in + signals → full/reduced/skip, branch logged). **Deadline-bound: Block 1 needs the full engine when Block 0 exits (~2026-08-02).** Block 1 ships as v3 bundles into the same import pipeline.
5. **Calmness track (Phase 3)** — after Block 1 adopts the engine: the morning-after 1–5 report becomes a real capture field with an analysis contract (calmness trend conditioned on training load), promoted to a first-class experiment outcome; only then is meditation/breath content redesigned.

Detailed execution plans are working artifacts (gitignored scratch), deleted when the work ships — this list is the plan of record, and each step lands here as a changelog entry when done.

---

## Two standing objectives

**O1 — Training progression.** Maximize weighted dS/dt over the state vector (S1 threshold pace at LTHR, S2 squat-pattern e1RM, S3 calf/soleus HSR e1RM, S4 upper physique proxy, S5 hip-hinge e1RM — weights and bands per `block0/registry.json`), subject to recovery constraints — HRV band, RHR band, tissue flags, sleep. Recovery metrics are constraints, never the objective (P1). Green constraint dashboards with flat S remain a failure state.

**O2 — Mind calmness.** Reduce rumination and adversarial internal dialogue. Primary outcome is subjective: a morning-after self-report (one 1–5 scale rating yesterday's mind) on the same morning check-in surface as soreness. Physiology (daytime stress, nightly HRV, RHR) is corroborating evidence only and must be conditioned on training load — an unconditioned calmness metric would report "meditation stopped working" every hard block.

**Why the machinery differs.** Training dose-response is well characterized → O1 runs on continuous state estimation (estimators, signals, selection rules). Calmness interventions are genuinely uncertain → O2 runs on the A/B experiments engine, with the morning-after report as a first-class outcome metric.

## The surface-survival rule (P7, generalized)

Every surface, score, card, and metric names (a) the objective it serves and (b) the decision its output informs. Anything that cannot answer both is demoted or deleted.

| Surface | Verdict |
|---|---|
| Recovery score | Demoted to the O1 constraint strip (band status + which constraint fired). Not the home page. |
| Per-metric tabs (HR, HRV, sleep, …) | Drill-downs entered from a fired constraint or flag, not primary navigation. |
| SpO2 / skin temp / respiration tabs | Health flags only; standalone surfaces demoted. |
| Card ratings no model reads | Deleted. |
| Experiments engine | Retained and promoted: O2's measurement layer. |
| Training domain (v3) | The execution layer for O1; import-only ingress. |
| v2 routines engine | Legacy import path for meditation/breath bundles until Phase 3; then retired wholesale. |

## Standing rules (binding on all future work)

- **Import is the only ingress.** Routine/experiment/training content enters exclusively by importing an authored bundle. No generators, translators, seeders, or derived artifacts — ever. (Origin: the 2026-07-08 retraction; see changelog.)
- **The app adapts to the v3 schema, never the reverse.** Artifacts are stored verbatim; where the markdown spec and shipped artifacts disagree, artifacts win.
- **Capture cannot be backfilled; analysis can.** Capture ships before analysis whenever a block clock is running.
- **Morning-after calmness report** (banked for step 5): one 1–5 scale rating yesterday's internal dialogue, on the morning check-in — chosen over evening reports and episode logging.
- **Baselines carry condition tags** (`heat-season`, `chronic-load`, `protocol-change`); missing check-in data sends rules conservative, and "missing" means *no card log for the date* — an untouched tissue on a saved check-in is an attested 0.

## Non-goals

- No v2 salvage beyond the salvage list in `general_principles.md` §3.4.
- No calmness-side routine redesign before its sensor exists (P6: unsensed values get traded away silently).
- No new metric surfaces "while we're at it": every addition goes through the survival rule above.

---

## Changelog

- **2026-07-05 — adopted.** Two-objective reframe, survival rule, sequencing decisions (training first; Block 0 before the engine; audit in lieu of runtime linter for Block 0; calmness report banked).
- **2026-07-07 — revised to the artifacts.** `block0/` extracted from the authoring session: three v3 bundles, block definition, `registry.json` (5-component state vector incl. S5 hip-hinge), exercise library, reference linter with 0/0 report (reproduced byte-identically). Block 0 window pinned 2026-07-06 → 2026-08-02.
- **2026-07-08 — Phase 0 shipped and RETRACTED same day.** A v3→v2 translation pipeline ran Block 0 on the old engine for one day; rejected as a second ingress and a schema shoehorn. Translator, derived bundle, and retire script deleted; DB wiped of all routine/experiment/artifact content. The import-only and app-adapts-to-schema rules date from here. Kept from that day's work: typed tissue check-in, `variant_taken` branch logging, rule display — v3-semantics adaptations, not shoehorns.
- **2026-07-09 — v3-native import shipped** (next-steps list item 0, formerly "Phase 1 first deliverable"). New standalone `training` domain: upload → strict contract validation → ported L1–L12 linter (parity 0/0) → verbatim storage → single-shot activation; Today/schedule/block read models with backend-side display projections; native capture with occurrence-validated ingest. Block 0 re-activated through the real UI. Open minor follow-up: typed 404 discrimination for block status on the import page.
- **2026-07-11 — docs restructure, prescription seam, card redesign.** (1) Docs restructured — single-home data topology (`docs/reference/data-and-ingest.md`), colocated per-domain `CHARTER.md`, generated route inventory, thinned `ARCHITECTURE.md`, question-router `docs/README.md` (merged; fixed the blind spot where the activity-download pipeline was undiscoverable). (2) Backend "prescription seam": the training API emits structured prescription fields + a `last`-logged load anchor instead of pre-flattened strings, via a new `card_logs_before` read (merged; 829 tests green). (3) Today execution card rebuilt read-primary — whole-session table, collapse-to-log, human variant badge, next-move faces, structured run segments (branch `feat/workout-card-redesign`, unpushed). Deferred: two-card-system de-dup (waits for a v2 import to verify against). Next: run→activity parse (= next-steps #1) then the PPL×2 strength block.
- *(retirement)* This doc retires when Block 1 adopts the full engine (next-steps items 1–4 done): from then on the principles and schema specs govern and this file is history.
