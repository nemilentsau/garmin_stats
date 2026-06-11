# Analyst Data-Discovery Program

**Status:** active research agenda (rationale + method constraints) · **Created:** 2026-05-27 ·
**Last reconciled:** 2026-06-11 · **Owner:** dashboard copilot effort

This document defines the *rationale, operating principles, and method constraints* for the
questions we pose to the data analyst (the `finding-analyst` skill, executed run-by-run) to turn a
year of Garmin health data into a defensible **stress / recovery copilot**. It is a research
agenda, not an implementation plan: each phase produces durable evidence in `FINDINGS.md`, and that
evidence — not intuition — defines the dashboard's scores, axes, drill-down tabs, and language.

> **Where to look for current status.** This file holds the durable *why and how*. The
> answered-vs-open status of each question, and the prioritized run order, live in
> `docs/dashboard-metrics-plan.md` (the execution companion). Promoted evidence lives in
> `FINDINGS.md`. When this file and the plan disagree on what is still open, the plan and
> `FINDINGS.md` win — this file is not a second question tracker.

The current dashboard should remain a scaffold until the agenda has earned a replacement.
Dashboard concepts and candidate layouts are tracked separately in
`docs/analytical-dashboard-ideas.md` so ideas do not accidentally become product claims.

---

## 1. What we are trying to achieve

### The vision

Today's dashboard is a scaffold: a single composite "REST" score (41/100) built from four
recovery signals weighted at an arbitrary 25 points each, plus four Garmin sparklines. It
served us while we were standing the platform up. It does **not** yet help us *understand*
our stress and recovery — it reports numbers without telling us what they mean, whether they
are reliable, or what a change is worth paying attention to.

We want the dashboard to become a **copilot for understanding stress and recovery**: a
surface that knows what our data actually supports, names the state our body is in, explains
why, and lets us drill into each axis on its own tab. To get there we must first do the
honest analytical work of figuring out **which metrics we can actually use and how to define
scores from them** — across the full ~357-day dataset, not the handful of days the current
scaffold was tuned against.

### The governing principle: let the data discover the axes

We deliberately do **not** pre-declare the dashboard's pillars. The current intuition — a
"stress" pillar and a "recovery" pillar — is very likely wrong as *two* axes:

- Stress ↔ Body Battery: **−0.75**
- Stress ↔ HRV nightly: **−0.67**
- HR avg ↔ Stress: **+0.87**, HR avg ↔ Body Battery: **−0.69**

The stress-side cluster (stress, HR avg, respiration, resting HR) and the recovery-side
cluster (HRV, body battery, sleep score) move as near-mirror images. In this dataset **high
stress *is* low recovery** — two gauges driven by one underlying autonomic state. Presenting
them as independent pillars would double-count the same signal, the same flaw the current
composite already risks.

So the first job is a **dimensionality question**: how many genuinely independent axes exist
in the data, and what loads onto each? The pillars fall out of that answer.

> **Phase 1 is now answered (see `FINDINGS.md`, snapshot 2026-05-26).** The data resolved into
> **one dominant recovery↔stress axis** (stress, HR avg, resting HR, respiration on one pole; HRV,
> body battery, sleep score on the other; pairwise |r| 0.5–0.84) — *not* separate stress and
> recovery pillars. Three metrics sit off the axis: SpO2 (rejected as a recovery signal — a
> low-oxygen health *flag* only), `sleep_deep_score` (low-information — exclude from trends), and
> skin-temp deviation (an acute event-flag, not a daily gauge). `sleep_rem_score` is only weakly
> tied (r≈0.48 to sleep score) and unresolved. **Load / strain ("progress") remains genuinely
> missing** from the daily mart and is deferred to Phase 5 / `docs/ACTIVITY_ANALYTICS_DESIGN.md`
> rather than faked now. The honest output is roughly one recovery score + two health flags, not a
> handful of independent axes — see `docs/dashboard-metrics-plan.md` for the implications.

This mirrors how serious wearables decompose physiology (Whoop: Recovery / Strain / Sleep;
Oura: Readiness / Sleep / Activity) — and it makes the missing **Load** axis explicit, which
is why "progress" is deferred to future work (Phase 5) rather than faked now.

### What the data is — and is not

**Available daily metrics (~357 days, Epix Gen 2 Pro):** resting HR + HR zones, stress, body
battery, SpO2 (avg/min), respiration, nightly + weekly HRV + HRV status, sleep score (+ deep
/ REM sub-scores), skin-temp deviation.

**Known limits, carried from `FINDINGS-preliminary-2026-05.md`:**

- **No sleep duration, no training-load / activity / steps, no behavioral logs** in the daily
  mart. This is why "progress" cannot be an axis today.
- SpO2 missing on ~19.6% of days (front-loaded, clustered); HRV/sleep/skin-temp have smaller
  clustered gaps. Missingness must be handled before, not after, scoring.
- Garmin derives both stress and nightly HRV from heart-rate variability, so some
  cross-metric relationships may reflect one autonomic state measured twice. Construct-validity
  and causal claims must stay honest about this.
- This is **"a strong recovery dataset, not yet a strong training-performance dataset."** The
  program must not let the copilot over-claim.
- The preliminary findings file is archived and superseded. It is useful as a question backlog,
  but no score, axis, or UI phrase can cite it as current evidence. The active trust record is
  `FINDINGS.md`.

### Operating principles for every question

1. **Evidence over intuition.** No score weight, axis, or copilot phrase ships without a
   FINDINGS entry behind it.
2. **Period-level stats from raw readings, never from averaging daily aggregates** (project
   rule).
3. **Every question is tagged with what it produces** — a durable finding, a score
   definition, or a dashboard element. A question that changes neither a decision nor the UI
   does not earn a slot.
4. **Prefer the honest, smaller answer.** Fewer well-backed axes beat more intuitive ones.
5. **Phases are sequential.** We do not ask "how do I score this axis" before the data has
   confirmed the axis exists.
6. **Derived metrics are labeled.** Garmin-derived composites (`stress`, Body Battery,
   `hrv_status`, sleep score) are useful, but a new score built from them may mostly repackage
   Garmin's model. Each run must distinguish source-native observations from proprietary or
   derived Garmin summaries.
7. **Validation cannot only reuse discovery examples.** If November, February, or
   `2026-02-26` are used to discover an axis, they cannot be the only evidence that validates
   the score. Use holdout windows, leave-event-out checks, or clearly label the result as
   in-sample construct validation.

---

## 2. The phases

Fifteen questions across five phases. Phases 1–3 are the analyst's core work (discover →
define → validate). Phases 4–5 shape the copilot's behavior and its guardrails.

### Phase 1 — Discover the axes *(this defines the pillars)*

The output of this phase is the literal list of dashboard axes. Everything downstream depends
on it.

- **Q1.1 — How many independent dimensions are in the daily data, and what loads onto each?**
  Correlation-cluster / factor-structure analysis across all daily metrics.
  → *Produces: the actual list of pillars (likely fewer than intuition suggests).*
- **Q1.2 — Are those axes stable across the year, or do the loadings shift by regime/season?**
  Is November a *different correlation structure*, not merely worse values?
  → *Produces: whether one fixed scoring model is valid year-round, or needs regime-awareness.*
- **Q1.3 — Which metrics are redundant vs uniquely informative?** Resolve the open questions on
  `spo2_min` and `deep_score` orthogonality — keep or drop each.
  → *Produces: the metric shortlist each score is built from.*

Minimum method constraints for Phase 1:

- Use robust association checks, not only Pearson correlations. Spearman/rank checks and
  missingness sensitivity are required for skewed, bounded, and structurally missing metrics.
- Treat time-series autocorrelation as real. Use block/bootstrap uncertainty or an equivalent
  caveat when claiming loading stability or correlation strength.
- Check whether results survive known missingness blocks and major regimes. A complete-case
  result that silently drops the SpO2 missing blocks is not a dashboard-ready finding.
- Separate source-native measurements from Garmin-derived composites before deciding that two
  signals independently support the same axis.
- Produce at least one visual diagnostic for the factor/cluster result: correlation heatmap,
  clustered matrix, loading plot, or small-multiple time-series comparison.

### Phase 2 — Define each axis score

For each axis confirmed in Phase 1, decide how to turn its metrics into a single defensible
number.

- **Q2.1 — Absolute scale or personal baseline?** Should scores be z-scored against the user's
  own rolling history, and over what window (e.g. 60 / 90 days) to be both stable and
  responsive?
  → *Produces: the scoring normalization.*
- **Q2.2 — How are metrics weighted within an axis?** Equal, correlation-deflated, or
  information-weighted — replacing the current arbitrary 25/25/25/25.
  → *Produces: score weights.*
- **Q2.3 — What transform / summary does each score need?** Median vs mean given the HRV / sleep
  left-skew; any needed distribution transform.
  → *Produces: per-score center + shape handling.*
- **Q2.4 — How much smoothing before a score is readable?** The right moving-average window, and
  how to handle the truncated-left-edge problem that already misrepresented the HRV chart
  (seed lead-in days vs suppress until a full window exists).
  → *Produces: smoothing spec + edge handling.*

Every score definition must output a score contract, not only prose:

- Metric inputs, with each input labeled as source-native, derived Garmin, or backend-derived.
- Normalization rule and baseline window.
- Missing-data rule: suppress score, degrade confidence, or substitute neutral value.
- Weighting rule and why it does not double-count redundant metrics.
- Smoothing rule, including lead-in/seed behavior.
- Meaningful-change threshold and default comparison period.
- UI-safe label, tooltip explanation, and language guardrails.

### Phase 3 — Validate the scores mean something

A score is not trustworthy because it computes cleanly. Prove it.

- **Q3.1 — Does each score carry temporal structure** (autocorrelation, lead / lag), or is it
  day-to-day noise?
  → *Produces: which scores are trend-worthy vs glance-only.*
- **Q3.2 — Do the scores respond correctly to known events?** Construct validity against the
  November suppression block, the February recovery peak, and the acute 2026-02-26 dip.
  → *Produces: confidence the score reflects reality, not an artifact.*
- **Q3.3 — What is a meaningful change vs noise, per score?** Smallest worthwhile difference, so
  the copilot can say "dropped meaningfully" instead of reporting a raw "−14.4."
  → *Produces: the threshold for flagging deltas.*

Validation must explicitly state whether it is out-of-sample, leave-event-out, or in-sample
construct validation. A score that only explains the events used to design it may still be
useful, but it should not earn strong dashboard language.

### Phase 4 — Make it a copilot (narrative + drill-down)

Turn validated scores into something that explains and guides.

- **Q4.1 — Do the days cluster into a few recurring "states"?** e.g. *deep suppression / clean
  recovery / stress-loaded-but-recovering.*
  → *Produces: the copilot's headline narrative vocabulary.*
- **Q4.2 — Which signals lead vs lag when a regime shifts?** Builds on the established lagged
  stress→next-night-HRV relationship.
  → *Produces: early-warning logic ("respiration is rising before HRV drops").*
- **Q4.3 — Per axis, what is the right drill-down tab?** Which sub-metrics, what time window, and
  what comparison (vs personal baseline / vs distribution).
  → *Produces: each tab's spec.*

Copilot language guardrails apply here, even though Phase 5 finalizes them. Use "consistent
with", "suggests", "flag", "expected after", and "worth checking" before causal or diagnostic
phrasing. Do not use language that implies medical diagnosis, performance prescription, or
training readiness until the required data exists.

### Phase 5 — Honest limits & the future "progress" axis

Define where we stop and what would let us go further.

- **Q5.1 — Where would this dataset make us over-claim?** Re-state the recovery-vs-performance
  ceiling explicitly as copilot guardrails.
  → *Produces: guardrails on copilot language.*
- **Q5.2 — What is the minimum activity / training data we would need to ingest to unlock a real
  Load / Progress axis?** Which questions become answerable once it exists.
  → *Produces: the scoped trigger for future "progress" work.*

---

## 3. How this gets executed

- Each question is run through the **`finding-analyst`** skill as an independent investigation.
- Confirmed results land as durable entries in **`FINDINGS.md`** (the trusted baseline being
  rebuilt on the full 357-day dataset); provisional or predictive-only results are labeled as
  such, following the existing convention.
- Chart inspections go to `.claude/chart-inspections/<metric>-<context>/` and are never
  overwritten.
- The dashboard build is **downstream of this agenda** — the `data-analysis`,
  `analytical-dashboard`, and `ux-design` skills consume Phase 1–4 outputs to define scores,
  charts, and tabs. No dashboard scoring change ships ahead of the finding that justifies it.
- Before the first Phase 1 result ships, `FINDINGS.md` must exist and state whether there are
  any trusted findings yet. Broken or implied trust records make the dashboard contract
  unenforceable.

## 4. Open questions inherited from preliminary findings

These pre-existing leads fed into the phases above. Their current state is tracked in `FINDINGS.md`
(Resolved / Open Questions); the live status as of 2026-06-11 is:

- November suppression block extent → **resolved** (~5-week regime, Nov 5 → early Dec; `FINDINGS.md`).
- SpO2 min vs avg as the surfaced oxygen metric → **resolved** (neither — SpO2 is a health flag, not
  a recovery signal; `FINDINGS.md`).
- `deep_score` — independent signal or noise? → **resolved** (low-information; exclude from trends;
  `FINDINGS.md`).
- Median vs mean / rolling-median defaults for HRV and sleep → **partly resolved**: the static
  summary-stat policy is set (`FINDINGS.md` Distribution Snapshot); the rolling/smoothing defaults
  remain open as Phase 2 Q2.4 (plan R5).
- How much of the lagged stress→HRV link is physiology vs shared HRV-derivation → **still open**
  (needs a non-HRV-derived stressor proxy; `FINDINGS.md` Open Question; Phase 4 Q4.2 / Phase 5 Q5.1).
