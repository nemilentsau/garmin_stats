# Dashboard Metrics Refactor — Findings & Run Plan

**Status:** analyst backlog **complete (P0–P2 done, 2026-06-11)** — score contract validated,
flags defined, drill-down specced; ready for the dashboard build · **Created:** 2026-06-11 ·
**Owner:** dashboard copilot effort

This document consolidates what the `finding-analyst` runs have established, reconciles it
against the refactor goal, and tracked the analyst questions answered **before** the dashboard
refactor. All blocking runs (R1–R9) are done; the **R6 construct-validity gate passed**, so the
build may proceed on the validated score contract below. It is the execution companion to
`docs/analyst-data-discovery.md` (the phased agenda), `docs/analytical-dashboard-ideas.md` (the
layout idea backlog), and `docs/dashboard-drilldown-spec.md` (the R8 drill-down spec).

**Done:** R1 (weights), R2 (meaningful change), R3 (normalization), R4 (axis stability),
R5 (smoothing), R6 (construct-validity gate — passed), R7 (one card, sleep is an input),
R8 (drill-down spec), R9 (two flags), R10 (experiment response — verdict: blocked on data,
must not surface). **Remaining:** the open state-banner scope decision (needs agenda Q4.1) —
the only non-build item left. The analyst program is otherwise complete; next is the build.

## The refactor goal (as stated)

Remove the four Garmin metrics that drive the dashboard overview (resting HR, nightly HRV, sleep
score, stress) and the four hardcoded `0–25` readiness components in
`backend/app/domains/garmin_analytics/domain/dashboard.py`, and replace them with a small set of
**scores that meaningfully reflect physiological response to experiments and exercise** — scores
that can trend up or down over time and where a change is interpretable, not an arbitrary
`−14.4`.

## Two reality checks the data forces on that goal

1. **"Response to exercise" cannot be built from current data.** Every finding repeats that this
   is *a strong recovery dataset, not a training-performance dataset*. There is no training load,
   no activity/session data, no steps, and no sleep duration in the daily mart. A score meaning
   "how my body responded to that workout" is blocked on the activity-ingest work in
   `docs/ACTIVITY_ANALYTICS_DESIGN.md`, not on an analyst question. Response to **experiments**
   (e.g. the meditation routine) is *partially* possible — experiment exposures already exist as
   `experiment_id + date` records — but only against recovery outcomes, and only once a validated
   recovery score exists to measure against.

2. **The data discovered ONE axis, not "a handful."** Stress, HR-avg, resting-HR, and respiration
   sit on one pole; HRV, body battery, and sleep score on the other (pairwise |r| 0.5–0.84). In
   this dataset **high stress *is* low recovery** — one autonomic state measured several ways.
   Three metrics sit off the axis (deep-sleep score, SpO2, skin-temp), two of which already proved
   to carry no usable trend signal. The honest output is roughly **one recovery/autonomic score +
   two health *flags* (oxygen, thermoregulation) that are not daily gauges**, possibly a soft
   second score for sleep. The "3–5 axis cards" in the idea backlog is **not yet evidence-backed**;
   resolving that tension is itself a question below.

**Recommended reframe:** target *one validated recovery score with a meaningful-change threshold,
plus two health flags*, rather than "a handful of exercise-response scores." That is what the data
supports today and is a far more honest dashboard than the current scaffold.

## What is already settled (do NOT re-run)

| Agenda question | Status | Result | Run |
|---|---|---|---|
| Q1.1 — how many axes? | confident | One recovery↔stress axis (6 metrics) | `2026-05-26-multi-baseline-recharacterization` |
| Q1.3 — SpO2 redundant? | confident | Rejected as recovery signal; keep as low-O₂ flag only | `2026-05-26-spo2-incremental-value` |
| Q1.3 — deep-sleep signal? | confident | Low-information, no persistence — exclude from trends | `2026-05-27-sleep-deep-signal-or-noise` |
| Q1.3 — HRV bimodal? | confident | No — continuous, regime-modulated; do not threshold it | `2026-05-27-hrv-bimodality` |
| Open Q — Nov regime extent | confident | ~5 weeks, not 2; stress leads, cardiovascular tone recovers last | `2026-05-26-recovery-nov-regime-extent` |
| Q4.2 (partial) — lead/lag | bounded | stress→next-night-HRV is real but does **not** generalize beyond the one severe episode | `2026-05-26-stress-hrv-lag`, `2026-05-27-recovery-leadlag-generalize` |
| Distribution / coverage baseline | confident | Median/IQR for stress, SpO2-avg, sleep sub-scores; full autonomic coverage; SpO2 19% missing in two structural blocks | `2026-05-26-multi-baseline-recharacterization` |
| R4 · Q1.2 — loadings stable? | confident | Yes — PC1 congruence ≥ 0.993 across regimes/quarters, no sign flips; static weights legitimate (severe-regime attenuation noted, provisional) | `2026-06-11-multi-axis-loading-stability` |
| R3 · Q2.1 — normalization | confident (invalidation) / provisional (selection) | 30–60 d trailing baselines absorb regimes — invalid. Expanding robust-z selected provisionally (registered acute criterion failed all candidates incl. hindsight reference; demoted post-hoc, disclosed). Missing-data rule: ≥30-day warm-up, ≥5/7 inputs, degrade <7 | `2026-06-11-recovery-normalization-baseline` |
| R1 · Q2.2 — score weights | confident | Weighting practically immaterial (r ≥ 0.9996 between candidates); correlation-deflated adopted ≈ equal; weights recorded in FINDINGS + run | `2026-06-11-recovery-score-weighting` |
| R2 · Q3.3 — meaningful change | confident (in-sample) | Default = 7d vs prior 7d, badge at \|Δ7\| ≥ 0.97 z; acute \|Δ1\| ≥ 1.86 z; ~3 badges/month; single-night dips don't badge by design | `2026-06-11-recovery-score-meaningful-change` |
| R5 · Q2.3/Q2.4 — smoothing | confident | No transform (symmetric); trailing 7-day MA, seeded W−1=6 per `_MA_SEED_DAYS`; one window across smoothing/comparison/chart | `2026-06-11-recovery-score-smoothing-spec` |
| R6 · Q3.1/Q3.2 — construct validity | confident | **GATE PASSED** — T1 autocorrelation, T2 leave-event-out, T3 clean Apr+ holdout all pass; score validated for shipping (events n-of-1) | `2026-06-11-recovery-score-validation` |
| R7 — sleep: 2nd score? | confident | No — one axis, sleep is an input (R² 0.47, independent part is noise); REM = drill-down detail; one card + two flags | `2026-06-11-sleep-second-score-or-axis` |
| R9 — flag definitions | confident | O₂: spo2_avg < ~90.5% (personal); missing = "unknown"; thermo: skin-temp outside ±~0.9°C; resolved Apr-21→27 episode | `2026-06-11-spo2-skintemp-flag-thresholds` |
| R8 — drill-down tab spec | done (design) | One recovery drill-down + evidence stack replaces the 4 metric tabs; flags + sleep sub-section specced | `docs/dashboard-drilldown-spec.md` |
| R10 — experiment response | confident (data-gap) | Blocked on data — only 5 exposure days in 1 block; not claimable; HRV-shared-input tautology; dashboard must not surface it | `2026-06-11-experiment-response-detectability` |

## Run plan — questions to answer before refactoring

Priority order. The Phase 2 + Phase 3 block is the **minimum bar**: without it, the refactor only
swaps arbitrary weights for different arbitrary weights.

### P0 — Fixes the "meaningless numbers" problem directly

Run in dependency order: **R3 + R4 in parallel, then R1, then R2.** Weighting schemes (R1) can
only be compared once the inputs share a normalization scale (R3) and the static-vs-regime
question (R4) is settled; the meaningful-change threshold (R2) is a property of the composed
score's time series, so it needs both.

- **R3 · Q2.1 — Absolute scale or personal baseline, and over what window?** ✅ **Done with
  amendment** (`2026-06-11-recovery-normalization-baseline`): personal baseline, **expanding
  history-to-date robust z** (median/MAD, current day excluded; revisit a ~365-day cap when
  year 2 accrues). 30/60-day trailing windows are *invalid* — they absorb the Nov regime by
  weeks 3–5 and overshoot after it ends (confident); 90-day misses the registered bar by one
  day. Selection is *provisional*: the registered acute criterion failed every candidate
  including the hindsight reference and was demoted post-hoc (disclosed in the run; R6 must
  validate). Missing-data rule (provisional): ≥30 prior present days per metric (warm-up
  renders no score), composite needs ≥5/7 inputs, degraded-confidence flag <7, suppress <5.
  Handed to R2 (tentative): single-night events rank top 5–11% of composite day-deltas, never
  top 5% — consider separate acute vs sustained thresholds.
  → *Produced: normalization rule + baseline window + missing-data rule.*

- **R4 · Q1.2 — Is the axis (correlation structure) stable across regimes/seasons?** ✅ **Done**
  (`2026-06-11-multi-axis-loading-stability`, confident): loadings are stable — PC1 congruence
  0.993–0.999 across regime-defined and quarterly windows, no sign flips; **static weights are
  legitimate**. Caveat for R1: two couplings (resp↔BB, HRV↔sleep) attenuate during the
  Sep–Nov crash quarter (provisional), so full-period correlation-deflated weights slightly
  overstate redundancy during severe regimes — record that with the weight contract.
  → *Produced: static scoring is legitimate; no regime-awareness needed.*

- **R1 · Q2.2 — How are metrics weighted within the recovery axis?** ✅ **Done**
  (`2026-06-11-recovery-score-weighting`, confident): equal, correlation-deflated, and PC1
  weightings are practically identical (r ≥ 0.9996, p90 |Δ| ≤ 0.04 z) — redundancy across the
  axis is uniform, so deflation lands ≈ equal. **Adopted: correlation-deflated weights**
  (recovery-signed, per-day renormalized over ≥5/7 inputs): RHR .142, HRavg .148, stress .139,
  resp .137, BB .135, HRV .140, sleep .159. Double-count defense documented (no metric > 0.16,
  no pole > 57%, composite ≥ 0.93 vs each pole sub-composite). LOMO regime fidelity ≥ 73%.
  → *Produced: the score weights + double-count justification.*

- **R2 · Q3.3 — What is a meaningful change vs noise, per score?** ✅ **Done**
  (`2026-06-11-recovery-score-meaningful-change`, confident, in-sample): **default comparison
  = 7-day mean vs prior 7-day mean, meaningful at |Δ7| ≥ 0.97 z; secondary acute flag at
  |Δ1| ≥ 1.86 z.** Stable-window false positives 5.7%/0.0%; Nov-regime onset flagged day 8;
  badge frequency ≈3/month. The 2026-02-26 single-night dip deliberately does not badge —
  single-night visibility belongs to drill-down raw views (R5/R8). Thresholds are z-unit
  values; display rescaling must scale them. R6 validates.
  → *Produced: the delta-flagging thresholds + default comparison period.*

### P1 — Needed for a trustworthy score

- **R5 · Q2.3 / Q2.4 — Transform and smoothing spec per score.** ✅ **Done**
  (`2026-06-11-recovery-score-smoothing-spec`, confident): no score-level transform (score is
  symmetric, skew −0.42); **trailing 7-day MA** (86% plateau-noise reduction, 0 added onset
  lag, 0% sustained-depth attenuation; MA3 too jagged, MA14 over-smooths); **seed the display
  edge with W−1=6 prior days** per the `dashboard.py` `_MA_SEED_DAYS` precedent (skipping errs
  up to 0.12 z on the first 6 points). One window (7) spans smoothing, R2's comparison, and the
  existing chart. Trend-worthiness of the smoothed series is R6's call. Raw-values *display*
  remains R8.
  → *Produced: center/shape handling + smoothing window + seed behavior (the contract's last
  computational field).*

- **R6 · Q3.1 / Q3.2 — Temporal structure + construct validity.** ✅ **Done — GATE PASSED**
  (`2026-06-11-recovery-score-validation`, confident): the score is **validated for shipping**.
  T1 (in-sample-structural): real autocorrelation (lag-1 0.457, exceeds block-permutation null
  p<1e-4). T2 (leave-event-out, baselines frozen pre-event): MA7 below pre-Nov P10 for 36
  straight days, above pre-plateau P90 on 93% of Feb best-window days, acute dip absorbed by
  MA7 by design. T3 (clean Apr–Jun holdout, postdates all parameter-setting): autocorrelation
  holds (0.377 vs 0.412) and Δ7 flag rate a sane 8.3%. Registration corrected mid-run
  (disclosed): the original "held-out" half included the design-time plateau. Caveat: events
  are n-of-1. **This satisfies the plan's "no scoring change ships ahead of the finding" rule
  for the recovery score** — the dashboard build may now proceed.
  → *Produced: validated recovery score; the build gate is open.*

### P2 — Shapes the refactor, not blocking the score itself

- **R7 · Is sleep a second score or part of the one axis?** ✅ **Done**
  (`2026-06-11-sleep-second-score-or-axis`, confident): **one axis, sleep is an input — no
  second card.** Sleep_score is only borderline-independent of the autonomic axis (rank-R²
  0.469) and its independent part is noise (residual lag-1 AC +0.19, CI spans 0). REM is 79%
  independent of sleep_score but carries no recovery info (residual r −0.03) — drill-down
  detail at most. **Card count: one recovery score + two health flags (R9), no sleep card.**
  Side note (tentative, deferred): dropping sleep slightly *raises* regime fidelity
  (83.3%→86.1%) — a future refinement that would re-trigger R6, not changed now.
  → *Produced: one defensible score/card (+ two flags); sleep & REM are drill-down sub-metrics.*

- **R8 · Q4.3 — Per-axis drill-down tab spec.** ✅ **Done** → `docs/dashboard-drilldown-spec.md`.
  The four per-metric tabs are replaced by **one recovery drill-down with an evidence stack**
  (the seven inputs are one axis, not four tabs): L1 score + meaningful-change badge + two flag
  chips (incl. the mandatory "unknown" SpO₂ state); L2 evidence stack (value/baseline/z-delta/
  coverage/source-type per input, ordered by mover); L3 90-day raw+MA7 trend with event
  annotations, per-input small multiples, flag detail panels (structural-missing bands), and a
  collapsed sleep-architecture sub-section (sleep_score + REM, not a card). Default windows and
  per-metric number formatting specified; backend-contract additions listed (display-only
  frontend). Out of scope flagged: state banner (needs Q4.1), z→display scaling (UX), raw-values
  toggle (Open Q5), load axis, experiment surfacing (R10).
  → *Produced: the drill-down spec replacing the metric tabs.*

- **R9 · Flag definitions — oxygen and thermoregulation.** ✅ **Done**
  (`2026-06-11-spo2-skintemp-flag-thresholds`, confident): **Low-oxygen flag** = nightly
  `spo2_avg` < personal median−2.5·MAD ≈ **90.5%** (3.6% of covered nights; catches all 7 days
  of the real Apr-21→27 episode; ≈ conventional 90% line). spo2_avg beats spo2_min (coarse,
  2/7 hits) — spo2_min is supporting nadir detail; absolute cutoffs useless (min<88% fires
  98.7% of nights). **Missing SpO2 = third "unknown" state, never clear** (the 18% gaps are the
  two structural blocks only). **Thermoregulation flag** = two-sided skin-temp deviation outside
  median±2.5·MAD ≈ **[−0.91, +0.83]°C** (4.4%); independent of oxygen (didn't fire in Apr). Per-day
  flags + a trailing-7 "recent" chip (sticky for skin-temp → R8/UX tunes the window). Also
  resolved `FINDINGS.md` Open Question 2 (Apr-21→27 = real low-oxygen episode).
  → *Produced: both flag thresholds + missing-data behavior + clear rule.*

**Open scope decision — state banner.** The idea backlog's headline pattern is "state before
score" (a state label above the numeric score), which needs agenda Q4.1 (do days cluster into a
few recurring states?) answered first. Decide whether the banner is part of this refactor: if
yes, Q4.1 joins P2 as its own R-item; if no, the overview leads with the score and the banner
waits for a later phase. Don't let it ship unbacked either way.

### Queued behind R6 — experiment response (post-score follow-up)

- **R10 · Does the validated recovery score detect experiment-exposure effects?** ✅ **Done —
  BLOCKED ON DATA** (`2026-06-11-experiment-response-detectability`, confident data-gap verdict):
  **no — not claimable from current data.** The only experiment (`meditation-hrv-2026-03`) has
  just **5 logged exposure days in one consecutive block** (2026-05-23→05-27, 3 full + 2
  partial; 9 card logs) — the spec's 14-day March design is a draft placeholder. 5 consecutive
  days < one Δ7 window, no across-time exposure contrast, and the score shares its HRV input
  with the experiment's target (tautology). The dashboard must **not** surface an
  experiment-response number for this experiment. Descriptive caution: the recovery bump
  *predates* the block (reverse-causation trap). **A claimable attempt needs:** sustained logged
  exposures (≥~2 wk), ≥2 separated blocks or a baseline-vs-treatment contrast, and an
  HRV-excluded recovery proxy. The causal HRV question stays with the experiment's own
  `compute_experiment_analysis` pipeline.
  → *Produced: the honest verdict (blocked on data) + the requirements to unblock.*

### Out of scope until activity ingest exists

- Any "exercise/training response" or "progress/load" score (Q5.2). Blocked on
  `docs/ACTIVITY_ANALYTICS_DESIGN.md` (no training-load/activity/session data in the mart).

## Score contract — recovery score (VALIDATED, 2026-06-11)

Consolidated from R1–R6. R6 passed the construct-validity gate, so this contract is cleared
for the dashboard build. Only the UI-safe label/display-scaling field remains (UX pass, R8).

- **Inputs (recovery-signed, with source type):** resting HR − (device-computed from
  source-native HR), HR avg − (backend-derived from source-native readings), stress −
  (Garmin-derived), respiration − (source-native), body battery + (Garmin-derived),
  nightly HRV + (Garmin-derived), sleep score + (Garmin-derived). Stress/BB/HRV share HRV
  derivation — labeled per contract rule.
- **Normalization + baseline window:** per-metric robust z vs expanding personal history
  (median/MAD×1.4826, current day excluded, ≥30 prior present days). 30–60-day trailing
  windows are invalid (absorb regimes). Revisit ~365-day cap when year 2 accrues. *(R3;
  selection provisional, invalidation confident)*
- **Missing-data rule:** per-metric z suppressed without a valid baseline; composite computes
  with ≥5/7 inputs, carries a degraded-confidence flag when <7, suppressed below 5; 30-day
  warm-up renders no score. *(R3, provisional)*
- **Weighting rule:** correlation-deflated, ≈ equal by measurement (RHR .142, HRavg .148,
  stress .139, resp .137, BB .135, HRV .140, sleep .159), per-day renormalized over available
  inputs. Double-count defense: no metric > 0.16, no pole > 57%, composite ≥ 0.93 vs each
  pole sub-composite; weighting choice shown practically immaterial (r ≥ 0.9996). Static
  across regimes per R4. *(R1, confident)*
- **Smoothing rule:** trailing 7-day MA of the score (no extra transform — score is symmetric).
  Seed the display edge with W−1=6 prior days (compute MA over seed+display, drop the seed),
  per `dashboard.py` `_MA_SEED_DAYS`. One window (7) across smoothing, the R2 comparison, and
  the existing chart. *(R5, confident; trend-worthiness pending R6)*
- **Meaningful-change threshold + default comparison:** default = 7-day mean vs prior 7-day
  mean, meaningful at |Δ7| ≥ 0.97 z; secondary acute flag |Δ1| ≥ 1.86 z; ≈3 badges/month;
  thresholds scale with any display rescaling. *(R2, confident in-sample)*
- **UI-safe label/tooltip:** **open — R5/UX** (z-to-display scaling decision included).

## Execution notes

- Each R-item runs through the `finding-analyst` skill as an independent investigation; confirmed
  results land in `FINDINGS.md` with snapshot date, date range, sample size, and caveats.
- Pin a fresh snapshot at the start of P0: the trust record is pinned at `2026-05-26` and the mart
  has continued since. Settled findings do not need re-running for the extra days, but the score
  contract must be derived from the current snapshot.
- Start with the P0 block in dependency order (R3 + R4 in parallel → R1 → R2): together they
  produce the score contract that every later run validates.
- No dashboard scoring change ships ahead of the finding that justifies it. The `data-analysis`,
  `analytical-dashboard`, and `ux-design` skills consume these outputs to build scores, charts,
  and tabs.
- Every score definition must emit a **score contract** (per `analyst-data-discovery.md` Phase 2):
  metric inputs with source-type labels, normalization + baseline window, missing-data rule,
  weighting rule, smoothing rule, meaningful-change threshold, and UI-safe label/tooltip.
