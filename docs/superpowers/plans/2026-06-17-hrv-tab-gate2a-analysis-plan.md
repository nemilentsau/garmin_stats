# HRV Tab — Gate 2A Follow-Up Analysis Plan (D2A / D7A / D9A / D12)

**Status:** Proposed. Companion to `2026-06-17-hrv-tab-design-decisions.md`. Resolves the four
"needs short follow-up analysis before backend contract/behavior changes" gates so the D1–D12
record can move to implementation (its **Gate 3**).

**Reframe up front:** three of the four are short analyst runs; **D12 is not statistical** — the
decision record says so ("Contract deletion also needs a consumer audit, not more statistical
analysis"). So:

| Gate | Kind | Run folder? | Blocks |
| --- | --- | --- | --- |
| **D2A** recovery cue | analyst run, hypothesis-test, **extended** (resolves OQ#10) | `2026-06-18-hrv-recovery-cue-bakeoff/` | D12-#2 |
| **D7A** distribution | analyst run, question-led display decision, minimal | `2026-06-18-hrv-distribution-scope/` | D12-#1 |
| **D9A** day-of-week | analyst run, hypothesis-test, **extended** (touches provisional FINDINGS) | `2026-06-18-hrv-dow-display/` | D12-#5 |
| **D12** contract shape | engineering consumer-audit + sequencing | *checklist, no finding folder* | nothing (consumes the above) |

D2A / D7A / D9A are independent → run in parallel. D12-#3 (delete dead rules) and the
stop-rendering changes are independent of all three and can start immediately.

---

## Shared setup (all three runs)

**Data source — one frozen snapshot, reused across all three.** The audit froze
`snapshot 2026-06-16` (378 days, **365 nights**, nightly median 53 ms, SD 13.9 ms, night-to-night
delta SD ~13–18 ms). Reuse that exact snapshot (copy its `08-snapshot/`) so every number is
directly continuous with Q6/Q16/Q17. If it is unavailable or stale, re-export with
`scripts/export_snapshot.py` and **verify before analyzing** that the headline numbers reproduce
(median 53, SD 13.9, n=365) — a mismatch is itself a finding and reframes the run (analyst gate 1).
Each `03-analysis.py` declares `# DATA: .claude/finding-runs/<run>/08-snapshot/daily.csv`.

**Importable, never extended.** Replicate the live logic by *importing* from the analysis layer —
`classify_hrv_recovery` (`domains/garmin_health/domain/daily_metrics/hrv.py:37`),
`compute_hrv_distribution`, `compute_day_of_week`, `compute_trajectory`
(`domains/garmin_analytics/domain/analysis/hrv_patterns.py`). Candidate rules are defined inside
the run's `03-analysis.py`, not in product code.

**Ceremony.** D2A and D9A are **extended** (they move an Open Question / a provisional
observation, which is a `FINDINGS.md` edit → needs `02-data-profile.md`, `06-review.md`,
`07-findings-update.md`, and the confidence-set-in-05-only-downgraded-in-06 discipline). D7A is
**minimal** unless it produces a new durable claim. None promotes above `provisional` (n-of-1,
single device, single year — the interpretive ceiling stands).

---

## D2A — Recovery-cue rule bake-off

**Question (hypothesis-test).** Which replacement for the fixed −10/−5/+8 ms recovery pill best
satisfies the D2A decision rule — preserve the acute-dip catch, cut headline flicker below 63%, and
make the Garmin-status override explicit?

**Verify-first.** Reproduce on the snapshot: stable 26.6%, off-baseline 73.4%, **4-state flip rate
63.0%** (223/354 pairs), and `2026-02-26` (42 ms vs 71.0 prior-7d = **−29 ms → "suppressed"**).
This is the C0 baseline; if it does not reproduce, stop and reframe.

**Pre-registered candidates** (defined in `03-analysis.py`, frozen before scoring):
- **C0 — current:** fixed −10/−5/+8 + `is_unfavorable_hrv_status` OR-ed into "suppressed". Baseline.
- **C1 — continuous, no category:** display signed `delta` + `delta_z` (z = delta / personal
  delta-SD ≈ 13.4). No status label. Soft cue only if `|z| ≥ 1.5`.
- **C2 — personal bands:** replace fixed ms with z-bands (e.g. suppressed `z ≤ −1.0`, below
  `−0.5`, elevated `+0.5`); Garmin **not** OR-ed. Measure flip at two band widths.
- **C3 — sustained-move + acute override:** headline from the smooth `7d-vs-30d` drift
  (`long_baseline.delta_7d_vs_30d`, already computed) with a fast acute-dip override when single
  night `z ≤ −1.5`. Separates "trending down" (slow) from "tonight cratered" (fast).

Garmin-as-separate-chip is held as a fixed design treatment and measured by Gate C across all.

**Labeled evaluation sets** (built from the snapshot, pre-registered):
- *True acute dips* = nights with `delta ≤ −25 ms` (~−1.9 SD), plus `2026-02-26` by name.
- *Calm nights* = nights with `|delta| < 5 ms`.

**Scorecard — one row per candidate, every column computed identically:**

| Column | Definition | Maps to |
| --- | --- | --- |
| acute-dip recall | fraction of true-dip set the candidate visibly flags | Gate A (sensitivity) |
| calm-night false-headline rate | fraction of calm nights shown as warning/off-baseline | "false headline rate" |
| night-to-night flip rate | categorical-state changes / contiguous pairs (`N/A` for C1) | Gate B (flicker) |
| sustained-label flip rate | flip rate of the drift label specifically (C3) | Gate B |
| Garmin-only suppressions | nights called bad **solely** by the Garmin OR (delta > −10 but status unfavorable) | Gate C (override transparency) |
| neutral share | fraction in the neutral state (sanity: should be ≫ 26.6%) | over-discretization |

**Decision rule (resolves D2A → unblocks D12-#2).** Approve a candidate only if it **(A)** keeps
acute-dip recall = 1.0 including `2026-02-26`, **(B)** cuts the flip rate materially below 63% *or*
removes the categorical headline entirely (C1), and **(C)** reports Garmin-only suppressions so the
chip-separation choice is grounded. If none beats C0 on A+B jointly, fall back to the D2 position —
**expose raw evidence, invent no new label** (`delta_nightly_from_baseline` + baseline label +
optional `delta_z`). Contract impact stays additive (`recovery.delta_z`); **do not** redefine
`recovery.status` semantics unless the winner demands it.

**Plots (`04-plots/`).** (1) headline-state timeline per candidate over the full year
(small-multiples — flicker is visible at a glance); (2) `2026-02-26` window zoom showing each
candidate's call; (3) scatter of `delta` vs Garmin-status disagreement (the 100+-night conflict).

**Recipes.** Single-point context (acute-dip z), Distribution shape (delta distribution),
Normalization-window-sweep framing for the band definitions. No catalogued "rule bake-off" recipe
exists — log it as a **candidate recipe + friction note**.

---

## D7A — Distribution display scope

**Question (display decision).** Does the standalone histogram survive, and at what window scope —
remove + single readout, last-90d, or selected-trend-range?

**Verify-first.** Reproduce the conflation: a 50 ms night ranks **p44 full / p75 Nov / p23 plateau
/ p48 recent-90**, and the live bug — frontend shows the latest-wired `pattern_windows`
distribution (`69.0 @ p82`) for *all* selections while the insights endpoint already computes the
correct selected-keyed value (`42.0 @ p27.7` for `2026-02-26`).

**Pre-registered representative dates** (one concrete night per regime, pinned from the snapshot):
low regime (Nov-2025), high plateau (Jan–Mar 2026), recent softening, latest night, and the
`2026-02-26` acute dip.

**Computation.** For each representative night × each window scope ∈ {full history, last 90 days,
selected trend range, the night's local regime}, compute the selected-night percentile and the
window median/IQR → a table (rows = nights, cols = scopes). The **spread across columns per row**
is the evidence: a night swinging p23→p75 proves the percentile is not a stable answer.

**The "distinct question" test** (operationalizes the D7A decision rule): does the histogram tell
the user anything the D5 all-history IQR band + raw dots don't? Run **Distribution shape**
(bimodality coefficient + KDE) — the audit reports skew ≈ +0.01, so the distribution is likely
unimodal+symmetric, meaning the histogram's *shape* adds little beyond median/IQR.

**Decision rule (resolves D7A → unblocks D12-#1):**
- Unimodal+symmetric **and** percentile window-sensitive → **Option 1**: drop the standalone
  histogram, show one selected-night percentile readout in the selected-night panel with an
  **explicit window label** ("tonight = pXX of your last 90 days"). The trend IQR band already
  carries "typical range." This is the audit's strong alternative and needs **zero new backend
  fields** — just wire the existing insights selected-keyed value (the Q4 fix, already "ready").
- Shape carries real information in a defensible window → keep a **compact** histogram; prefer
  **last-90d (Option 2)** over selected-trend-range (Option 3): a fixed recent window is comparable
  night-to-night, whereas a window that moves with the user's zoom makes the percentile move for
  non-data reasons. Add the smallest field set (`selected_value`, `selected_percentile`,
  `total_days`, `window_label`) keyed to that window.

**Plots.** (1) percentile-vs-window heatmap (rows = representative nights, cols = scopes);
(2) full-history KDE/histogram with representative nights marked; (3) per-regime overlaid
distributions showing the conflation.

**Recipes.** Distribution shape + Normalization window sweep (both validated — the latter is
exactly "which reference population normalizes a score") + Period comparison for regime medians.

---

## D9A — Day-of-week display

**Question (hypothesis-test).** Does the ~10 ms detrended weekday rhythm survive a *real* bootstrap,
and which display honestly represents it?

**Verify-first.** Reproduce the centered ±7-day detrended residual means (Sat −5.5, Thu −3.5 …
Tue +4.5; peak-to-trough 10.0 ms), **Kruskal-Wallis eps² 0.061**, and split-half Spearman 0.75.
Note the gap D9A names: the audit's stability used a *deterministic 2-of-3 subsample loop*, **not** a
real bootstrap, and the live `compute_day_of_week` returns **raw** weekday averages, not residuals.

**Real bootstrap (the core new work).** B ≈ 5000 **moving-block** resamples (block length respects
day-to-day autocorrelation — borrow the moving-block machinery the Lagged-correlation /
Loading-stability recipes already use). Per resample, recompute the detrended residual per weekday →
**95% CI per weekday**, **CI on peak-to-trough swing**, and the bootstrap distribution of eps².

**Effect-size honesty.** State the swing (10 ms) against single-night noise (SD ~18 ms): ratio
≈ 0.56 → quantifies the "doesn't determine any one night" caveat that must ship with the display.

**Decision rule (resolves D9A → unblocks D12-#5):**
- Peak-to-trough bootstrap CI **excludes 0** and Sat/Thu-low replicates → **preferred display**:
  compact bars of **detrended residual mean by weekday** centered on 0 (never raw averages on a zero
  baseline), with per-weekday `n`, eps², bootstrap CI, and provisional copy. Confirms (does not
  upgrade past provisional) the existing FINDINGS observation, now on a real bootstrap. Backend
  (D12-#5) must then expose **detrended residuals + effect size + window label**, not raw averages —
  otherwise the product shows the wrong statistic.
- CI **includes 0** → demote to a **one-line note** (selected-night panel / assistant) or **remove**
  from the tab; **downgrade** the FINDINGS observation accordingly (a real correction, recorded in
  `07-findings-update.md`). Avoids the schema change entirely (static copy).

**Plots.** (1) detrended residual bars with bootstrap CI whiskers + per-weekday n; (2) split-half
overlay (first 182 vs last 183 days); (3) the 10 ms swing drawn against the 18 ms single-night noise
band, so the modesty of the effect is visible.

**Recipes.** Period comparison (weekday grouping) + a **weekday-seasonality moving-block bootstrap**
(catalogue as a candidate recipe + friction note; Day-type clustering's k-means machinery is the
wrong tool here).

---

## D12 — Contract shape (consumer audit, not statistics)

The "extra analysis" here is a **code + consumer audit**, gated on the three runs above. Per item:

| # | Gate | Action |
| --- | --- | --- |
| 1 | D7A | range-scoped selected distribution + percentile + window label — **only if** Option 2/3 wins; Option 1 needs no new field (wire existing insights value) |
| 2 | D2A | maybe add `recovery.delta_z`; **do not** change `recovery.status` semantics until the winning rule passes the D2A decision rule |
| 3 | **ready now** | delete `overnight_volatility_rule` + `falling_trajectory_rule` from `hrv_rules.py`; add/update tests proving the removed messages no longer emit (OQ#11 + Q12) |
| 4 | optional | trend-range coverage summary — only if per-night `quality` proves insufficient during build |
| 5 | D9A | expose detrended weekday residuals / effect size / window label — **or** avoid the schema change by demoting to static copy (per D9A's choice) |

**Consumer audit for the fields that become unused** (`baseline_bands`, `trajectory`,
`status_mix`): stop-rendering is ready (frontend-only); **contract deletion** requires confirming no
remaining consumer:
1. **Backend** — grep `app/` for each field/function: who constructs it, who reads it, which
   `hrv_rules.py` rules depend on it (known: `falling_trajectory_rule` → `trajectory`,
   `overnight_volatility_rule` → `overnight_stdev`).
2. **Contract → OpenAPI → frontend** — grep `frontend/src/lib/api-types.ts` for the generated type,
   then grep `frontend/src/` for every component reading it. Safe to delete only if no consumer
   remains after stop-rendering.
3. **Tests** — find tests asserting the field/message is emitted; update them to prove non-emission.

**Sequencing.** Do D12-#3 and the three stop-rendering changes first (independent). #1/#2/#5 land
*after* their gates, each designed to be additive or a no-op wiring fix so existing consumers don't
break. **Any schema change** → `scripts/generate-api-types.sh` → ruff, pyright, pytest,
`npm run check` (CLAUDE.md validation scope).

---

## Suggested order of work

1. **Now, no analysis needed:** D12-#3 (delete two dead rules + tests), stop-rendering of
   `baseline_bands`/`trajectory`/`status_mix`, and the Q4 selected/latest percentile wiring fix.
2. **In parallel:** D2A, D7A, D9A — each a short run against the same frozen snapshot.
3. **After the runs land their decisions:** the D12 consumer audit + the gated schema changes
   (#1/#2/#5), then full validation and API-type regeneration.
4. Promote OQ#10 (→ resolved by D2A), the day-of-week observation (confirmed/downgraded by D9A), and
   OQ#11 (resolved by the D12-#3 deletion) in the same patch as their runs.
