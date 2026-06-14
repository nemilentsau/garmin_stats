# Overview Tab UX Polish — Design

**Date:** 2026-06-14
**Scope:** Central dashboard (Overview, route `/`) — recovery trajectory chart, evidence table, and the global page background.

## Motivation

A UX review of the finished Overview tab surfaced four issues, validated against the
`ux-design` and `analytical-dashboard` skill rules:

1. **The trajectory axis is set by noise, not signal.** The y-axis is computed from both
   the raw daily score and the 7-day average, so the spiky raw series (≈ −2.0…+1.5)
   dictates the bounds and squeezes the bold average line into the middle ~40% of the
   plot. The average is the story; it should fill the plot.
2. **Decorative background bleeds through data surfaces.** A fixed `topo-bg` SVG
   (fractal-noise grain + "contour" line pattern) sits behind the whole app at z-index 0.
   Every panel above it is transparent, so the texture shows through the chart plot and
   the table, reading as phantom gridlines. Non-data ink (Tufte); conflicts with the
   `ux-design` rule against decorative texture.
3. **Evidence table column widths are wrong.** Only the sparkline column has a fixed
   width (110px); every other column auto-distributes across the full ~1344px table.
   The short numeric columns are `nowrap`, so the metric column absorbs all slack —
   a bloated, mostly-empty metric column next to a cramped sparkline.
4. **Sparkline color is ambiguous.** The "30 days" sparkline is tinted by the *latest
   day's* recovery status (`recoveryColor(row.recovery_good)`), painted over a 30-day
   trend. A red sparkline implies "30 bad days" when only today's delta is unfavorable.
   Color is doing double duty with the Δz cell.

## Goals / Non-Goals

**Goals:** make the average trajectory readable; remove non-data ink; fix table
proportions; disambiguate sparkline color. Contained to the Overview surface plus the
global layout background.

**Non-goals:** no changes to the recovery-score math (weights, z-scoring, regimes), the
evidence/driver-series semantics, hover-brushing behavior, or any other tab. The 7-day
average (`ma7`) window stays 7 days.

---

## Change 1 — Dispersion band replaces the raw daily line

Replace the raw daily line on the trajectory with a **±1 SD dispersion band** that
follows the 7-day average. This preserves the day-to-day spread context without a spiky
line competing with the average, and lets the axis hug the signal.

### Band definition

- **Center:** the existing `ma7` (seeded trailing 7-day average) — unchanged.
- **Width:** rolling standard deviation of the daily `raw` score over a **trailing
  14-day window**. Band edges = `ma7 ± SD`.
- **Why 14, not 7:** SD is a second-moment estimate (standard error ≈ `σ/√(2(n−1))`),
  so a 7-point SD wobbles ~45% more day-to-day, producing a "breathing" band that
  re-introduces the visual noise we are removing. 14 days gives a calm ribbon, decouples
  the band width from the 7-day center (so a single freak day doesn't lurch both), and
  smooths the SD transient at genuine regime transitions. The average line stays a 7-day
  window; only the band width uses 14.
- **Coverage rule:** None-skipping inside the window. Require **≥5 valid points** in the
  14-day window, else `band_lo`/`band_hi` are `None` for that day (no fill drawn for that
  segment). Mirrors the existing None-skipping convention in `seeded_ma7` / `_delta7`.

### Backend changes

- **New primitive** in `domains/garmin_analytics/domain/primitives/trends.py` (or a
  sibling next to `trailing_ma7`): `trailing_sd(values, window=14, min_valid=5)` →
  `list[float | None]`. None-skipping; population vs sample SD: use **sample SD**
  (`ddof=1`) since these are sampled days, consistent with treating the window as a
  sample of recent days.
- **`ScorePoint`** (`recovery_score/evidence.py`) gains `band_lo: float | None` and
  `band_hi: float | None`. Computed in `compute_recovery` from the same `display`-window
  raw scores used for `ma7`, seeded the same way (14-day window needs 13 seed days; reuse
  the existing seed mechanism, widening the seed slice to `max(window, SEED_DAYS)` days so
  the first displayed points get a full window instead of ramping up).
  - `band_lo = ma7 − sd`, `band_hi = ma7 + sd`, both `None` when `ma7` or `sd` is `None`.
- **Contract** (`contracts/dashboard.py`): `RecoveryScorePoint` gains
  `band_lo: float | None = None` and `band_hi: float | None = None`. Mapped in
  `_score_series` (`domain/dashboard.py`), rounded to 3 decimals like `raw`/`ma7`.
- **`raw` is retained** in the payload (no longer plotted as a line, but kept so the
  tooltip can still show a hovered day's actual daily value).
- Regenerate API types: `bash scripts/generate-api-types.sh`; commit
  `frontend/src/lib/api-types.ts`.

### Frontend changes (`RecoveryTrajectory.svelte`)

- **Remove** the `daily` (raw) line dataset.
- **Add a filled band** between `band_lo` and `band_hi`. Implementation: two line
  datasets sharing a `fill` between them (Chart.js `fill: '+1'` / `-1` index fill), or a
  single dataset with `fill` to a paired dataset. Pale, desaturated, **borderless**:
  `backgroundColor: 'rgba(126,168,216,0.10)'`, `borderWidth: 0`, `pointRadius: 0`. It must
  recede behind the bold average line.
- **Axis fix:** compute `tightScale` from `[band_lo, band_hi, ma7]` (filtering `None`)
  instead of `[raw, ma7]`. The band (≈ ±1 SD) is far tighter than the raw extremes, so the
  average line fills the plot.
- **Two-band distinction:** the chart now has two bands —
  - the existing **typical reference band** (constant ±0.5 z, horizontal): keep as a
    **bordered box** with its "typical" label (current `typicalBand` annotation);
  - the new **dispersion band** (follows the curve): **borderless soft fill**.
  The line-bounded box vs. soft fill gives two visually distinct treatments so they are
  not confused. This must be confirmed visually before finalizing; if they still read as
  ambiguous, fall back to a faint dashed outline on one of them.
- **Tooltip:** still title by date; show `7-day average` value, and (from retained `raw`)
  the daily value for the hovered day. Band edges need not appear in the tooltip.

> Note: the backend already sends per-point `baseline_lo`/`baseline_hi` (= ∓0.5), but the
> frontend currently hardcodes the typical band at ±0.5. Out of scope to rewire now
> (values are identical today), but noted for a future cleanup.

---

## Change 2 — Delete the topo background entirely

Remove the `topo-bg` SVG block in `+layout.svelte` (the `<svg class="topo-bg">` element,
its `<defs>` `topo-noise` filter and `topo-lines` pattern, and the two `<rect>`s) and the
`.topo-bg` CSS rule. The page keeps its solid `#0d1520` background. No data surface needs
a background change after this, because nothing decorative remains to bleed through.

The header brand icon and all other layout chrome are unaffected (separate SVG).

---

## Change 3 — Evidence table column widths (`EvidenceTable.svelte`)

Introduce a `<colgroup>` (or explicit `th` widths) so the slack goes to the sparkline,
not the metric column:

| Column   | Width                                  |
|----------|----------------------------------------|
| metric   | ~180px                                 |
| latest   | ~96px (content-sized, `nowrap`)        |
| baseline | ~96px                                  |
| Δz       | ~80px                                  |
| 30 days  | remaining width (≳ 320px at desktop)   |

Remove the fixed `td.spark { width: 110px }`; let the sparkline column flex to fill. The
mobile rule (hide `.spark` below 640px) is unchanged.

---

## Change 4 — Neutral sparkline color (`EvidenceTable.svelte`)

The sparkline currently receives the same status `color` as the Δz cell
(`recoveryColor(row.recovery_good)`, line 80/92). Pass a fixed neutral color instead
(e.g. `#5e7282`, the existing muted-blue-gray token) to `<EvidenceSparkline>`; leave the
Δz cell semantically colored (green/red + arrow). Color then means "good/bad today" in
exactly one place; the sparkline is neutral trend texture.

---

## Testing

**Backend (`backend/tests/`):**
- `trailing_sd` unit tests, equivalence classes:
  - fewer than `min_valid` valid points in window → `None`;
  - `None` values inside the window are skipped, not treated as zero;
  - a known constant series → SD 0; a known varied series → expected sample SD (`ddof=1`);
  - left-edge seeding: first displayed point uses prior days, not a ramp-up.
- `compute_recovery` / `_score_series`: `band_lo = ma7 − sd`, `band_hi = ma7 + sd`;
  both `None` when `ma7` or `sd` is `None`; rounding to 3 decimals.

**Frontend:**
- `cd frontend && npm run check` (after regenerating api-types).
- Visual verification with browser MCP at desktop (1440) and mobile (390):
  - average line now fills the plot height;
  - dispersion band reads as soft spread, visually distinct from the typical box;
  - no background texture anywhere;
  - table: metric column tightened, sparkline column wide and readable;
  - sparklines neutral; Δz still colored; empty/loading states intact.

## Validation commands

- Backend: `cd backend && uv run ruff check && uv run pyright app/ tests/ && uv run pytest tests/ -v`
- API types: `bash scripts/generate-api-types.sh` (then commit `api-types.ts`)
- Frontend: `cd frontend && npm run check`

## Risks / Open items

- **Two-band legibility** is the one thing that can only be settled visually; the design
  commits to bordered-box vs. borderless-fill, with a dashed-outline fallback.
- **Seed window widening** to 14 days must not change `ma7` output (ma7 still 7-day);
  covered by keeping the `ma7` computation untouched and only widening the slice feeding
  the new SD.
