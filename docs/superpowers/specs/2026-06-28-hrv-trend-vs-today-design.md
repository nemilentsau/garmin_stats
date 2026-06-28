# HRV tab — separate "trend" from "today" (decouple Garmin status)

*Design spec · 2026-06-28 · branch `refactor-hr`*

## The principle (this is the durable rule)

The HRV tab presents **two distinct signals that must never be conflated**:

- **Trend / direction** — the 7-day moving average and the trailing typical-range ribbon
  ("which way am I heading"). Built from *averages*; a single night barely moves it.
- **Today** — tonight's actual nightly value and its delta vs the recent baseline
  ("how I feel this morning"). A single, un-smoothed reading.

Both are valuable and both must be present. Neither may stand in for, override, or recolor the
other. Garmin's own HRV status is a *third*, separate signal — a multi-day trend assessment on
Garmin's own baseline — and it must be surfaced on its own, never merged into either of the above.

## The problem

The verdict logic conflates trend into today. `classify_hrv_recovery` does:

```python
if delta <= -10 or is_unfavorable_hrv_status(status):   # the OR is the bug
    return "suppressed"
```

`status` is Garmin's multi-day status. So a night whose nightly HRV is **above** its recent
baseline (positive `delta`) is still labelled `"suppressed"` whenever Garmin reads Low/Unbalanced —
a trend signal overriding the today signal. Measured in this dataset: 43 of 132 "suppressed" nights
were Garmin-status-only, several with HRV +10…+27 ms above baseline (`docs/findings/hrv.html`).

The headline *color* symptom was already fixed (B1, shipped). This spec fixes the **root cause**
(the verdict) and applies the same separation to the **historical strip**, which today is colored by
each night's own Garmin status — noisy (the per-night status flips ~63% of consecutive nights) and a
conflation of "today" coloring onto a historical (trend) surface.

## Scope

**In scope**
1. Recovery verdict becomes delta-only (decouple Garmin status from `classify_hrv_recovery`).
2. Garmin status surfaced as its own labeled signal (its own chip), never merged.
3. Historical strip colored by the **averaged trend** (MA vs the typical-range band), not per-night
   status.
4. Insight-rule review for now-obsolete contradiction handling.
5. Documentation of the principle in `HRV_TAB_REFACTOR.md`.

**Explicitly out of scope (do not touch)**
- The trend chart keeps MA line + ribbon + extreme markers. **Raw nightly values do NOT go back on
  the chart** — a single night is noise; that v2 decision stands.
- The headline keeps tonight's actual value + delta vs recent baseline.
- B2 gap handling (densified calendar, breaks at gaps) is unchanged.
- Heart-rate insights and period aggregates (they already use Garmin status as their own separate
  signal — correct, leave as-is).

## Design

### 1. Recovery verdict: delta-only

`backend/app/domains/garmin_health/domain/daily_metrics/hrv.py` —
`classify_hrv_recovery` drops the `status` parameter and the `or is_unfavorable_hrv_status(status)`
branch. Tonight's recovery state is decided solely by the nightly-vs-recent-baseline delta:

```python
def classify_hrv_recovery(*, delta: float | None) -> str | None:
    if delta is None:
        return None
    if delta <= -10:
        return "suppressed"
    if delta <= -5:
        return "below_baseline"
    if delta >= 8:
        return "elevated"
    return "stable"
```

- Sole caller `_compute_recovery` (`domain/insights/hrv.py`) updates to `classify_hrv_recovery(delta=delta)`.
- `is_unfavorable_hrv_status` stays (heart-rate insights still use it as their own signal).
- Downstream consumers of `recovery.status` (the `recovery_status_rule` text and the
  `_LOW_RECOVERY_STATUSES` gating in `sleep_recovery_rule` / `resting_hr_divergence_rule`) keep
  working; their meaning simply becomes honest (no Garmin trend folded in).

### 2. Garmin status as its own labeled signal

Garmin's per-day status is already on the response (`HrvInsightsResponse.day_stats.status` and
`agg.daily[].hrv.status`). Surface it explicitly and separately:

- A small **labelled chip** — e.g. `Garmin: Unbalanced` — in the selected-night detail panel (and,
  for the latest night, near the Tonight headline), with a status-colored dot.
- Copy must frame it as Garmin's own multi-day assessment, distinct from the recovery readout. It is
  never OR-ed into the verdict and never the strip color.

### 3. Historical strip: color by the averaged trend

Add a backend-computed per-day trend classification so the strip shows *direction*, not single-night
status (frontend stays display-only — it maps a backend value to a color, computes nothing).

- **Contract:** add `trend_state: str | None` to `NightlyHrvTrendPoint`
  (`contracts/analysis.py`), values `"below" | "within" | "above"`, `None` during warmup/gaps.
- **Backend classification** (`compute_nightly_hrv_trend`), per day, from the values it already
  produces:
  - `ma7`, `band_low`, or `band_high` is `None` → `trend_state = None` (warmup or gap point)
  - `ma7 < band_low` → `"below"` (trend under the typical range)
  - `ma7 > band_high` → `"above"` (trend over the typical range)
  - otherwise → `"within"`
- **Frontend strip** (`+page.svelte`): build the day→color map from `analysis.nightly_trend`'s
  `trend_state` (keyed by date), not from `agg.daily[].hrv.status`. A `TREND_STATE_COLORS` map
  references `COLORS.*`:
  - `below` → warning red (`COLORS.heartRate`)
  - `within` → good green (`COLORS.heartRateResting`)
  - `above` → elevated teal (`COLORS.respiration`)
  - `None` / missing → neutral gray (`UNKNOWN_STATUS_COLOR`)
- The strip legend re-derives from the `trend_state` values actually present (same derive-from-present
  pattern as B11), labelled as a **trend** key (e.g. "Below / Within / Above your typical range").
- The strip color (trend) and clicking a night (that night's own z vs baseline — the "today" of that
  historical night) deliberately answer different questions; label the strip so this reads as
  "trend over time → click a night for its detail," not a contradiction.

### 4. Insight-rule review

`recovery_status_rule` previously patched the status-vs-delta contradiction in its detail text (a
bandaid for the very conflation we are removing). With the verdict now delta-only the contradiction
can no longer arise, so that special-casing is removed and the rule states the delta-based recovery
plainly. `stable_recovery_rule`'s `is_balanced_hrv_status(selected.hrv.status)` gate is **kept**
(decided): it is a confirmatory condition for a reassuring message, not a verdict override, so it does
not violate the "never conflate" principle.

### 5. Documentation

`docs/HRV_TAB_REFACTOR.md` gains a short, prominent **"Trend vs Today — never conflate"** section
stating the principle and the three rules: (a) tonight's verdict = nightly delta vs recent baseline
only; (b) Garmin status is a separate labelled signal, never OR-ed in; (c) the historical strip is
colored by the averaged trend (MA vs the typical-range band), not per-night status. The "What
shipped" / "Under the hood" sections are updated to match.

## Files touched

- `backend/.../garmin_health/domain/daily_metrics/hrv.py` — `classify_hrv_recovery` signature.
- `backend/.../garmin_analytics/domain/insights/hrv.py` — `_compute_recovery` call site.
- `backend/.../garmin_analytics/domain/insights/hrv_rules.py` — drop the contradiction bandaid; review
  `stable_recovery_rule`.
- `backend/.../garmin_analytics/contracts/analysis.py` — `NightlyHrvTrendPoint.trend_state`.
- `backend/.../garmin_analytics/domain/analysis/hrv.py` — classify `trend_state` in
  `compute_nightly_hrv_trend`.
- `frontend/src/lib/api-types.ts` — regenerated.
- `frontend/src/routes/hrv/+page.svelte` — strip colored from `trend_state`; trend legend; Garmin
  status chip.
- `docs/HRV_TAB_REFACTOR.md` — principle + rules.

## Edge cases

- **Warmup** (first ~21 nights, band `None`): `trend_state = None` → gray strip cells; no
  recovery delta → recovery `None`. No verdict invented.
- **Gaps** (B2): gap points have `ma7 = None` → `trend_state = None` → gray cell, consistent with the
  broken line.
- **Degenerate window** (zero spread, `band_low == band_high`): `ma7` equal → `"within"`; not a
  garbage extreme.
- **Garmin status absent** (`none`/null): chip hidden; strip already trend-based so unaffected.

## Testing

- `classify_hrv_recovery`: a positive/normal delta with a Garmin Low/Unbalanced status no longer
  returns `"suppressed"` (it returns `stable`/`elevated`/etc. by delta); the −10/−5/+8 boundaries
  still hold. Verdict no longer takes `status`.
- `recovery_status_rule`: no longer emits suppressed text for a positive-delta Garmin-Low night.
- `trend_state` classification: `below` / `within` / `above` boundary cases at `band_low` and
  `band_high`, and `None` for warmup/gap points.
- Frontend node test: strip colors derive from `trend_state`; legend derives from present trend
  states; Garmin status chip renders from `day_stats.status`.
- Visual: strip reads as a smooth trend heatmap (not per-night flicker); Garmin chip present and
  labelled separately; headline unchanged; chart unchanged.

## Success criteria

- No surface lets a trend signal (Garmin status, MA) decide or recolor a "today" value, and no
  "today" value drives a historical/trend surface.
- Tonight's verdict reflects tonight vs recent baseline only.
- The historical strip is a smooth, trend-faithful direction band.
- Garmin status is visible, labelled, and independent.
- The principle is documented so this does not get re-litigated.

---

## Post-review refinements (2026-06-28, after visual feedback)

The strip design above shipped, then three visual corrections were made (commit `3577163`) — this
section supersedes the earlier color/gray details:

- **Trend colors:** `below` → amber (`COLORS.stress`), `within` → green (`COLORS.heartRateResting`),
  `above` → blue (`COLORS.spo2`). (The original red/green/teal made green and teal nearly
  indistinguishable.)
- **No-reading nights are trend-colored, not gray.** The strip is a trend heatmap, so a single
  missing night takes the surrounding 7-day trend's color (`trend_state` is carried on the otherwise
  all-null gap point). The chart's line/ribbon still break at the missing night. Gray is therefore
  limited to the warm-up weeks (no band yet) and is surfaced as a **"Building baseline"** legend entry.
- **Legend is sticky** (pinned left) so it stays visible while the strip scrolls horizontally.
