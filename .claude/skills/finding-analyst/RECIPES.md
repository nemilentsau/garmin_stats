# Analytical Recipes

Named techniques the analyst applies, separate from *what* is being investigated. Recipes give reviewers something to audit and the analyst a shared vocabulary.

**Status discipline:** A recipe is `candidate` until a real run uses it, then `validated` (record the first run folder that used it). Speculation does not earn a `validated` entry. The eight below are **seeded as candidates** — none is validated until exercised.

**Library availability (backend `.venv`):** `numpy`, `scipy`, `matplotlib` are installed. `pandas`, `statsmodels`, and `ruptures` are **not** — recipes that need them carry a ⚠ marker. When a run first genuinely needs one, add it as an analyst-only dependency group (keep it out of backend runtime deps) and note that in the friction log; do not reach for it speculatively. numpy + scipy cover most first-pass work.

| Recipe | Status | First used by |
| --- | --- | --- |
| Anomaly window | candidate | — |
| Change-point ⚠ | candidate | — |
| Lagged correlation | candidate | — |
| Period comparison | candidate | — |
| Missingness pattern | validated | `2026-05-26-hrv-feb25-26-drop` |
| Distribution shape | candidate | — |
| Day-type clustering ⚠ | candidate | — |
| Trigger search | validated | `2026-05-26-hrv-feb25-26-drop` |
| Single-point context | validated | `2026-05-26-hrv-feb25-26-drop` |

---

## Anomaly window
- **Status:** candidate
- **Question shape:** Which date windows had simultaneous deviation across N metrics versus baseline?
- **Inputs:** daily metrics, a window length (e.g. 7/14 days), a baseline reference (full-period or rolling).
- **Outputs:** ranked windows with per-metric z-score / deviation magnitude. Effect size first.
- **Method:** z-score each metric against baseline mean/SD (`numpy`), sum or count exceedances per window.
- **Caveats:** correlated metrics inflate "simultaneous" counts; one stress block can drive every stress-side metric at once. Skewed metrics need median/MAD, not mean/SD.
- **Validation:** plot the flagged window against the full series; confirm the deviation is visible, not a scaling artifact.

## Change-point ⚠
- **Status:** candidate
- **Question shape:** When did the baseline of metric X shift?
- **Inputs:** one metric's daily series, the date range.
- **Outputs:** estimated change-point date(s) with before/after level and magnitude.
- **Method:** `ruptures` (PELT / binary segmentation) ⚠ not installed — until then, approximate with rolling-mean crossover + a manual segmented comparison in `numpy`/`scipy`.
- **Caveats:** missingness creates false change-points; detrend or mask gaps first. Distinguish a true regime shift from a single outlier day.
- **Validation:** overlay detected segments on the raw series; the shift should be visible by eye.

## Lagged correlation
- **Status:** candidate
- **Question shape:** Does metric A on day D predict metric B on day D+k for k in 1..7?
- **Inputs:** two daily series, a lag range.
- **Outputs:** correlation per lag with sample size and CI; effect size (r) before any p-value.
- **Method:** align series at each lag, `scipy.stats.pearsonr` / `spearmanr`. `statsmodels` ⚠ only if you need cross-correlation diagnostics or autocorrelation correction.
- **Caveats:** **this is a multi-comparison sweep** (multiple lags × multiple pairs) — state N and treat a lone significant lag as `tentative`. Autocorrelation within a series inflates significance. Correlation ≠ causation.
- **Validation:** scatter the strongest lag; confirm it isn't driven by a handful of points.

## Period comparison
- **Status:** candidate
- **Question shape:** What separates the best 14-day window from the worst, by effect size?
- **Inputs:** daily metrics, two windows (or a rule to pick them).
- **Outputs:** per-metric mean diff + Cohen's d + spread + n for each window.
- **Method:** `numpy` for summaries, `scipy.stats` for effect size; report median/IQR for skewed metrics.
- **Caveats:** picking windows by an outcome then testing on the same data is circular; declare how windows were chosen. Small windows → unstable estimates.
- **Validation:** plot both windows on the full series so the reader sees what "best" and "worst" mean.

## Missingness pattern
- **Status:** validated (`2026-05-26-hrv-feb25-26-drop`)
- **Question shape:** When does metric X drop out, and does dropout covary with other state?
- **Inputs:** daily metrics including null markers, date range.
- **Outputs:** missingness rate per metric/window, clustering of gaps, covariation of dropout with other metrics.
- **Method:** boolean null mask per metric (`numpy`), gap-run detection, compare state on present vs absent days.
- **Caveats:** distinguish null (no reading) from zero (a reading of zero — e.g. the 0-BPM wrist-contact artifact). Front-loaded gaps (early device setup) are not the same as mid-series dropout.
- **Validation:** timeline plot of present/absent days per metric.

## Distribution shape
- **Status:** candidate
- **Question shape:** Is metric X unimodal, bimodal, or skewed? Does the shape change by month?
- **Inputs:** one metric's daily values, optional grouping (month).
- **Outputs:** histogram/KDE, skew, modality call, per-group shape.
- **Method:** `numpy.histogram`, `scipy.stats.skew`, `scipy.stats.gaussian_kde`.
- **Caveats:** small per-group n makes modality unreliable; don't over-read a second bump from 8 points.
- **Validation:** look at the histogram — modality claims must be visible, not just a statistic.

## Day-type clustering ⚠
- **Status:** candidate
- **Question shape:** What recovery-day archetypes exist across the dataset?
- **Inputs:** standardized multi-metric daily vectors.
- **Outputs:** cluster labels + centroid profile per cluster + cluster sizes.
- **Method:** `scipy.cluster` (hierarchical/k-means) — works without extra deps; `pandas` ⚠ convenient for the feature table but not required.
- **Caveats:** clustering always returns clusters; validate stability and interpretability before believing archetypes. Standardize first or high-variance metrics dominate.
- **Validation:** plot centroids as a small-multiple profile; confirm clusters are separable on at least two metrics.

## Trigger search
- **Status:** validated (`2026-05-26-hrv-feb25-26-drop`)
- **Question shape:** Within a known bad window, which metrics shifted first and by how much?
- **Inputs:** daily metrics, a bounded window, a baseline.
- **Outputs:** per-metric first-deviation date + magnitude, ordered by onset.
- **Method:** z-score each metric vs baseline (`numpy`), find first sustained exceedance per metric, order onsets.
- **Caveats:** "first" is sensitive to the exceedance threshold; report the threshold. Sensor lag ≠ physiological lead.
- **Validation:** stacked small-multiples of each metric across the window with the onset marked.

## Single-point context
- **Status:** validated (`2026-05-26-hrv-feb25-26-drop`)
- **Question shape:** Is a single sharp day-over-day move in metric X anomalous, and what co-moved?
- **Inputs:** one focal date, the metric, a baseline window around it.
- **Outputs:** the day-over-day delta as a z-score / percentile against the local distribution of deltas, plus same-day movement of correlated metrics and coverage/missingness on the focal nights.
- **Method:** distribution of consecutive-day deltas (`numpy`), z-score the focal delta; cross-check correlates and coverage.
- **Caveats:** a single point is inherently `tentative` — it cannot replicate. Garmin-provided nightly values (HRV nightly, sleep score) can move from short/partial nights or sensor gaps, not only physiology; always check coverage first.
- **Validation:** plot the focal date in context with neighbors annotated; spot-check the two endpoint values against the snapshot.
