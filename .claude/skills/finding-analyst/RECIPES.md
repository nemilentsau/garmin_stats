# Analytical Recipes

Named techniques the analyst applies, separate from *what* is being investigated. Recipes give reviewers something to audit and the analyst a shared vocabulary.

**Status discipline:** A recipe is `candidate` until a **trusted** run uses it, then `validated` (record the first run folder that used it). Speculation does not earn a `validated` entry. The method/caveat text below is sound general technique and is kept; but as of 2026-05-26 all `validated` flags were **reset to `candidate`** because their only validations came from early preliminary runs that are no longer relied upon (archived). Validation is being **re-earned on the full-dataset baseline study** (`2026-05-26-multi-baseline-recharacterization`) and later trusted runs. New recipes enter as `candidate` unless a trusted run already used them.

**Library availability (backend `.venv`):** `numpy`, `scipy`, `matplotlib` are installed. `pandas`, `statsmodels`, and `ruptures` are **not** — recipes that need them carry a ⚠ marker. When a run first genuinely needs one, add it as an analyst-only dependency group (keep it out of backend runtime deps) and note that in the friction log; do not reach for it speculatively. numpy + scipy cover most first-pass work.

| Recipe | Status | First used by (trusted) |
| --- | --- | --- |
| Anomaly window | validated | `2026-05-26-multi-baseline-recharacterization` |
| Pairwise correlation sweep | validated | `2026-05-26-multi-baseline-recharacterization` |
| Change-point ⚠ | validated | `2026-05-26-recovery-nov-regime-extent` (approximation; `ruptures` still not needed) |
| Lagged correlation | validated | `2026-05-27-sleep-deep-signal-or-noise` (self-autocorrelation form) |
| Partial-correlation control | validated | `2026-05-26-spo2-incremental-value` |
| Period comparison | validated | `2026-05-26-multi-baseline-recharacterization` |
| Missingness pattern | validated | `2026-05-26-multi-baseline-recharacterization` |
| Distribution shape | validated | `2026-05-26-multi-baseline-recharacterization` |
| Loading-stability comparison | validated | `2026-06-11-multi-axis-loading-stability` |
| Normalization window sweep | validated | `2026-06-11-recovery-normalization-baseline` |
| Day-type clustering ⚠ | validated | `2026-06-11-recovery-day-states` (returned a continuum / no-discrete-clusters verdict) |
| Trigger search | candidate | — (reset 2026-05-26; awaiting a trusted run) |
| Single-point context | candidate | — (reset 2026-05-26; awaiting a trusted run) |

---

## Anomaly window
- **Status:** validated (`2026-05-26-multi-baseline-recharacterization`)
- **Question shape:** Which date windows had simultaneous deviation across N metrics versus baseline?
- **Inputs:** daily metrics, a window length (e.g. 7/14 days), a baseline reference (full-period or rolling).
- **Outputs:** ranked windows with per-metric z-score / deviation magnitude. Effect size first.
- **Method:** **robust** z each metric against baseline median/MAD (×1.4826), not mean/SD — health metrics are skewed and outlier-prone. Sum |z| across metrics per rolling window. When correlated metrics would inflate a "simultaneous" count, add a **cross-cluster** score that only credits a window when *both* an on-axis and an off-axis metric deviate (the validated run used recovery-stack vs SpO2/skin-temp).
- **Caveats:** correlated metrics inflate "simultaneous" counts; one stress block drives every stress-side metric at once (use the cross-cluster score). **Rank, then look:** the validated run's top-6 raw windows included three that the timeline showed were barely above baseline and coincided with device-setup-era partial coverage — the visual demoted them. Always overlay the ranking on the full timeline before believing a window. Early/sparse-coverage windows produce false anomalies.
- **Validation:** plot the flagged window against the full series; confirm the deviation is visible, not a scaling artifact or a coverage gap.

## Pairwise correlation sweep
- **Status:** validated (`2026-05-26-multi-baseline-recharacterization`)
- **Question shape:** Across many metrics, which *pairs* co-move — and which co-movement is *not* already explained by known structure?
- **Inputs:** one representative scalar per metric family (exclude q1/q3/median/min/max siblings — they correlate ~1 within a family and swamp the ranking), full period.
- **Outputs:** all unordered pairs ranked by |Spearman r|, complete-case n per pair, each tagged explained vs under-documented.
- **Method:** Spearman per pair (rank-based; metrics are skewed/bounded), complete-case with an n floor (≥150). Render the full matrix as a heatmap for the breadth view.
- **Caveats:** **defining "explained" by a hand-coded known-pairs list is brittle** — the validated run flagged 7 within-cluster pairs as "candidates" only because the allow-list missed those edges. Prefer a *structural* notion of explained (cluster membership, or residual correlation after partialling one dominant factor). A bare pair sweep re-derives the obvious cluster; the value is in what is strong **and** off-axis. Many-comparison sweep → every hit is `tentative`.
- **Validation:** heatmap + scatter the top under-documented pairs; confirm a flagged pair is genuinely novel, not a within-cluster edge the mask missed.

## Change-point ⚠
- **Status:** validated (`2026-05-26-recovery-nov-regime-extent`, via the no-dependency approximation)
- **Question shape:** When did the baseline of metric X shift? (Including: when does a *known* regime end?)
- **Inputs:** one metric's daily series, the date range.
- **Outputs:** estimated change-point date(s) with before/after level and magnitude.
- **Method:** `ruptures` (PELT / binary segmentation) ⚠ not installed — and **not needed for a single regime with a known start/end question**. The validated approximation: recovery-/direction-signed robust z per metric, 7-day centered smoothing, then the regime edge = last day the smoothed z crosses the suppression threshold; pair with a segmented period comparison. Reserve `ruptures` for detecting *unknown* change-points across a long series.
- **Caveats:** missingness creates false change-points; smooth with a min-points-per-window guard and mask gaps. Distinguish a true regime shift from a single outlier day. **Define "recovered" strictly after the last suppressed day** — a mid-regime blip can otherwise be miscredited as the end (this bit the validated run until the logic was fixed). Edge dates are soft (threshold- and smoothing-dependent); trust the composite-level conclusion over exact per-metric days.
- **Validation:** overlay the smoothed trajectory + segment medians on the raw series; the regime and its edges should be visible by eye (they were — composite returned to band ~Dec 11).

## Lagged correlation
- **Status:** validated (`2026-05-27-sleep-deep-signal-or-noise`, self-autocorrelation form)
- **Question shape:** Does metric A on day D predict metric B on day D+k for k in 1..7?
- **Inputs:** two daily series, a lag range.
- **Outputs:** correlation per lag with sample size and CI; effect size (r) before any p-value.
- **Method:** align series at each lag with **contiguous calendar pairing** (pair D with D+k only when both real dates exist exactly k days apart and both values are present — never bridge a gap, or a "lag +1" can secretly span weeks). `scipy.stats.spearmanr` for skewed/bounded metrics (stress, HRV, sleep). `statsmodels` ⚠ only if you need cross-correlation diagnostics or autocorrelation correction.
- **Caveats:** **this is a multi-comparison sweep** (multiple lags × multiple pairs) — state N and treat a lone significant lag as `tentative`. **Autocorrelation within a series inflates significance** — use a **moving-block bootstrap** (block ≈ 7 days) for CIs rather than i.i.d. resampling (validated run measured stress AR +0.38). A raw lagged r often just re-expresses the same-day relationship plus autocorrelation; if the question is "beyond same-day," pair this with **Partial-correlation control**. Correlation ≠ causation.
- **Validation:** scatter the strongest lag; confirm it isn't driven by a handful of points.

## Partial-correlation control
- **Status:** validated (`2026-05-26-spo2-incremental-value`)
- **Question shape:** Does the A→B association survive once an obvious confound C is held constant? (e.g. does lagged stress→HRV survive controlling same-night stress and same-night HRV?)
- **Inputs:** the A,B pair plus one or more control series C, aligned on the same contiguous, all-present rows.
- **Outputs:** partial correlation r_AB·C with bootstrap CI; compared side-by-side against the raw r.
- **Method:** rank-transform all variables (partial *Spearman*), regress A and B on the controls (with intercept) via `numpy.linalg.lstsq`, correlate the residuals. The residual method generalizes to ≥2 controls (the pairwise-formula version only handles one). Block-bootstrap the whole computation for the CI.
- **Caveats:** controlling a variable *linearly* does not strip nonlinear or latent shared structure. If A and B share a derivation (e.g. Garmin computes both stress and HRV from HRV), a surviving partial may still reflect a common latent signal, not an independent channel — say so. A robustness control can only weaken the claim; declare it up-front, not after seeing whether it helps.
- **Validation:** plot raw vs partial with CIs; confirm the partial clears the pre-registered floor and the CI excludes zero.

## Period comparison
- **Status:** validated (`2026-05-26-multi-baseline-recharacterization`)
- **Question shape:** What separates the best 14-day window from the worst, by effect size?
- **Inputs:** daily metrics, two windows (or a rule to pick them).
- **Outputs:** per-metric mean diff + Cohen's d + spread + n for each window.
- **Method:** `numpy` for summaries, `scipy.stats` for effect size; report median/IQR for skewed metrics.
- **Caveats:** picking windows by an outcome then testing on the same data is circular; declare how windows were chosen. Small windows → unstable estimates.
- **Validation:** plot both windows on the full series so the reader sees what "best" and "worst" mean.

## Missingness pattern
- **Status:** validated (`2026-05-26-multi-baseline-recharacterization`)
- **Question shape:** When does metric X drop out, and does dropout covary with other state?
- **Inputs:** daily metrics including null markers, date range.
- **Outputs:** missingness rate per metric/window, clustering of gaps, covariation of dropout with other metrics.
- **Method:** boolean null mask per metric (`numpy`), gap-run detection, compare state on present vs absent days.
- **Caveats:** distinguish null (no reading) from zero (a reading of zero — e.g. the 0-BPM wrist-contact artifact). Front-loaded gaps (early device setup) are not the same as mid-series dropout.
- **Validation:** timeline plot of present/absent days per metric.

## Distribution shape
- **Status:** validated (`2026-05-26-multi-baseline-recharacterization`)
- **Question shape:** Is metric X unimodal, bimodal, or skewed? Does the shape change by month?
- **Inputs:** one metric's daily values, optional grouping (month).
- **Outputs:** histogram/KDE, skew, modality call, per-group shape.
- **Method:** `numpy.histogram`, `scipy.stats.skew`, `scipy.stats.gaussian_kde`. For a **modality** call, triangulate three diagnostics — never trust one: bimodality coefficient (Sarle's; >0.555 leans bimodal), 1- vs 2-component Gaussian mixture by **BIC** (hand-rolled 1D EM — no library has it; sklearn not installed; read ΔBIC as 0–2 negligible / 2–6 positive / 6–10 strong), and the KDE by eye. A two-Gaussian fit will *always* return two components — check the KDE is genuinely two-peaked, not one peak with a shoulder.
- **Caveats:** small per-group n makes modality unreliable; don't over-read a second bump from 8 points. **Apparent bimodality is often a regime mixture, not intrinsic** — before claiming bimodality, re-test on residuals from a long rolling median and/or within a single stable regime; if the bumps vanish, they were the pooled mixture of the series' regimes (the HRV-bimodality run found exactly this: BC 0.44, BIC tie, unimodal-with-shoulder KDE).
- **Validation:** look at the histogram/KDE — modality claims must be visible as separated peaks, not just a statistic; confirm any verdict is robust to a simple alternative (e.g. a median split reproducing a mode contrast).

## Loading-stability comparison
- **Status:** validated (`2026-06-11-multi-axis-loading-stability`)
- **Question shape:** Is a multi-metric correlation/loading structure stable across time windows (regimes, seasons), or does scoring need to be window-aware?
- **Inputs:** daily metrics for one axis, two or more pre-registered window schemes.
- **Outputs:** per-window PC1 loadings + variance share; Tucker congruence per window pair with bootstrap CI; decisive pairwise-shift list.
- **Method:** per window, rank-standardize complete-case rows and take PC1 of the Spearman matrix (sign-align on a chosen metric); Tucker congruence `φ = a·b / (|a||b|)` between window pairs; moving-block bootstrap (≈7-day blocks, both windows independently) for congruence and pairwise-r CIs. Pair with a pairwise sweep flagging |Δr| ≥ 0.30 with disjoint CIs.
- **Caveats:** within-window range restriction attenuates |r| without implying structural change — pre-register that attenuation alone is non-disqualifying, and lean the verdict on congruence + sign pattern. Count decisive shifts as **distinct metric pairs**, not comparison events. Small severe-regime windows (n < 30) give wide CIs; corroborate with a calendar scheme covering the same period. Complete-case windows silently drop the worst missing-cluster days — profile the overlap first.
- **Validation:** loading bars per window plotted side-by-side must look near-identical for a "stable" verdict; heatmaps must keep block structure visibly.

## Normalization window sweep
- **Status:** validated (`2026-06-11-recovery-normalization-baseline`)
- **Question shape:** Which baseline (absolute, expanding, trailing-W) should normalize a score, and what missing-data rule keeps it valid?
- **Inputs:** daily metrics for the score's inputs; pre-registered candidate baselines; pre-registered selection criteria anchored on *confirmed* events (regime fidelity, acute sensitivity, stable-period noise floor, coverage cost) in priority order.
- **Outputs:** per-candidate criteria table; winner (or honest no-winner); leave-one-metric-out robustness; per-day input-count distribution + low-input bias check for the missing-data rule.
- **Method:** per-metric robust z (median/MAD×1.4826, current day excluded) under each candidate; equal-weight signed probe composite (declare it is a probe, not the final weights); evaluate registered criteria; LOMO ×k to confirm the choice isn't driven by one input.
- **Caveats:** **include a hindsight absolute reference** — if a criterion fails the reference too, it measures the composite, not the baselines, and cannot rank candidates (this run's acute criterion did exactly that; demotion is a post-hoc amendment that caps the selection at provisional). Event-anchored criteria are in-sample design choices, not validation — say so and hand validation to a separate run. Trailing windows recenter on sustained regimes by ~window/2 — check the post-regime overshoot too, not just in-regime fidelity.
- **Validation:** regime-zoom overlay of all candidates (adaptation must be visible by eye); spot-check composite values by independent recomputation, including one surprising day traced back to raw values.

## Day-type clustering ⚠
- **Status:** validated (`2026-06-11-recovery-day-states` — correctly returned a continuum / no-discrete-states verdict)
- **Question shape:** What recovery-day archetypes exist across the dataset — or is it a continuum?
- **Inputs:** standardized (R3-normalized) multi-metric daily vectors.
- **Outputs:** cluster labels + centroid profiles; PCA variance shares; silhouette across k; split-half ARI; PC1-slice reproduction.
- **Method:** k-means/hierarchical (hand-rolled in numpy — no sklearn in the venv; `scipy.cluster` also works). To separate real states from continuum slices, ALSO run: PCA (a discrete-state structure needs a real 2nd dimension, PC2 ≳ 15%); silhouette across k (a continuum has no knee, monotonic decline from k=2); a **PC1-slice test** (do PC1 quantiles reproduce the clusters? ≥80% → the clusters ARE the 1D score); split-half ARI for stability.
- **Caveats:** **clustering always returns clusters** — k=2 on an elongated 1D cloud yields ~0.4 silhouette by construction, which is a *score band* (above/below baseline), not two states. Stability (high ARI) is necessary but NOT sufficient: stable clusters can still be continuum slices. The decisive tests are the 2nd-dimension check + PC1-slice reproduction + the visual (one elongated cloud vs separated blobs). Standardize first or high-variance metrics dominate.
- **Validation:** PC scatter colored by the 1D score — a smooth gradient along PC1 with no blob separation = continuum; plot centroids as a small-multiple profile only if discrete states survive.

## Trigger search
- **Status:** candidate (reset 2026-05-26)
- **Question shape:** Within a known bad window, which metrics shifted first and by how much?
- **Inputs:** daily metrics, a bounded window, a baseline.
- **Outputs:** per-metric first-deviation date + magnitude, ordered by onset.
- **Method:** z-score each metric vs baseline (`numpy`), find first sustained exceedance per metric, order onsets.
- **Caveats:** "first" is sensitive to the exceedance threshold; report the threshold. Sensor lag ≠ physiological lead.
- **Validation:** stacked small-multiples of each metric across the window with the onset marked.

## Single-point context
- **Status:** candidate (reset 2026-05-26)
- **Question shape:** Is a single sharp day-over-day move in metric X anomalous, and what co-moved?
- **Inputs:** one focal date, the metric, a baseline window around it.
- **Outputs:** the day-over-day delta as a z-score / percentile against the local distribution of deltas, plus same-day movement of correlated metrics and coverage/missingness on the focal nights.
- **Method:** distribution of consecutive-day deltas (`numpy`), z-score the focal delta; cross-check correlates and coverage.
- **Caveats:** a single point is inherently `tentative` — it cannot replicate. Garmin-provided nightly values (HRV nightly, sleep score) can move from short/partial nights or sensor gaps, not only physiology; always check coverage first.
- **Validation:** plot the focal date in context with neighbors annotated; spot-check the two endpoint values against the snapshot.

## Rule/threshold bake-off
- **Status:** candidate (added 2026-06-19, first used by `2026-06-18-hrv-recovery-cue-bakeoff`)
- **Question shape:** A classifier/threshold display is suspected bad — which replacement rule is best, on a pre-registered, candidate-agnostic scorecard?
- **Inputs:** the live rule (imported, not reimplemented) as the C0 baseline; 2-4 candidate rules defined before scoring; labeled evaluation sets cut purely from a derived quantity (e.g. acute-event set, calm/neutral set); the per-night series.
- **Outputs:** one scorecard row per candidate with identical columns — sensitivity/recall on the event set, false-headline rate on the calm set, night-to-night flip (flicker), neutral share — plus a single decision-rule verdict.
- **Method:** fix candidates + scorecard + decision rule in `01-question.md` first; reproduce the baseline's published numbers before scoring (verify-first); score every candidate identically; small-multiple the per-night headline state so flicker is visible.
- **Caveats:** **the discretization, not the threshold values, is usually the flicker source** — always include a continuous (no-category) candidate and a smoothed-basis candidate, or you only compare bucket placements. A noisy signal flips ~any same-night categorical label at a high rate regardless of cuts. Personal-SD-scaled thresholds drift as the dataset grows; call them illustrative. n-of-1 ceilings cap confidence at provisional. The mart snapshot lacks product-derived recovery quantities (nightly-vs-7d delta, 7d/30d baseline); re-derive them with the product's **positional** `prior_7d_avg` (`metrics[i-7:i]`, nulls skipped) + `safe_avg` 1-decimal rounding — a naive "last 7 non-null nights" buffer reaches across gaps and drifts the counts/flips.
- **Validation:** headline-state timeline small-multiples (categorical candidates show interleaved flicker; continuous/sustained show calm/blocked); event-window zoom confirming every candidate catches the canonical event.

## Weekday / cyclic seasonality bootstrap
- **Status:** candidate (added 2026-06-22, first used by `2026-06-18-hrv-dow-display`)
- **Question shape:** Does a calendar-cyclic pattern (day-of-week, time-of-day) in a serially-correlated daily metric survive de-trending and a real significance test — and how big is it?
- **Inputs:** the daily series; a cycle label per point (weekday); a de-trend window (centered ±k-day mean, excl-center) to strip the slow regime without leaking the cycle.
- **Outputs:** per-cycle-bin residual means with **moving-block bootstrap** 95% CIs (block ≈ n^⅓, which is also ~one cycle), an effect size (Kruskal-Wallis eps² with CI), and a **circular-shift null** p-value for the swing and eps²; split-half replication of the bin shape.
- **Method:** freeze the de-trend to reproduce any prior numbers first; moving-block bootstrap for per-bin CIs; circularly rotate the residual series vs the cycle labels (preserves autocorrelation, destroys cycle alignment) for the null; report effect size before p.
- **Caveats:** **peak-to-trough = max−min of bin means is ≥ 0 by construction — never put a bootstrap CI on it and check "excludes 0" (degenerate). Use per-bin signed CIs + a circular-shift null instead.** Autocorrelation alone manufactures a non-trivial swing (here ~6 ms), so an iid test massively overstates significance; the block/shift machinery is mandatory. A deterministic k-of-m subsample is NOT a bootstrap and tends to overstate replication. Wake-date / clock labels ≠ behavioral cause — name the label, not the inferred event. n-of-1 caps at provisional.
- **Validation:** residual bars centered on 0 with CI whiskers + per-bin n (never raw averages on a zero baseline); split-half overlay; the swing drawn against the single-observation noise band.
