# Dashboard Drill-Down Spec (R8)

**Status:** design spec — consumes the validated score contract + R7 (card count) + R9 (flags) ·
**Created:** 2026-06-11 · **Owner:** dashboard copilot effort

This is plan item **R8**: what replaces the four per-metric tabs (resting HR, HRV, sleep,
stress) now that the analysis has settled the structure. It is a *spec*, not implementation —
the build (data-analysis → analytical-dashboard → ux-design) consumes it. Frontend stays
display-only; every number, baseline, smoothing, threshold, flag state, and label below comes
from a backend analytics contract, never frontend computation.

## What this replaces, and why there are no per-metric tabs

The old dashboard had four tabs, one per Garmin metric. The analysis (R4/R1/R7) showed those
four — plus respiration, HR-avg, body battery — are **one autonomic axis**, not four
independent things. So they do not become four tabs; they become the **seven contributing
inputs of one recovery score**, surfaced together in one drill-down as an evidence stack.

Settled structure (from R7, R9):
- **One headline score:** the validated recovery score (autonomic axis).
- **Two health flags:** low-oxygen, thermoregulation — flags, not gauges (R9).
- **Sleep & REM:** drill-down sub-metrics, not a second card (R7).
- **spo2_min:** supporting nadir detail under the oxygen flag (R9).
- **deep_score:** excluded entirely (low-information).

## Information hierarchy (three tiers)

| Tier | Content | Interaction |
|---|---|---|
| **L1 — Glance** | Recovery score (MA7) + meaningful-change badge + 7-day sparkline; two flag chips (incl. "unknown") | Always visible |
| **L2 — Scan** | Evidence stack: the 7 inputs, each with value / personal baseline / delta / coverage | Visible on load |
| **L3 — Investigate** | Recovery trend (raw + MA7, 90-day, event-annotated); per-input mini-trends; flag detail panels; sleep architecture sub-section | On expand |

## L1 — Recovery headline

- **Score:** the MA7-smoothed recovery score (R5). Render as a number + a **bullet graph**
  against the personal baseline band (not a circular gauge — Few). The score is robust-z; the
  display-scaling decision (z → a 0–100 or −/0/+ surface) is the one **open contract field**
  (UX, below) — until decided, show the z value with its baseline band.
- **Meaningful-change badge:** uses R2's default comparison (7-day mean vs prior 7-day mean),
  shown only when |Δ7| ≥ 0.97 z. Label it with the comparison period ("vs prior week") and a
  direction arrow whose "good" direction is *up* (higher = better recovery). No badge when the
  change is within noise — the dashboard must not dramatize normal variation.
- **Sparkline:** 7-day MA7 trajectory, last point emphasized.
- **Acute note (secondary):** if |Δ1| ≥ 1.86 z, a small "sharp move yesterday" note — distinct
  from the headline badge. Single-night events live here and in the raw trend, never as the
  headline (R2).

## L1 — Two flag chips (oxygen, thermoregulation)

Each flag is a compact chip with **redundant encoding** (color + icon + text label — never
color alone; ~8% red-green CVD):

- **Low-oxygen flag (R9):** trips when nightly `spo2_avg < ~90.5%` (personal median−2.5·MAD).
  Three states, visually distinct:
  - **clear** (neutral/gray, no alarm),
  - **flag** (amber + droplet/lungs icon + "Low overnight O₂"),
  - **unknown** (hatched/“—” + "No SpO₂ reading") — **mandatory distinct state**; a missing
    night is never rendered clear/green. (The 18% gaps are the two structural blocks.)
- **Thermoregulation flag (R9):** trips when skin-temp deviation is outside ≈[−0.91, +0.83]°C
  (personal median±2.5·MAD). Two-sided, so the icon shows direction (above/below baseline).
  Independent of oxygen — both can be clear while the recovery score moves, and vice versa.
- **"Recent" persistence chip:** a flag fired in the trailing 7 days shows a muted "recent"
  marker. Works for oxygen (~10% of days); **for skin-temp use a shorter window (e.g. 3 days)
  or rarer threshold** — the 7-day version is too sticky (24% of days) per R9. This window
  length is a UX tuning knob, not a data finding.

## L2 — Evidence stack (the core of the drill-down)

The "why this score" panel: one row per recovery input, exposing what moved the score. This is
what replaces four separate metric tabs — all inputs in one comparable stack.

Columns per row:
1. **Metric** + **source-type badge** — `source-native` (respiration), `device-computed`
   (resting HR), `derived` (Garmin composites: stress, body battery, HRV, sleep). The badge
   makes Garmin-derived coupling visible (stress/BB/HRV share HRV derivation), per the contract.
2. **Latest value** (raw units, per-metric precision — §number formatting).
3. **Personal baseline** — the expanding robust baseline (R3), shown as the reference the z is
   measured against.
4. **Delta** — both the robust-z contribution and the raw-unit change vs baseline; signed,
   direction-correct per metric (lower resting HR = good; higher HRV = good).
5. **Meaningful?** — whether this input's move is beyond its own noise (reuses the per-metric
   robust scale).
6. **Coverage** — present / "no reading" for the day; degraded-confidence marker when the
   composite ran on <7 inputs (R3 missing-data rule).

Ordering: by absolute z-contribution (largest mover first) so the driver of today's score is
top — preattentive emphasis on what changed.

The seven rows: resting HR, HR-avg, respiration, body battery, nightly HRV, stress, sleep
score. (Weights are near-equal per R1, so do not imply a weight hierarchy in the layout —
equal-weight rows; the *delta* magnitude carries the "what moved it" story.)

## L3 — Recovery trend (investigate)

- **Default window: 90 days** for the drill-down trend (the score is a slow signal; 90d shows
  the regime → plateau → softening arc). Glance/L1 stays 7-day. Offer 7d / 30d / 90d / 1y.
- **Raw + smoothed together:** thin raw daily score + bold MA7 (R5), MA7 **seeded** across the
  left edge (W−1=6 days) so the trend doesn't ramp at the window start. Disclose the smoothing
  window in the chart subtitle.
- **Event annotations:** the promoted events (Nov regime, Feb plateau, Apr–May softening, the
  2026-02-26 acute dip) as light annotations — only because they are in `FINDINGS.md`.
- **Per-input mini-trends:** small multiples (identically scaled) of the seven inputs over the
  same window, for users who want to see which input drove a regime — replaces the old
  per-metric tab charts in one comparable grid.

## L3 — Flag detail panels

- **Oxygen panel:** `spo2_avg` line over the window with the personal flag threshold drawn;
  **structural-missing spans shown as explicit gray "no data" bands** (never bridged — break
  the line at gaps). `spo2_min` plotted as the secondary nadir series (supporting detail, not
  the flag line). Conventional 90% reference shown as a faint guide.
- **Thermoregulation panel:** skin-temp deviation with a **diverging color scale** (below /
  baseline / above — the deviation has a meaningful zero), the two-sided threshold band drawn.

## L3 — Sleep architecture sub-section (not a card)

Per R7, sleep is an input, not a second score — but `sleep_score` and `sleep_rem_score` carry
sleep-architecture detail users may want. Place them in a **collapsed sub-section inside the
recovery drill-down**, explicitly framed as "sleep detail," not as a recovery driver:
- `sleep_score` trend (it is already row 7 of the evidence stack; here with its own history).
- `sleep_rem_score` as architecture context — labeled "does not drive recovery" (R7: 79%
  independent of sleep_score but r −0.03 with recovery).
- `sleep_deep_score`: **omitted** (excluded as low-information).
- No sleep *duration* (absent from the mart) — do not imply it exists.

## Windows & comparisons (summary)

| Surface | Default window | Comparison |
|---|---|---|
| L1 recovery sparkline | 7 days | vs personal expanding baseline (R3) |
| L1 meaningful-change badge | 7d vs prior 7d (R2) | |Δ7| ≥ 0.97 z |
| L2 evidence stack | latest day | each input vs its expanding baseline |
| L3 recovery trend | 90 days (7d/30d/90d/1y) | personal baseline band + event markers |
| L3 flag panels | 90 days | personal flag threshold + structural-missing bands |

## Number formatting (per analytical-dashboard §9)

Tabular lining figures everywhere. Resting HR / HR-avg / HRV / stress: 0 decimals. Respiration:
1 decimal. SpO₂: 0 decimals (avg and min). Skin-temp deviation: 2 decimals, always signed.
Deltas: signed, with arrow + comparison-period label, direction-correct per metric.

## Backend contract implications (display-only frontend)

The API must expose, so the frontend computes nothing: the MA7 recovery score + raw score
series; per-input value/baseline/z-delta/coverage/source-type for the evidence stack;
the Δ7/Δ1 meaningful-change flags; the two health-flag states **including the explicit
"unknown" state**; the structural-missing spans for the oxygen panel; and event-annotation
windows. This extends `domains/garmin_analytics` contracts; `dashboard.py` is where the score,
flags, and evidence stack are computed.

## Explicitly out of scope (and why)

- **State banner / headline state label** — needs agenda Q4.1 (do days cluster into recurring
  states?), unanswered. Open scope decision in the plan: the overview leads with the score
  until Q4.1 is run. Do not ship a state label unbacked.
- **z → 0–100 (or −/0/+) display scaling + final UI labels/tooltips** — the one remaining
  score-contract field; a UX decision, taken at build time. Thresholds scale with it (R2).
- **Raw-nightly-values toggle on the HRV chart** — `FINDINGS.md` Open Question 5, a separate
  display question.
- **Any load / strain / training-response card** — no activity data in the mart
  (`docs/ACTIVITY_ANALYTICS_DESIGN.md`); no fake progress axis.
- **Experiment-response surfacing** — **excluded** (R10 verdict, run
  `2026-06-11-experiment-response-detectability`): blocked on data — only 5 logged exposure days
  in one block, below the score's noise floor, and the score shares its HRV input with the
  experiment's target. The dashboard must **not** show an experiment-response number for the
  meditation experiment. Revisit only when sustained exposures exist; the causal HRV question
  stays in the experiment's own analysis pipeline, not the recovery card.
