# HRV Tab — Design Decision Record (D1–D12)

**Status:** Awaiting user approval. **No product code is to be written until this is approved.**

**Source of truth:** the analyst surface audit
`.claude/finding-runs/2026-06-15-hrv-tab-current-surface-audit/05-findings.md` (all 22 surface
verdicts) and `FINDINGS.md` (Open Questions #10/#11, the day-of-week Temporal Observation).
Design principles applied from the `ux-design` and `analytical-dashboard` skills.

This record turns the analyst verdicts into final, buildable decisions. It supersedes the
"Gate 2" recommendations in `2026-06-15-hrv-tab-analyst-design-dry.md` where the analyst
evidence corrected a plan assumption (flagged **⚠ corrects plan** below).

---

## At a glance

**REMOVE** (evidence says noise / redundant / dead):
- Garmin baseline zone annotations on the trend chart (Q5)
- Overnight trajectory mini-bar + `falling_trajectory_rule` (Q12)
- Overnight `overnight_volatility_rule` (>25 ms) — dead & inverted (Q13, FINDINGS OQ#11)
- 14-day status-mix bar (Q14)
- "Weekly Avg" top-bar stat (Q7); current-status streak **headline** (Q8, keep recent-bad-run only)
- The grid of same-night correlation scatter cards (Q18)

**CHANGE:**
- Recovery cue → stop using the current fixed-ms pill as a headline; replacement classifier needs
  a short rule-selection analysis before backend behavior changes (Q6, OQ#10)
- Distribution → fix selected/latest mismatch now; decide histogram vs percentile readout after a
  short window-scope analysis (Q16, Q4)
- History strip → labeled timeline; encode delta/percentile; complete legend (Q9, Q10)
- Above-the-fold order → nightly trend is the hero; demote overnight intraday (Q22)
- Coverage/trust cue before any interpretation on thin nights (Q20)

**KEEP:**
- Nightly trend (raw dots + bold MA7) — the spine (Q1)
- All-history typical IQR band (Q3) **⚠ corrects plan** (not selected-period)
- Overnight intraday line — gated on coverage, in the selected-night detail (Q11)
- Selected-night detail panel, trimmed (Q21)
- Day-of-week — **with effect size + n** (Q17) **⚠ corrects plan** (plan expected removal)
- A compact relationships summary replacing the scatters (Q18)

---

## Decision readiness

**Ready without more dataset analysis:**
- Promote the nightly trend above the fold, keep raw dots + MA7, use one all-history typical band,
  remove Garmin baseline zones, and show gaps as gaps (D5/D-fold).
- Rename "Tonight" to "Latest night" and show weekday + ISO date for selected history (D3).
- Replace the hover-only history strip with a labeled accessible timeline (D4).
- Remove/demote Weekly Avg, current-status streak headline, trajectory mini-bar, status-mix bar,
  same-night scatter grid, long guide copy, and lagged-stress chart (D2/D6/D8/D10/D11).
- Add coverage/trust cues using existing per-night `quality.sample_count` / `coverage_hours`
  fields (D-trust).

**Needs short follow-up analysis before backend contract/behavior changes:**
- **D2 recovery cue:** the current pill is proven bad, but the replacement rule is not yet proven.
  Compare candidate displays/rules against flip rate, acute-dip detection, and false headline rate
  before changing `classify_hrv_recovery`.
- **D7 distribution:** decide whether the product should keep a histogram at all. If yes, compare
  last-90d vs selected trend range vs full-history percentile semantics for representative nights
  before adding range-scoped API fields.
- **D9 day-of-week:** the provisional signal is real enough to keep as a low-priority pattern, but
  implementation needs the displayed statistic pinned down: raw weekday averages, detrended
  residuals, effect size, and uncertainty cannot be conflated.
- **D12 contract shape:** schema changes depend on the three gates above. Contract deletion also
  needs a consumer audit, not more statistical analysis.

This is a lightweight Gate 2A, not a new full finding run unless the follow-up discovers a new
dataset claim for `FINDINGS.md`.

---

## D1 — Primary user question

**Decision:** The tab answers **"Is my nightly HRV stable, drifting, or acutely suppressed —
and what does the selected night look like in context?"**

**Why:** The recovery axis is one continuous, regime-modulated signal (FINDINGS); both
discretizations the tab currently leans on fail — the app pill flips 63% of nights (Q6) and
Garmin status is 83% one value (Q8). Read **level + trend**, never a mode label. (Rejects the
"classify HRV into modes" direction, consistent with the standing HRV-not-bimodal claim.)

## D2 — Top summary bar

**Decision:** Keep a compact 4-item bar (exempt-detail-surface; not a card grid). This
presentation decision is ready. Items:
1. **Nightly HRV** (latest/selected), `ms`, tabular figures.
2. **Δ vs prior-7-day baseline**, signed, with the comparison named in the label
   ("vs 7-day avg"). Color by a diverging (below/at/above) scale, not categorical green/red only.
3. **7-day vs 30-day drift** (the sustained-direction cue) — replaces "Weekly Avg".
4. **Trust cue** when coverage is weak; otherwise a **non-headline recovery context cue** only after
   D2A selects a replacement rule/display.

**Removed from the bar:** "Weekly Avg" (Q7 — Garmin `weekly_avg` ≈ app MA7, Pearson 0.979,
median |Δ| 1.3 ms; pure duplicate) and the **streak headline** (Q8 — 83% "days still Balanced").
Keep a *conditional* "recent low run: N d" chip only when `worst_recent_streak > 0`.

**D2A — recovery cue follow-up analysis required before backend behavior changes:** the fixed
−10/−5/+8 ms cutoffs over-discretize (stable 27%, 63% flip — Q6/OQ#10), so the current pill must
not remain a headline. But the replacement is **not yet decided**. Before changing
`classify_hrv_recovery`, compare candidate outputs on the frozen snapshot:
- same-night continuous display: signed delta + optional `delta_z`, with no categorical status;
- widened/personal same-night bands, with measured flip rate;
- sustained-move rule using 7-day-vs-30-day drift and acute-dip override;
- Garmin status as a separate chip, never OR-ed into app "suppressed".

Decision rule: approve a new classifier only if it preserves the 2026-02-26 acute-dip catch,
materially reduces headline flicker versus 63%, and makes the Garmin override conflict explicit.
Until then, the implementation should expose raw evidence (`delta_nightly_from_baseline`,
baseline label, and optionally `delta_z`) rather than inventing a new status label.

## D3 — Time language

**Decision:** Use **"Latest night"** for the top snapshot (not "Tonight"); use visible
**weekday + ISO date** for any selected history (e.g., `Thu, 2026-02-26`).

**Why:** Garmin HRV is wake-date oriented; "Tonight" mislabels it. The Q17 day-of-week rhythm
is *weekday-labeled* and its behavioral-night mapping is unconfirmed — so surface the label,
never an inferred "last night out". (The live render currently says "TONIGHT".)

## D4 — History navigation

**Decision:** Replace the hover-only strip with a **labeled compact timeline**:
- Visible **selected chip** (weekday + ISO date), **month-boundary ticks**, a **latest marker**.
- **Accessible button labels** (not `title=`), **prev/next keyboard nav**.
- Encode each night by **baseline delta / percentile on a sequential HRV-intensity scale**
  (purple, the HRV hue), reserving categorical red/amber/green for explicit status labels;
  **complete the legend** (every emitted state incl. `High`/`Unknown`).

**Why:** Q9/Q10 + live render — ~370 unlabeled cells, dates hover-only, legend missing
High/Unknown, and a 4-state color that's one value 83% of the time wastes the strip's capacity.
A sequential intensity scale carries the continuous signal the categories throw away.

## D5 — Nightly trend (the hero chart)

**Decision:** One line chart, promoted **above the fold** (D-fold):
- **Raw nightly dots** (light) + **bold 7-day MA** — both retained (Q1: one-night SD 18 ms ≈
  82% of the IQR; dropping raw re-hides acute dips like 2026-02-26).
- **One** typical band: the **all-history personal IQR** (Q3 **⚠ corrects plan** —
  a selected-period band reads 32–48 in November and *hides* the regime; full-history is the
  correct stable drift reference). Label it "your typical range (all recorded history)". Do not
  call this an expanding per-point band unless that is separately implemented.
- **Drop the Garmin baseline zones** (Q5 — a 2nd, proprietary, time-varying band that matches
  none of the app's references and is drawn for the wrong night on selection).
- **Selected-night vertical marker**; coverage gaps shown as **gaps, not bridged**.
- **Tight y-axis** via `frontend/src/lib/chart-scale.ts` (`tightScale`), ticks inside padded
  bounds — never overshoot to round numbers.

MA correctness (Q2): backend already computes MA7 over full history and the frontend slices the
*result* — no left-edge artifact. No change.

## D6 — Selected-night detail

**Decision:** Keep the inline expand below the timeline, but **trimmed**:
- Keep: **raw overnight HRV line** (gated on coverage — D-trust) + the acute Δ-vs-baseline + the
  ranked insight messages.
- **Remove:** the **trajectory mini-bar** (Q12 — overnight HRV almost always rises, median
  +10.4 ms; ±5 ms ≈ 1.3× the noise SE; direction flips 36%; "falling" is 4% and not separable
  from noise) and the **14-day status-mix bar** (Q14 — degenerate: median 1 distinct status,
  single-color 57% of nights).
- Do not duplicate one insight as stat + pill + card.

## D7 — Distribution

**Decision:** Fix the selected/latest mismatch, but do **not** add a backend field until D7A decides
whether the histogram survives.

Ready now:
- If a selected night is open, any displayed percentile/highlight must use selected-night context,
  not the latest-wired `analysis.pattern_windows` value.
- Any copy must name the reference population exactly: full history, last 90 days, or selected
  trend range.

**Why:** Q16 — full-history percentile conflates regimes (a 50 ms night is p44 full-history but
p75 in Nov / p23 in the plateau). Q4 — the frontend currently shows the latest-wired analysis
`pattern_windows` distribution; the **insights** endpoint already computes the correct
selected-keyed value (42.0 @ p27.7 for 2026-02-26) but is ignored. Strong alternative: demote the
standalone histogram to a single **"tonight = pXX of your last 90 days"** readout in the
selected-night panel, since the trend IQR band already shows the typical range.

**D7A — distribution follow-up analysis required before schema work:** compare three options with
representative dates from the low regime, high plateau, recent softening, latest night, and the
2026-02-26 acute dip:
1. Remove the standalone histogram and show one selected-night percentile readout in the
   selected-night panel.
2. Keep a compact histogram scoped to last 90 days.
3. Keep a compact histogram scoped to the selected trend range.

Decision rule: keep the histogram only if it answers a distinct question not already answered by
the trend band + raw points. If the chosen reference is not already available from existing
responses, then add the smallest backend field needed: selected value, selected percentile, total
days, and a human-readable window label.

## D8 — Weekly spread

**Decision:** Demote to **median + IQR** only; **drop min/max** (or tooltip-only); visually
de-emphasize/annotate weeks with `day_count < 5`.

**Why:** Q15 — weekly median ≈ trend MA7 (Spearman 0.89, redundant); range/IQR = 2.25× (min/max
are single-night-noise-driven); 9% of weeks have < 5 days. Keep only if the within-week IQR is
judged worth its own panel; otherwise it folds into the trend chart's raw scatter.

## D9 — Day of week

**Decision (⚠ corrects plan — KEEP, low priority):** Keep day-of-week only as a secondary
group-level pattern if D9A pins down the displayed statistic. It cannot be read on a single night.

**Why:** Q17 — a real ~10 ms weekly rhythm (Sat/Thu low) that **survives** regime de-trending
(eps² 0.061) and **replicates** (split-half r 0.75). Promoted to `FINDINGS.md` (provisional). But
it explains ~6% of variance and a single night's 18 ms noise dwarfs it — so present honestly
(effect size + n + a "doesn't determine any one night" note).

**D9A — day-of-week follow-up analysis required before implementation:** the current backend chart
exposes raw weekday averages, while the finding's strongest evidence is regime-detrended residuals
plus effect size. Before implementing, rerun the Q17 robustness check with a real bootstrap (not the
deterministic 2-of-3 subsample loop), then choose one display:
- **preferred:** compact table/bar of detrended residual mean by weekday, with `n`, effect size, and
  uncertainty/copy that names it as provisional;
- **lighter:** demote to a one-line pattern note in the selected-night panel or assistant;
- **fallback:** remove from the product tab if the display would require too much explanatory text.

Do not show raw weekday average bars with a zero baseline and call that the supported finding.

## D10 — Correlations

**Decision:** Replace the grid of "HRV vs X" scatter cards with **one compact relationships
summary** — an aligned |r| table vs the recovery axis (cards-last-resort: comparison across
metrics → aligned table, not tiles). Label it **co-movement, not cause**.

**Why:** Q18 — every partner is a strong within-axis edge (respiration −0.85 … HR avg −0.58) and
the predictors inter-correlate at mean |r| 0.71; six scatters say one thing six times and imply
causation. One aligned table states it better.

## D11 — In-page explanatory text & the lagged-stress result

**Decision:**
- Keep a **compact** HRV definition; move "how to read this" guidance into precise labels,
  footnotes, and tooltips; remove generic educational text that restates the UI.
- **Do not** put the lagged stress→HRV result on the tab. Q19 — it replicates (D+1 −0.49) but is
  *provisional, predictive-not-causal* with a shared-derivation confound; a chart can't carry
  that caveat. Surface it (if anywhere) in the **assistant** with language; it stays in FINDINGS.

## D-fold (Q22) — Above-the-fold priority

**Decision:** The fold shows, top-to-bottom: **(1)** the compact summary bar (D2), **(2)** the
**nightly trend hero chart** (D5), **(3)** the labeled history timeline (D4) entry. **Demote the
single-night overnight intraday chart** into the selected/latest-night detail (D6).

**Why:** Q22 — today the prime slot is the noisy single-night overnight chart while the trend
(the spine that answers D1) sits below the fold. Z-pattern: the most decision-relevant series
belongs top-left/hero.

## D-trust (Q20) — Coverage & trust cues

**Decision:** When the latest/selected night is low-coverage (**`sample_count < 20` or
`coverage_hours < 4`**), show a **trust cue before any interpretation**: mute/annotate the
recovery cue and gate (or badge) the overnight line. Use existing `quality.sample_count` /
`coverage_hours` (5.3% / 6.8% of nights trip these — Q11/Q20).

## D12 — Backend contract scope

Backend changes are allowed only after the readiness gates above. **If any schema
changes:** regenerate API types, then run the full backend + frontend validation
(`scripts/generate-api-types.sh`, ruff, pyright, pytest, `npm run check`).

| # | Status | Change | Driver | Contract |
| --- | --- | --- | --- | --- |
| 1 | **Blocked on D7A** | Range-scoped selected distribution + percentile, only if histogram/readout choice needs it | Q16/Q4/D7 | extend `HrvInsights.distribution` (or a ranged variant) with range-keyed `selected_value`/`selected_percentile` + window label |
| 2 | **Blocked on D2A** | Recovery classification rework, only after candidate rules are compared | Q6/D2/OQ#10 | maybe add `recovery.delta_z`; do not change `recovery.status` semantics until the new rule passes the D2A decision rule |
| 3 | **Ready** | Remove dead/invalid rules | Q12/Q13 | delete `overnight_volatility_rule` and `falling_trajectory_rule` from `hrv_rules.py`; add/update tests proving removed messages no longer emit |
| 4 | **Optional** | Coverage summary over the trend range | Q20/D-trust | only if per-night `quality` proves insufficient during implementation |
| 5 | **Blocked on D9A** | Day-of-week evidence fields, only if product keeps a chart/table | Q17/D9 | expose detrended weekday residuals/effect size/window label, or avoid schema change by demoting to static explanatory copy |

**Fields that become unused** (stop rendering; remove from contract only if no other consumer):
`baseline_bands` (D5), `trajectory` (D6), `status_mix` (D6). Stopping frontend rendering is ready;
contract deletion requires a consumer audit and focused tests, not more statistical analysis.

---

## What needs your approval before any code

1. **D2A / D12-#2:** approve a short recovery-cue rule analysis before any `classify_hrv_recovery`
   behavior change. Current state: remove the old pill as a headline; do not approve a new
   classifier yet.
2. **D5 / Q3 ⚠:** confirm keeping the **all-recorded-history** typical band (rejecting the
   earlier plan's "selected-period IQR").
3. **D9A / Q17 ⚠:** confirm whether to run the lightweight day-of-week display analysis before
   keeping a product chart. Current state: provisional signal exists; display form is not approved.
4. **Removals (D5/D6/D12-#3):** confirm deleting the trajectory, status-mix, Garmin baseline
   zones, volatility rule, and falling-trajectory rule.
5. **D7A / D12-#1:** approve a short distribution display analysis before adding range-scoped API
   fields. Current state: selected/latest mismatch must be fixed; histogram/readout choice is not
   approved.

On approval, the next step is the plan's **Gate 3** implementation sequence (shared chart
helpers → component extraction → modern data loading → apply decisions → validate), backend
contract changes first so API types regenerate before the frontend work.
