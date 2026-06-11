# Dashboard Metrics Refactor — Findings & Run Plan

**Status:** ready-to-run analyst backlog · **Created:** 2026-06-11 · **Owner:** dashboard copilot effort

This document consolidates what the `finding-analyst` runs have already established, reconciles
it against the refactor goal, and lists the analyst questions that must be answered **before**
the dashboard is refactored. It is the execution companion to `docs/analyst-data-discovery.md`
(the phased agenda) and `docs/analytical-dashboard-ideas.md` (the layout idea backlog).

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

## Run plan — questions to answer before refactoring

Priority order. The Phase 2 + Phase 3 block is the **minimum bar**: without it, the refactor only
swaps arbitrary weights for different arbitrary weights.

### P0 — Fixes the "meaningless numbers" problem directly

- **R1 · Q2.2 — How are metrics weighted within the recovery axis?**
  The literal replacement for the `25/25/25/25` in `dashboard.py`. Compare equal-weight vs
  correlation-deflated (metrics are highly redundant, so naive equal weighting double-counts the
  autonomic signal) vs information-weighted.
  → *Produces: the score weights + a justification that it does not double-count.*

- **R2 · Q3.3 — What is a meaningful change vs noise, per score?**
  The head-on answer to "−14.4 is meaningless." Establish the smallest worthwhile difference so the
  copilot can say "dropped meaningfully" instead of reporting a raw delta.
  → *Produces: the delta-flagging threshold + default comparison period.*

- **R3 · Q2.1 — Absolute scale or personal baseline, and over what window?**
  Whether the score is z-scored against the user's own rolling 60/90-day history — this is what
  makes "improving vs my own baseline" definable at all, and is the backbone of "see if it improves
  or decreases."
  → *Produces: the normalization rule + baseline window.*

### P1 — Needed for a trustworthy score

- **R4 · Q1.2 — Is the axis (correlation structure) stable across regimes/seasons?**
  We've shown *values* shift (Nov vs Feb); we have **not** shown whether the *loadings* hold — i.e.
  whether one fixed scoring model is valid year-round or needs regime-awareness. Gates whether a
  single static weight set is even legitimate. **Genuine open gap.**
  → *Produces: whether scoring can be static or must be regime-aware.*

- **R5 · Q2.3 / Q2.4 — Transform and smoothing spec per score.**
  Partly informed (median/IQR metric list exists; the HRV chart truncated-left-edge MA bug is
  documented) but no score-level decision exists.
  → *Produces: per-score center/shape handling + smoothing window + lead-in/seed behavior.*

- **R6 · Q3.1 / Q3.2 — Temporal structure + construct validity.**
  Does the score carry real autocorrelation (trend-worthy vs glance-only), and does it respond
  correctly to the known events (Nov regime, Feb peak, 2026-02-26 acute dip)? State explicitly
  whether validation is out-of-sample, leave-event-out, or in-sample.
  → *Produces: confidence the score reflects reality, not an artifact.*

### P2 — Shapes the refactor, not blocking the score itself

- **R7 · Is sleep a second score or part of the one axis?**
  Resolve the tension between the "3–5 cards" idea and the one-axis finding. Includes the
  unresolved REM-score status (r≈0.48 with sleep_score — redundant or independent?).
  → *Produces: the actual count of defensible scores/cards.*

- **R8 · Q4.3 — Per-axis drill-down tab spec.**
  Since the goal is to remove the four individual metric tabs, decide what replaces them: which
  sub-metrics live inside the recovery card's drill-down, what window, what comparison.
  → *Produces: each tab's spec.*

### Out of scope until activity ingest exists

- Any "exercise/training response" or "progress/load" score (Q5.2). Blocked on
  `docs/ACTIVITY_ANALYTICS_DESIGN.md` (no training-load/activity/session data in the mart).

## Execution notes

- Each R-item runs through the `finding-analyst` skill as an independent investigation; confirmed
  results land in `FINDINGS.md` with snapshot date, date range, sample size, and caveats.
- Start with the P0 trio (R1 → R2 → R3): together they produce the score contract that every later
  run validates.
- No dashboard scoring change ships ahead of the finding that justifies it. The `data-analysis`,
  `analytical-dashboard`, and `ux-design` skills consume these outputs to build scores, charts,
  and tabs.
- Every score definition must emit a **score contract** (per `analyst-data-discovery.md` Phase 2):
  metric inputs with source-type labels, normalization + baseline window, missing-data rule,
  weighting rule, smoothing rule, meaningful-change threshold, and UI-safe label/tooltip.
