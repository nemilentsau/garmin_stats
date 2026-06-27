# HRV Tab v2 — Question-Driven Redesign

- **Date:** 2026-06-27
- **Status:** Approved design, pending spec review
- **Scope:** `frontend/src/routes/hrv/+page.svelte` and the backend HRV insights it consumes (`backend/app/domains/garmin_analytics/domain/insights/hrv.py` and related). **No change to the recovery score core.**
- **Owning skill:** `data-analysis` (aggregation + presentation). UX validated per `ux-design`.

## Motivation

The HRV tab carries many charts, but several render data without answering a question, so genuine signal reads as noise. The diagnosis: the daily metrics are shown with *time* as the only X-axis, but a chart earns its place only if it (a) shows a real trend, (b) flags a genuinely unusual night, or (c) attaches a cause to a pattern.

A second, deeper problem: "baseline" is computed three inconsistent ways for the same nightly-HRV metric — a full-history IQR band, a trailing 30-day simple mean, and (in the recovery evidence table) an expanding-window robust z. A lifetime/expanding baseline is wrong for a metric that genuinely drifts with fitness and season: it answers "is this night unusual vs my whole life" when the question is "is this night unusual *for me right now*."

This redesign reorganizes the tab around questions and replaces the per-tab baseline with a single, trailing, user-tunable definition.

## Design principle

The tab answers two kinds of question and is organized into two parts:

- **State** — "what's my HRV doing lately, and was any night off?" (recent, knob-governed)
- **Structure** — "what are my stable patterns?" (persistent, longer span)

Every surviving element must answer one of: trend, unusual-night, or cause. Anything that only describes a distribution is cut.

## State section

### Trend spine (hero)
- Keep the MA7 line over the existing **display range** picker (7d / 30d / 90d / 180d / 360d).
- Raw nightly values stay dropped (readability); the extreme-day markers below re-surface the only individual nights worth attention.
- **Display range and baseline window are independent controls** (see Window knob). The display range governs how much of the series is shown; the baseline window governs how far back the normal range looks. The backend returns the full series; the frontend slices to the display range (slicing only — no computation).

### Normal-range ribbon (changed)
- Replaces the full-history IQR band with a **trailing-window robust band**, drawn as a *moving ribbon* so the user watches their normal range drift as fitness changes.
- For each displayed night *t*, the band is computed from the present nightly values in the trailing window **before** *t* (current night excluded), using robust center/scale: `median ± 1·σ`, where `σ = MAD × 1.4826` (reuse `robust_center_scale` in `backend/app/utils/numeric.py`). This is the "typical range."

### Extreme-day markers (new)
- Mark nights whose trailing **robust |z| > 2** (`z = (value_t − median) / σ`, same trailing window and exclusion as the ribbon).
- Rationale for thresholds: a `±1σ` shaded band reads as "typical"; `|z| > 2` flags roughly the most extreme ~5% of nights — enough to be worth investigating, few enough to not be noise. Thresholds are tunable after visual calibration.
- Each marker is the entry point to the "why" question (answered later once activity/context data exists).

### Drill-in (timeline + selected night)
- Keep the day-cell timeline strip.
- In the selected-night detail panel: **remove the overnight minute-by-minute trace**; change "where this night ranks" from an all-history percentile to a **vs-trailing-window** comparison (the same robust z as the markers), so it is consistent with the knob. Keep the insight cards.

## Structure section

Persistent structural patterns get a standing home because findings get buried.

### Day-of-week bar (kept)
- Keep `compute_day_of_week`. Computed over a **long span (full history / ~6–12 months), not the knob window** — a weekday needs dozens of samples to be stable (a 30-day window has only ~4 of each weekday). This is deliberately the "stable rhythm" question, separate from "is tonight unusual."
- Future (out of scope here): overlay the candidate cause (training load / logged tags) to answer *why* the pattern exists.

### Co-movement list (kept, demoted)
- Keep as the honest "what moves with HRV," visually demoted. It is the natural stepping-stone to the activity/context story.

## Removed
- Overnight minute-by-minute HRV trace (hero and selected-night panel).
- Week-to-week box plot — "steadiness" is not an actionable question. Remove the **HRV call site only**; the shared `weekly_five_number_summaries` helper in `domain/primitives/trends.py` stays (other tabs, e.g. sleep, still use it).

## The window knob

- Segmented control `30 · 60 · 90` days, **default 60**, persisted in the URL as `?baseline=60` (shareable, refresh-safe; falls back to 60 when absent/invalid).
- Governs **one** baseline definition used everywhere in the State section: the ribbon, the extreme-day threshold, and the headline "7-day avg vs baseline" delta. It does **not** govern the Structure section (day-of-week stays on its longer span).
- Changing it refetches the HRV insights for that window (stats stay server-side per project rule). A subtle loading state covers the refetch.
- **Insufficient-data state:** if the trailing window holds fewer than a minimum number of present nights (start at 21, tunable), the ribbon/markers/delta for that point render an explicit "not enough data for this window" state rather than a misleading band.

## Backend changes

- `_compute_trend_band` and `_compute_long_baseline` in `domain/insights/hrv.py` collapse into one **trailing-window robust baseline** parameterized by the window. The hardcoded 30-day long baseline is subsumed; the headline delta becomes "7-day avg vs {window}-day baseline."
- New per-night **extreme flag** (robust |z| > 2) added to the nightly series the trend chart consumes.
- The HRV route in `garmin_analytics/routes.py` gains a `baseline` query param (default 60, validated to the allowed set), which threads into the insights computation (`domain/insights/hrv.py`) and the nightly trend series (`domain/analysis/hrv.py`, `compute_nightly_hrv_trend`).
- The HRV insights response contract changes (windowed band fields + per-night extreme flags; remove the fixed-30 long-baseline shape and the overnight-trace/box-plot fields if no longer used). Because the contract changes: **regenerate `frontend/src/lib/api-types.ts`** via `scripts/generate-api-types.sh`, then `npm run check`.
- `trailing_ma7` is unchanged (MA7 is window-independent).

## Scope & isolation

- The recovery score's expanding robust z (`domain/recovery_score/normalization.py`, `MIN_PRIOR_DAYS = 30`) is **not touched** — confirmed isolated; no re-validation needed.
- Consequence: the recovery evidence table still scores HRV with the expanding robust-z while the HRV tab uses the trailing baseline, so the two surfaces report HRV "unusualness" differently. This is intentional for this change (recovery core untouched). Reconciling them is **out of scope** here and is deliberately *not* pre-decided in favor of trailing — the recovery core's expanding window was validated, not accidental (see the Out-of-scope note and `FINDINGS.md`).

## Edge cases / degraded states
- Trailing window with < 21 present nights → explicit insufficient-data state (no garbage band/markers).
- Early in the dataset (before any window can be filled) → spine renders MA7 only; no ribbon/markers until enough trailing data exists.
- Missing nights inside a window → skipped (present-values only), consistent with existing helpers.
- Invalid/absent `?baseline` → default 60.

## Validation plan
- Backend: `uv run ruff check`, `uv run pyright app/ tests/`, `uv run pytest tests/ -v` — all green. Add tests for the windowed baseline (band, extreme flag, min-days insufficient state, window param validation) per the `testing` skill's equivalence-class discipline, including a degraded/insufficient-data case.
- Contract: regenerate API types, commit `frontend/src/lib/api-types.ts`.
- Frontend: `npm run check` clean.
- Visual: browser MCP screenshots of the redesigned tab at each knob setting (30/60/90), the insufficient-data state, and the selected-night panel — per the non-negotiable visual-verification rule.

## Out of scope / future
- Reconciling the HRV-tab baseline with the recovery-score baseline. **Do not assume the direction is "migrate the recovery core to trailing."** Run `2026-06-11-recovery-normalization-baseline` *validated and rejected* trailing 30–60d windows for the recovery score (they absorb sustained regimes); the expanding personal baseline was a deliberate choice. The two surfaces answer different questions — the HRV tab asks "is tonight unusual *right now*" (trailing), the recovery score asks "what state am I in vs my personal baseline" (expanding) — so reconciliation must either keep them deliberately distinct with clearly different labels, or re-validate before changing either. See `FINDINGS.md`.
- Exponential weighting (EWMA) of the baseline instead of a hard window.
- Attaching activity/training-load context to day-of-week and to extreme-day markers (the "why" layer) — this is the on-ramp to activity-data ingestion.
- A continuous baseline slider (would switch from URL-preset to a param-driven refetch model).

## Decisions to confirm in review
1. **Band statistic:** robust `median ± 1σ` (MAD-based) with `|z| > 2` for markers — chosen over the current IQR band so the band and the outlier threshold share one center/scale and match the recovery core's robust machinery (eases later unification). Confirm this over a windowed-IQR band.
2. **Default window 60**, presets `30 / 60 / 90`.
3. **Min present-nights = 21** for a window to render (tunable).
