# Recovery Dashboard — Design Reference

**Status:** built and shipped (2026-06-12). This is the durable reference for how the recovery
score, health flags, and the dashboard overview work. The implementation is the source of truth;
this document explains *what* the pieces are and *why*, so a maintainer does not have to
reverse-engineer them from code.

The numbers below were validated on the pinned snapshot **2026-06-11 (373 days, Garmin Epix Gen 2
Pro)**. The supporting analyst runs live in `.claude/finding-runs/2026-06-11-*` (local-only) and
the promoted evidence in `FINDINGS.md` (local-only). Each design choice cites the run that earned
it.

---

## 1. The recovery score (the central object)

**A single daily index of overall autonomic recovery state, on the user's personal scale.**

- **Inputs (7 daily aggregates):** resting HR, HR avg, stress, respiration (the *stress pole* —
  recovery-negative); body battery, nightly HRV, sleep score (the *recovery pole* —
  recovery-positive). These seven are **one axis**, not independent metrics: they co-move at
  pairwise |r| 0.5–0.84, and PC1 explains ~74% of their variance, stably across regimes and
  seasons (run `2026-06-11-multi-axis-loading-stability`).
- **Construction:**
  1. **Normalize** each metric to a robust z-score against the user's *own expanding history*
     (median/MAD×1.4826, current day excluded, ≥30 prior present days). Trailing 30–60-day
     baselines were rejected — they absorb sustained regimes (run
     `2026-06-11-recovery-normalization-baseline`).
  2. **Sign** each so higher = better recovery (the stress pole is negated).
  3. **Weight** with correlation-deflated weights, which land ≈ equal because redundancy is
     uniform (RHR .142, HRavg .148, stress .139, resp .137, BB .135, HRV .140, sleep .159);
     renormalized per day over whatever inputs are present (≥5 of 7 required). Weighting is
     practically immaterial — equal / deflated / PC1 agree at r ≥ 0.9996 (run
     `2026-06-11-recovery-score-weighting`).
  4. **Smooth** the displayed trend with a seeded trailing 7-day moving average (run
     `2026-06-11-recovery-score-smoothing-spec`).
- **Output:** a robust-z value, roughly [−3, +3]. 0 = the user's typical recovery; negative =
  suppressed; positive = strong. **Read it as level-vs-baseline and trend, never as a raw
  number.** The display keeps the z scale (no 0–100 mapping — that is a deferred UX decision).
- **What it is / isn't:** a recovery/autonomic-state summary, validated to track real regimes
  out-of-sample (§5). It is **not** a training/performance score — there is no activity, training
  load, steps, or sleep duration in the mart.

## 2. Meaningful change, band, and trend

- **Default comparison:** the 7-day mean vs the prior 7-day mean. A change is *meaningful* when
  **|Δ7| ≥ 0.97 z**; a single-day move is *acute* when **|Δ1| ≥ 1.86 z** (run
  `2026-06-11-recovery-score-meaningful-change`). Single-night events are surfaced as an acute
  note and in the raw trace, never as the headline.
- **Band:** the score is cut at **±0.5 z** into `suppressed` / `typical` / `strong`.
- **Trend:** from Δ7 against the 0.97 threshold → `improving` / `steady` / `declining`.
- **State label:** the "state before score" banner composes **band × trend** ("Typical recovery,
  improving"). Days do **not** cluster into discrete physiological archetypes — the recovery
  dimension is a continuum (PC1 74%, no separable clusters; run `2026-06-11-recovery-day-states`),
  so there are no invented "deep suppression / clean recovery" states.

## 3. Regime detection (data-driven, not hard-coded)

Sustained excursions of the MA7 score outside the typical band are detected and annotated on the
trajectory: a run of **≥14 days** where MA7 stays **≤ −0.5** (`low recovery`) or **≥ +0.5**
(`elevated recovery`), merging brief (≤3-day) returns into the band. These are *computed each
render* (`recovery_score/regimes.py`), so they generalize to any data, user, or future period —
they are not pinned dates. On the validated snapshot this finds the Nov–Dec low-recovery regime
and the Jan–Mar elevated plateau. This is presentation annotation derived from the score, carrying
no causal claim.

## 4. Health flags (oxygen, thermoregulation)

Two **flags**, not gauges — point-in-time health context, off the recovery axis (run
`2026-06-11-spo2-skintemp-flag-thresholds`):

- **Low-oxygen:** nightly `spo2_avg` < personal **median − 2.5·MAD (≈ 90.5%)**. `spo2_avg` beats
  `spo2_min` (which is integer-coarse) as the flag metric; `spo2_min` is supporting nadir detail.
  Absolute cutoffs are useless here (this user's nightly minimum runs ~80%), so the threshold is
  personal. **A missing reading is a distinct `unknown` state, never `clear`** — the ~18% SpO₂
  gaps are two structural device-coverage blocks, surfaced as `spo2_gaps`, not health events.
- **Thermoregulation:** skin-temp deviation outside personal **median ± 2.5·MAD (≈ ±0.9 °C)**,
  two-sided. Independent of the oxygen flag.

## 5. Validation (the shipping gate)

The score passed three pre-registered construct-validity tests (run
`2026-06-11-recovery-score-validation`):

- **T1 — temporal structure:** raw lag-1 autocorrelation 0.457, exceeds a block-permutation null
  at p < 1e-4 (trend-worthy, not noise).
- **T2 — leave-event-out:** with baselines frozen the day before each event, MA7 stays below the
  pre-Nov 10th percentile for 36 consecutive days and above the pre-plateau 90th percentile on 93%
  of the Feb best-window days.
- **T3 — clean holdout:** on Apr–Jun 2026 (postdates all parameter-setting), autocorrelation holds
  and the meaningful-change flag rate is a sane 8.3%.

**Caveat:** the dataset has one severe regime and one plateau — validation is strong for this data
and honest about its n-of-1 events.

## 6. The overview (anti-card; the synthesis + hub)

The overview (`frontend/src/routes/+page.svelte`) replaced the old readiness ring + four sparkline
cards + four hard-coded 0–25 components. It is organized by the data's actual structure — *one
state, read as trajectory + evidence* — not a card grid (the seven inputs are one axis; isolating
them in tiles hides the co-movement that is the point). Top to bottom:

- **State line** — the band × trend sentence + the score (small, in z). A sentence, not a gauge.
- **Recovery trajectory (the hero)** — one shared-axis time series: thin raw daily + bold seeded
  MA7, a shaded typical band, and the detected-regime annotations. Range toggles **7d / 30d / 90d
  / 180d / 360d** (default 90d), with the x-axis unit adapting (day ≤31d, month otherwise). The
  y-axis **hugs the data** (`frontend/src/lib/chart-scale.ts`) — tight bounds with round-only
  ticks, never auto-overshooting to round extremes that flatten the signal. **Hover-brushing:**
  hovering a day re-points the evidence table to that day.
- **Evidence table ("what moved it")** — the seven inputs as aligned rows (value / personal
  baseline / Δz with direction / a comparable inline sparkline / source-type), **sorted by impact
  (|Δz|)**, each metric linking into its detail tab. Hovering the trajectory repopulates these to
  the hovered day via the per-metric `driver_series`.
- **Flag strip** — two ternary chips (clear / flag / unknown), linking to `/pulse-ox` and
  `/skin-temp`. It follows trajectory hover just like the evidence table, so a historical low-SpO₂
  or temperature flag is shown when the hovered day had that flag, rather than staying pinned to the
  latest day.

The nine per-metric detail tabs (`/heart-rate`, `/hrv`, `/sleep`, `/stress`, `/body-battery`,
`/respiration`, `/skin-temp`, `/pulse-ox`) are **kept as-is** — they carry intraday curves,
distributions, sleep stages, HR zones, and circadian profiles a daily score cannot encode. The
overview is the entry point; the evidence rows and flags link into them.

> **Forcing rule (encoded in the `ux-design` and `analytical-dashboard` skills):** before any card
> grid, ask "does this data need to be compared across items, or read as a trend?" If yes, cards
> are the wrong container — use an aligned table or a shared-axis series. Cards are for independent
> entities (a routine, an experiment, one metric's own detail page).

## 7. API contract & where it is computed

`GET /api/dashboard` → `DashboardOverviewResponse`
(`backend/app/domains/garmin_analytics/contracts/dashboard.py`):

| Field | Purpose |
|---|---|
| `state` | band / trend / score_z |
| `score[]` | trajectory points (raw, seeded ma7, typical-band bounds) |
| `change` | Δ7 / Δ1 + meaningful/acute flags |
| `evidence[]` | latest-day per-input rows (value, baseline, Δz, source, tab link, sparkline) |
| `driver_series[]` | per-metric value/baseline/Δz aligned to `score` dates — powers hover-brushing |
| `flags[]` | oxygen + thermoregulation (incl. `unknown`, tab links) |
| `flag_series[]` | dated oxygen + thermoregulation states aligned to `score` dates — powers historical flag hover |
| `spo2_gaps[]` | structural SpO₂ coverage gaps |
| `events[]` | detected low/elevated regimes |
| `correlations[]` | nightly-HRV-vs-sleep/resting-HR scatters — **not shown on the overview**; retained for the HRV detail tab |

Computation lives in `domains/garmin_analytics/domain/dashboard.py` + the
`domains/garmin_analytics/domain/recovery_score/` package (`normalization`, `weighting`,
`smoothing`, `thresholds`, `flags`, `regimes`, `evidence`), each unit-tested. The frontend is
display-only: it formats and renders, computing no statistics.

## 8. Deliberately out of scope

- **No readiness score / arbitrary 0–25 components** — the scaffold this refactor removed.
- **No experiment-response number** — blocked on data: the only experiment has 5 logged exposure
  days in one block, below the noise floor, and the score shares its HRV input with the
  experiment's target (run `2026-06-11-experiment-response-detectability`). The causal question
  stays in the experiment's own analysis pipeline.
- **No load / strain / progress axis** — no activity or training-load data in the mart; see
  `docs/ACTIVITY_ANALYTICS_DESIGN.md` for what would unlock it.
- **No 0–100 display scaling yet** — the z scale ships as-is; a friendlier surface is a deferred
  UX decision.
