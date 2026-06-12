# Dashboard Overview Spec (R8)

**Status:** design spec — consumes the validated score contract + R7 (card count) + R9 (flags) +
Q4.1 (state banner) · **Created:** 2026-06-11 · **Revised:** 2026-06-12 (scope corrected) ·
**Owner:** dashboard copilot effort

This is plan item **R8**: how the dashboard **overview** presents the validated recovery score.
It is a *spec*, not implementation — the build (data-analysis → analytical-dashboard → ux-design)
consumes it. Frontend stays display-only; every number, baseline, smoothing, threshold, flag
state, and label below comes from a backend analytics contract, never frontend computation.

## Scope — the OVERVIEW only; the detail tabs are kept and linked, not replaced

**Corrected scope (2026-06-12):** this spec changes only the dashboard **overview** (`/`). The
nine per-metric detail tabs (`/heart-rate`, `/hrv`, `/sleep`, `/stress`, `/body-battery`,
`/respiration`, `/skin-temp`, `/pulse-ox`) are **kept exactly as-is** — they carry intraday
curves, distributions, sleep stages, HR zones, and circadian profiles that a single daily score
cannot encode. The overview does **not** replace or recreate them.

The relationship: the overview is the **synthesis and entry point** — it states the overall
recovery state + trend, shows what drove it, and **links each driver into its existing detail
tab**. The tabs are the depth; the overview is the hub. The old overview's four sparkline plots +
readiness ring + four hardcoded 0–25 components are what get removed (the scaffold the refactor
targets), not any detail tab.

Settled structure (from R7, R9, Q4.1):
- **One headline score:** the validated recovery score (autonomic axis) — read as level + trend.
- **Two health flags:** low-oxygen, thermoregulation — flags, not gauges (R9); link to
  `/pulse-ox` and `/skin-temp`.
- **Sleep, REM, deep, spo2_min:** detail that lives in the existing tabs (R7/R9), reached via the
  evidence-row and flag links — NOT recreated on the overview.

## Information hierarchy (the overview is two tiers, then a link out)

| Tier | Content | Interaction |
|---|---|---|
| **L1 — State + trajectory** | State line (band × trend, a sentence); the shared-axis recovery trajectory (raw + MA7, baseline band, event annotations); two flag chips (incl. "unknown") | Always visible |
| **L2 — Evidence table** | The 7 inputs as aligned rows: value / personal baseline / Δz / inline sparkline / source-type / coverage — sorted by |Δz| | Visible on load |
| **L3 — Detail** | **The existing per-metric tabs**, reached by clicking an evidence row or a flag chip. NOT recreated on the overview. | On link-out |

## L1 — State line + recovery trajectory

- **State line (Q4.1):** "state before score" — a sentence, **not** named archetypes. The recovery
  dimension is a continuum (Q4.1: PC1 74%, no discrete clusters), so the label composes two
  validated quantities: a coarse **score band** (suppressed / typical / strong — cuts at ±0.5 z vs
  personal baseline) × a **trend direction** (improving / steady / declining — sign of R2's Δ7 vs
  its 0.97 z threshold). E.g. "Typical recovery, improving." No ring/gauge.
- **Score scale — z, for now (locked 2026-06-12):** the score is reported on its **robust-z
  scale** with the personal-baseline band. **Do not invent a 0–100 (or −/0/+) mapping yet** — the
  z value + band is the surface for this iteration. A friendlier display scale is a deferred,
  separate decision (see Out of scope); R2's thresholds are in z and stay in z until then.
- **Recovery trajectory (the hero):** one shared-axis time series — thin raw daily score + bold
  MA7 (R5), **seeded** across the left edge (W−1=6 days) so the trend doesn't ramp; the
  personal-baseline band shaded behind; event annotations (Nov regime, Feb plateau, Apr–May
  softening — only because they are promoted in `FINDINGS.md`). Default 90-day window on the
  overview hero with a 7d/30d/90d control. Disclose the MA window in the subtitle.
- **Meaningful-change badge:** R2's default comparison (7-day mean vs prior 7-day mean), shown
  only when |Δ7| ≥ 0.97 z, labeled with the period ("vs prior week") and a direction arrow whose
  "good" direction is up. No badge within noise — never dramatize normal variation.
- **Acute note (secondary):** if |Δ1| ≥ 1.86 z, a small "sharp move yesterday" note, distinct from
  the headline badge. Single-night events live here and in the raw trajectory, never as the
  headline (R2).

## L1 — Two flag chips (oxygen, thermoregulation)

Each flag is a compact chip with **redundant encoding** (color + icon + text — never color alone;
~8% red-green CVD), and **links to its detail tab**:

- **Low-oxygen flag (R9):** trips when nightly `spo2_avg < ~90.5%` (personal median−2.5·MAD).
  Three visually distinct states: **clear** (neutral), **flag** (amber + icon + "Low overnight
  O₂"), **unknown** (hatched/"—" + "No SpO₂ reading") — **mandatory distinct state**; a missing
  night is never rendered clear. Links to `/pulse-ox` for the SpO₂ detail (days-below-90%, lowest
  reading, daily trend — all already there).
- **Thermoregulation flag (R9):** trips when skin-temp deviation is outside ≈[−0.91, +0.83]°C
  (personal median±2.5·MAD). Two-sided; the icon shows direction. Independent of oxygen. Links to
  `/skin-temp` for the deviation-trend detail (already there).
- **"Recent" persistence chip:** a flag fired in the trailing 7 days shows a muted "recent"
  marker. Works for oxygen (~10% of days); for skin-temp use a shorter window (e.g. 3 days) or
  rarer threshold — the 7-day version is too sticky (24%) per R9. A UX tuning knob, not a finding.

## L2 — Evidence table (the core of the overview; links to the tabs)

The "what moved it" panel: one row per recovery input, exposing what moved the score, **each row
linking to that metric's existing detail tab**. This is an aligned table (not cards) so the reader
can scan one column and see the co-movement.

Columns per row:
1. **Metric** — a link to its detail tab (`hrv_nightly_avg`→`/hrv`, `heart_rate_resting`→
   `/heart-rate`, `stress_avg`→`/stress`, `body_battery_avg`→`/body-battery`,
   `respiration_avg`→`/respiration`, `sleep_score`→`/sleep`) + a **source-type badge**:
   `native` (respiration), `device` (resting HR / HR-avg), `derived` (the Garmin composites:
   stress, body battery, HRV, sleep). The badge makes Garmin-derived coupling visible.
2. **Latest value** (raw units, per-metric precision — §number formatting).
3. **Personal baseline** — the expanding robust baseline (R3), the reference the z is measured vs.
4. **Δ** — the robust-z contribution (and raw-unit change), signed, direction-correct per metric.
5. **Inline sparkline** — shared time window + shared normalized scale across rows so they are
   comparable (the thing four independent cards can never give).
6. **Coverage** — present / "no reading"; a degraded marker when the composite ran on <7 inputs
   (R3 missing-data rule).

Ordering: by absolute z-contribution (largest mover first) — preattentive emphasis on the driver.
Weights are near-equal per R1, so the layout implies no weight hierarchy; the Δ magnitude carries
the "what moved it" story.

The seven rows: resting HR, HR-avg, respiration, body battery, nightly HRV, stress, sleep score.

## L3 — Detail lives in the existing tabs (not recreated here)

The drill-down for any input is its **existing detail tab**, reached by clicking the evidence row
(or, for the flags, the flag chip). Those tabs already provide what a drill-down needs and more —
`/hrv` has the overnight trajectory, distribution, day-of-week, and status mix; `/heart-rate` has
the intraday curve, circadian profile, and zones; `/sleep` has the stages; `/pulse-ox` and
`/skin-temp` have the flag-metric detail. The overview must **not** duplicate these; it links to
them. (This corrects the earlier draft, which wrongly proposed recreating per-input mini-trends, a
flag-panel, and a sleep sub-section inside the overview.)

## Windows & comparisons (summary)

| Surface | Default window | Comparison |
|---|---|---|
| L1 recovery trajectory | 90 days (7d/30d/90d) | personal baseline band + event markers |
| L1 meaningful-change badge | 7d vs prior 7d (R2) | |Δ7| ≥ 0.97 z |
| L2 evidence rows | latest day + a short inline sparkline window | each input vs its expanding baseline |

## Number formatting (per analytical-dashboard §9)

Tabular lining figures everywhere. Resting HR / HR-avg / HRV / stress: 0 decimals. Respiration:
1 decimal. SpO₂: 0 decimals. Skin-temp deviation: 2 decimals, always signed. The recovery score:
robust-z, 1 decimal (e.g. "−0.2 z"). Deltas: signed, with arrow + period label, direction-correct.

## Backend contract implications (display-only frontend)

The API exposes, so the frontend computes nothing: the MA7 + raw recovery-score series with the
baseline band; per-input value / baseline / z-delta / coverage / source-type / **`tab_href`** for
the evidence rows + the inline sparkline window; the Δ7/Δ1 meaningful-change flags; the two
health-flag states **including the explicit "unknown" state** + their `tab_href`; the
structural-missing spans (carried for completeness even though the oxygen panel itself lives in
`/pulse-ox`); and the event-annotation windows. This swaps the overview models in
`domains/garmin_analytics/contracts/dashboard.py`; `domain/dashboard.py` computes them via the new
`recovery_score` domain. The per-metric endpoints (used by the detail tabs) are untouched.

## Explicitly out of scope (and why)

- **z → 0–100 (or −/0/+) display scaling + friendlier labels** — **deferred (locked 2026-06-12:
  keep the z-scale for now).** A future UX decision; R2's thresholds stay in z until then.
- **Any change to the nine detail tabs** — kept as-is; behavior-preserving code de-duplication is
  a separate, optional effort (refactor plan Phase E), not part of this spec.
- **Raw-nightly-values toggle on the HRV chart** — `FINDINGS.md` Open Question 5, a separate
  display question that belongs to `/hrv`.
- **Any load / strain / training-response card** — no activity data in the mart
  (`docs/ACTIVITY_ANALYTICS_DESIGN.md`); no fake progress axis.
- **Experiment-response surfacing** — **excluded** (R10 verdict, run
  `2026-06-11-experiment-response-detectability`): blocked on data (only 5 logged exposure days in
  one block; the score shares its HRV input with the experiment's target). The dashboard must
  **not** show an experiment-response number; the causal question stays in the experiment's own
  analysis pipeline.
