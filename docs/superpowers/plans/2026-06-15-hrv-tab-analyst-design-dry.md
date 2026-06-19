# HRV Tab Analyst, Design, and DRY Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rework the HRV detail tab only after a focused analyst pass proves which current plots are meaningful and a design pass decides what the tab should actually help the user understand.

**Architecture:** Treat this as a gated workflow: analyst evidence first, design decisions second, frontend refactor third. The frontend remains display-only; any statistics, smoothing, aggregations, baselines, distributions, and derived values must come from backend read models or existing backend insight responses. The final refactor should move `/hrv` from its legacy inline page shape onto the existing metric-page and chart-helper patterns without changing unrelated tabs.

**Tech Stack:** Svelte 5 runes, Chart.js adapters, existing `$lib` metric-page components, FastAPI/Pydantic backend contracts, `uv`, `pytest`, `ruff`, `pyright`, `npm run check`, Browser MCP visual verification.

---

## Resolution status (2026-06-17)

- **Gate 1 (analyst) — DONE.** All 22 questions answered with surface verdicts in
  `.claude/finding-runs/2026-06-15-hrv-tab-current-surface-audit/05-findings.md` (extended run:
  pinned snapshot, 15 plots/captures incl. live `/hrv` screenshots, self-review). Promotions to
  `FINDINGS.md`: Open Question #10 (recovery-pill over-discretization), Open Question #11
  (overnight volatility rule dead & inverted), Temporal Observation (day-of-week rhythm,
  provisional). The analyst pass **corrected two plan assumptions**: day-of-week is KEPT (Q17),
  and the typical band stays full-history/expanding, not selected-period (Q3).
- **Gate 2 (design D1–D12) — DRAFTED, awaiting approval:**
  `docs/superpowers/plans/2026-06-17-hrv-tab-design-decisions.md`.
- **Gate 3 (implementation) — not started; do not write product code until Gate 2 is approved.**

## Current State

The current HRV route is `frontend/src/routes/hrv/+page.svelte`. It is one of the two legacy metric tabs:

- Manual page state and selected-date loading rather than `createDateLoader`.
- Inline stat-bar markup and duplicated HR/HRV CSS.
- Inline chart configs for overnight HRV, nightly trend, weekly spread, distribution, day-of-week, and scatter correlations.
- A compact historical strip where dates are only visible through hover/title text.
- Cross-domain scatter charts pulled from `api.getDashboardOverview()` rather than HRV-specific analysis.

Backend data already exists through:

- `GET /api/hrv/daily`: daily HRV stats and period summaries.
- `GET /api/hrv/analysis`: nightly trend, weekly five-number summaries, distribution/day-of-week pattern windows.
- `GET /api/hrv/insights`: selected-day HRV stats, recovery comparison, raw overnight segment, trend band, streak, long baseline, Garmin baseline bands, selected-day distribution, trajectory, status mix, and insight messages.
- `GET /api/dashboard`: same-night HRV correlations currently reused by the HRV tab.

Important current evidence from `FINDINGS.md`:

- Nightly HRV is a continuous, regime-modulated recovery signal, not a bimodal/two-state switch.
- HRV strongly co-moves with the recovery axis: body battery, respiration, resting HR, stress, and sleep.
- Stress has a provisional lagged relationship with next-night HRV; this is predictive, not causal, and partly confounded by Garmin deriving both stress and HRV from HRV-like inputs.
- Single-night HRV dips are real but noisy; display must show raw points alongside smoothing when the question is about acute moves.

Known current product risks to validate:

- The trend chart's typical band and Garmin baseline zones are driven by latest-day insight context, while the visible trend can be a selected range and the user can select a historical night.
- The pattern-window distribution is computed with `selected_nightly` equal to the latest night in `compute_hrv_analysis`, so the highlighted bin can read like the selected night but actually represent the latest night.
- Day-of-week averages may be regime confounded and may not survive a "so what?" test.
- Same-night scatter correlations may duplicate known recovery-axis structure without helping the user decide anything on the HRV tab.
- The history strip is dense but cryptic because date identity, month boundaries, and selected context are not visible until hover.

## Non-Goals

- Do not touch FIT parsing or ingest.
- Do not add frontend statistical computation.
- Do not redesign the central dashboard overview.
- Do not promote new `FINDINGS.md` claims unless an analyst run independently earns the required confidence tier.
- Do not create a second chart factory; extend the existing `frontend/src/lib/chart-options.ts` and existing chart components.
- Do not remove HRV information purely for code-size reasons. Removal or demotion must be a design decision backed by the analyst pass.

## Gate 1: Analyst Questions

Create a presentation-layer analyst run:

`.claude/finding-runs/2026-06-15-hrv-tab-current-surface-audit/`

Run type: manual exploratory with presentation-layer tracing. This is not primarily a `FINDINGS.md` promotion run; it is a product-surface audit that may produce open questions and implementation decisions.

Snapshot command:

```bash
cd backend && uv run python ../.claude/skills/finding-analyst/scripts/export_snapshot.py --out ../.claude/finding-runs/2026-06-15-hrv-tab-current-surface-audit/08-snapshot/daily.csv
```

Use recipes:

- Distribution shape
- Missingness pattern
- Pairwise correlation sweep
- Lagged correlation, only for HRV surfaces that would imply lead/lag
- Period comparison
- Single-point context for selected-night display checks

Analyst questions to answer:

1. **Nightly trend chart:** Does the current raw nightly + 7-day moving average chart answer the main HRV question: "is recovery drifting up or down?" Report visible signal, missingness, sample size, and whether raw points are necessary.

2. **Moving average correctness:** Is the backend 7-day moving average computed over full history before the frontend slices the selected display range? Confirm the left edge does not recreate the previously documented truncated-window artifact.

3. **Typical band semantics:** Should the shaded typical band be full-history, selected-period, rolling, or Garmin baseline derived? Determine which baseline best matches how the tab labels the band.

4. **Latest-vs-selected mismatch:** When a historical night is selected, which charts still use latest-night baselines, bands, or highlighted values? Identify every surface where selected context and displayed context can diverge.

5. **Garmin baseline bands:** Do Garmin-provided baseline bands align with the app's 7-day/30-day baseline logic? Decide whether to show both, one, or neither on the nightly trend chart.

6. **Recovery pill thresholds:** Are `suppressed`, `below_baseline`, `stable`, and `elevated` thresholds in `classify_hrv_recovery` consistent with the user's actual nightly HRV variability? Compare thresholds against IQR and one-night delta distribution.

7. **Weekly average stat:** Does Garmin `weekly_avg` add meaningful context beyond the 7-day moving average and 7-day baseline delta? Decide whether it belongs in the top stat bar.

8. **Streak stat:** Does current-status streak help interpret HRV, or does it over-discretize a continuous signal that existing findings say should not be read as two states?

9. **History strip status colors:** Should the strip encode Garmin status, app recovery classification, percentile band, or delta from rolling baseline? Compare the interpretability and false precision of each.

10. **History strip usability:** What date labels are needed for orientation: weekday for selected night, month ticks, week ticks, latest marker, and visible selected chip? Treat hover-only dates as a known UX failure.

11. **Overnight intraday HRV:** Are raw overnight HRV samples reliable and interpretable enough to keep as a primary latest-night chart? Check sample counts, coverage hours, obvious gaps, and whether the line shape is stable or noisy.

12. **Overnight trajectory:** Does early/mid/late trajectory have evidence value, or is it a fragile summary of sparse noisy values? Validate the 5 ms rising/falling threshold against observed overnight segment variance.

13. **Overnight volatility insight:** Is the current stdev > 25 ms rule meaningful in this dataset? Check the distribution of overnight stdev and whether high stdev actually co-occurs with low recovery or poor sleep.

14. **Status mix:** Does 14-day status mix help explain selected-night context, or is it redundant with streak and trend? Decide whether it belongs in the selected-night panel.

15. **Weekly spread:** Does the weekly five-number summary reveal meaningful HRV variability, or do min/max lines add noise? Decide whether to show median + IQR only and move min/max to tooltip.

16. **Distribution:** Is a distribution histogram useful for the HRV tab? If yes, should it show full history, selected range, or selected-night percentile within the current range? Decide the highlight semantics.

17. **Day-of-week:** Are weekday HRV differences large enough after controlling for month/regime to justify a chart? If not, remove or demote it.

18. **Same-night correlations:** Do the current HRV scatter charts teach anything beyond known recovery-axis co-movement? Decide whether to keep, demote, or replace them with a smaller "relationships" summary.

19. **Lagged stress relationship:** Should the HRV tab surface the provisional stress(D) -> HRV(D+1) result, or is that better kept in findings/assistant because it needs caveats?

20. **Coverage and trust:** Which HRV views need explicit coverage/sample-count warnings? Define suppress/flag thresholds for latest-night, selected-night, and trend displays.

21. **Single-night dip handling:** Does the tab make acute dips inspectable without overreacting to noise? Use the documented 2026-02-25 to 2026-02-26 HRV drop as a spot-check.

22. **Above-the-fold priority:** If only three HRV surfaces can be visible without scrolling on desktop, which surfaces earn the space by answering a distinct question?

Required analyst artifacts:

- `01-question.md`: one manual-exploratory question covering current HRV tab surfaces.
- `03-analysis.py`: loads the pinned snapshot and any captured API responses needed to trace displayed values.
- `04-plots/`: annotated static plots plus live-render screenshots of `/hrv`.
- `05-findings.md`: one section per surface with verdict `keep`, `change`, `demote`, `remove`, or `needs backend field`.

## Gate 2: Design Decisions To Make

Record these decisions in the plan or in a follow-up design spec before implementation starts.

### D1. Primary User Question

Decide the HRV tab's main job:

- Recommended: "Show whether nightly HRV is stable, drifting, or acutely suppressed, and explain the selected night in context."
- Rejected direction: "Classify HRV into modes." Existing evidence says HRV is continuous and regime-modulated, not a two-state switch.

### D2. Top Summary Bar

Choose the four top-level summary items. Candidate set:

- Nightly HRV, selected/latest night.
- Delta vs prior 7-day baseline.
- 7-day vs 30-day baseline drift.
- Garmin status or app recovery status.
- Coverage/sample count when weak.
- Streak only if analyst pass proves it helps and does not over-discretize.

Design decision:

- Keep a compact stat bar, but labels must say exactly which baseline each delta uses.
- If latest data is partial or low coverage, the top row should show a trust cue before any interpretation.

### D3. Time Language

Decide whether the surface says `Tonight`, `Latest night`, or `Selected night`.

Recommended:

- Use `Latest night` for the top snapshot because Garmin sleep/HRV date semantics are wake-date oriented and may not mean the current evening.
- Use visible weekday plus ISO date for selected history, for example `Fri, 2026-02-26`.

### D4. History Navigation

Replace the hover-only day strip with a labeled compact timeline.

Required properties:

- Visible selected chip with weekday/date.
- Month boundary ticks and labels.
- Latest marker.
- Accessible button labels, not only `title`.
- Keyboard navigation through previous/next night.
- Color legend that includes every emitted state, including `High` or `Unknown` if present.

Open design choice:

- If status colors are too categorical, encode baseline delta/percentile with a sequential HRV intensity scale and reserve red/amber/green for explicit status labels.

### D5. Nightly Trend

Decide exactly which lines/bands appear.

Recommended default if analyst pass agrees:

- Raw nightly dots/light line.
- 7-day moving average bold line.
- One baseline band only: either selected-period IQR or Garmin baseline band, not both unless the distinction is visually obvious.
- Selected-night vertical marker.
- Coverage gaps shown as gaps, not bridged.

Axis decision:

- Use tight y-axis scaling from `frontend/src/lib/chart-scale.ts` for visible HRV values and displayed bands, with ticks inside the padded bounds.

### D6. Selected-Night Detail

Decide whether the selected-night panel should stay inline below the history strip.

Recommended:

- Keep inline expansion for now; it preserves context and matches the HR tab.
- Put overnight intraday HRV, trajectory, status mix, and insights in a single selected-night panel only if each survives the analyst pass.
- Do not duplicate the same insight as both stat, pill, and card.

### D7. Distribution

Decide histogram scope and highlight semantics.

Recommended:

- Distribution bins follow the selected trend range.
- Highlight uses the currently selected night when one is selected, otherwise latest night.
- Percentile copy must name the reference population: `within last 90 days`, `within full history`, or another exact range.

Implementation implication:

- Prefer backend-provided bins from `HrvPatternWindow`; frontend may compare backend-provided selected/latest nightly value to bin edges for rendering highlight, because that is display mapping, not statistical computation.
- Add a backend field only if range-specific selected percentile is needed and cannot be represented honestly with existing responses.

### D8. Weekly Spread

Decide whether weekly five-number summary stays.

Recommended:

- Keep only if it reveals variability that the nightly trend does not.
- Default display should emphasize median + IQR.
- Min/max can remain in tooltip or be removed if they are artifact-prone.
- Weeks with low `day_count` must be visually de-emphasized or annotated.

### D9. Day Of Week

Decide whether day-of-week belongs on the tab.

Recommended:

- Remove if weekday effects do not survive regime/month controls or have no actionable interpretation.
- If retained, show sample count and effect size, not just colored bars.

### D10. Correlations

Decide whether cross-domain scatter plots belong on the HRV detail tab.

Recommended:

- Keep only the relationships that help interpret HRV, not every dashboard correlation.
- Avoid presenting correlations as causes.
- Consider replacing multiple scatter cards with a compact relationship table if the analyst pass finds the scatterplots visually redundant.

### D11. In-Page Explanatory Text

Decide whether `MetricDefinition` should remain as a long reading guide.

Recommended:

- Keep a compact definition if needed.
- Move "how to use this dashboard" guidance into precise labels, footnotes, and tooltips where it clarifies the data.
- Remove generic educational text that repeats visible UI behavior.

### D12. Backend Contract Scope

Backend change is allowed only for decisions that require backend-derived fields:

- Range-specific selected percentile.
- Range-specific trend band.
- Coverage summary over a trend range.
- Selected-night distribution scoped to the selected trend range.

If any backend schema changes:

```bash
bash scripts/generate-api-types.sh
cd frontend && npm run check
cd backend && uv run ruff check
cd backend && uv run pyright app/ tests/
cd backend && uv run pytest tests/ -v
```

## Gate 3: Implementation Sequence

### Task 1: Run HRV Surface Analyst Audit

**Files:**
- Create: `.claude/finding-runs/2026-06-15-hrv-tab-current-surface-audit/01-question.md`
- Create: `.claude/finding-runs/2026-06-15-hrv-tab-current-surface-audit/03-analysis.py`
- Create: `.claude/finding-runs/2026-06-15-hrv-tab-current-surface-audit/04-plots/*`
- Create: `.claude/finding-runs/2026-06-15-hrv-tab-current-surface-audit/05-findings.md`

- [ ] Freeze snapshot with the command in Gate 1.
- [ ] Capture current `/hrv` desktop screenshot, selected-night-open screenshot, and mobile screenshot.
- [ ] Trace API values for `/api/hrv/analysis`, `/api/hrv/insights?date=<latest>`, `/api/hrv/insights?date=<historical>`, and `/api/dashboard`.
- [ ] Answer all analyst questions with explicit surface verdicts.
- [ ] Record implementation-affecting decisions as `keep/change/demote/remove/needs backend field`.

Expected result: a local-only analyst run that tells implementation exactly which HRV surfaces survive.

### Task 2: Write HRV Design Decision Record

**Files:**
- Modify: `docs/superpowers/plans/2026-06-15-hrv-tab-analyst-design-dry.md`

- [ ] Convert analyst verdicts into final decisions D1-D12.
- [ ] Record any backend fields required, with exact contract names.
- [ ] Record any chart or component removals explicitly.
- [ ] Get user approval before touching product code.

Expected result: no implementation ambiguity remains.

### Task 3: Extend Shared Chart Options For HRV Needs

**Files:**
- Modify: `frontend/src/lib/chart-options.ts`
- Test by use: `frontend/src/routes/hrv/+page.svelte`

- [ ] Add reusable helpers only where HRV and the broader metric-page refactor need them.
- [ ] Support line charts with raw series, smoothed series, optional IQR/baseline band, optional click handler, and tight y-axis scaling.
- [ ] Support weekly five-number line/band charts with min/max optional.
- [ ] Support histogram bar configs with caller-supplied highlight selection.
- [ ] Support scatter configs only if correlations remain on HRV.

Expected result: HRV chart configs shrink without introducing a parallel chart factory.

### Task 4: Extract Shared Legacy Page Components

**Files:**
- Create or modify: `frontend/src/lib/components/StatBar.svelte`
- Create or modify: `frontend/src/lib/components/MetricHistoryStrip.svelte`
- Create or modify: `frontend/src/lib/components/InsightLine.svelte`
- Modify: `frontend/src/routes/hrv/+page.svelte`
- Later consumer: `frontend/src/routes/heart-rate/+page.svelte`

- [ ] Extract only pieces duplicated by HRV and heart rate or clearly reusable by metric detail pages.
- [ ] Keep HRV-specific pieces such as trajectory and status mix local unless the HR tab also needs them.
- [ ] Ensure date strip buttons have visible labels/markers and accessible labels.
- [ ] Keep stable dimensions for cells, controls, charts, and selected panel.

Expected result: HRV page loses duplicated CSS and markup while preserving deliberate HRV-specific UI.

### Task 5: Modernize HRV Data Loading And Shell

**Files:**
- Modify: `frontend/src/routes/hrv/+page.svelte`
- Use existing: `frontend/src/lib/realtime-page.ts`
- Use existing: `frontend/src/lib/components/PageState.svelte`
- Use existing: `frontend/src/lib/components/MetricPageHeader.svelte`
- Use existing: `frontend/src/lib/components/ChartCard.svelte`

- [ ] Replace manual selected-date request id logic with `createDateLoader<HrvInsights>`.
- [ ] Wrap route content in `PageState`.
- [ ] Use `MetricPageHeader` for title and trend-range control, unless D3 chooses a custom latest/selected header.
- [ ] Use `ChartCard` for retained charts.
- [ ] Preserve latest-day fetch and selected-night fetch semantics.

Expected result: HRV joins the modern metric-page pattern.

### Task 6: Apply Design Decisions To HRV Surfaces

**Files:**
- Modify: `frontend/src/routes/hrv/+page.svelte`
- Modify backend contracts/routes only if D12 requires it.
- If backend schema changes: modify generated `frontend/src/lib/api-types.ts` using `bash scripts/generate-api-types.sh`.

- [ ] Implement final top summary bar.
- [ ] Implement final history timeline.
- [ ] Implement final nightly trend chart.
- [ ] Implement selected-night panel.
- [ ] Implement distribution/weekly spread/day-of-week/correlations according to D7-D10.
- [ ] Remove obsolete guide copy and CSS.

Expected result: HRV tab content matches analyst evidence and design decisions.

### Task 7: Validation

Frontend-only path:

```bash
cd frontend && npm run check
```

Backend/schema path, only if backend changed:

```bash
cd backend && uv run ruff check
cd backend && uv run pyright app/ tests/
cd backend && uv run pytest tests/ -v
bash scripts/generate-api-types.sh
cd frontend && npm run check
```

Browser visual verification:

- `/hrv` desktop, latest state.
- `/hrv` desktop, selected historical night open.
- `/hrv` after changing trend range.
- `/hrv` mobile width.
- Empty/loading/error states if touched.

Expected result: checks pass and screenshots confirm no overlapping text, no unreadable chart axes, no hover-only date identity, and no confusing selected/latest mismatch.

## Definition Of Done

- Analyst run answers the HRV chart/surface questions and records surface verdicts.
- Design decisions D1-D12 are resolved before implementation.
- HRV tab remains frontend-display-only.
- Any new stats or aggregations are backend-derived and typed through OpenAPI.
- HRV route no longer carries legacy duplicated page setup, stat-bar markup, and broad copied CSS.
- `npm run check` passes for frontend-only work.
- Backend lint, type check, tests, and API type generation pass if backend contracts change.
- Browser screenshots have been reviewed for every modified HRV state.
