# Frontend Metric Pages — DRY-up & Improve (tab by tab)

**Goal:** Remove the ~1,500 lines of near-identical code across the 8 metric *detail* pages by
extending the abstractions that already exist, and improve each tab's UX in the same pass (the
hug-the-data axis, the anti-card lens). Done one tab per increment, behavior-preserving.

**Scope:** `frontend/src/routes/{heart-rate,hrv,sleep,stress,body-battery,respiration,skin-temp,pulse-ox}/+page.svelte`
and the shared `frontend/src/lib/` helpers/components they use. The overview
(`frontend/src/routes/+page.svelte`) is not the main target because its first slate is already
rebuilt, but small access/status additions are allowed when they are backed by existing data or a
narrow dashboard contract. Backend contract changes should happen only when a tab or status lane
genuinely needs them; do not pre-build speculative fields.

**Status:** active frontend direction as of 2026-06-13. Parts 1 & 2 of the broader DRY-up
(backend dashboard helpers + overview formatters) are already done (commit `7dc90f5`). The current
sequence is: central dashboard first slate complete, then generic metric detail pages DRY-up and
visual improvement, with activity/workout ingestion deferred until those dashboards are stable.

---

## Where things stand (what I noticed)

There is a clean split across the 8 pages — this is the single most useful fact for planning:

- **6 already-modern pages** — `sleep`, `stress`, `body-battery`, `respiration`, `skin-temp`,
  `pulse-ox` — use the good pattern: `PageState`, `MetricPageHeader`, `DateSelector`, `StatCard`,
  `ChartCard`, `createDateLoader`, and (for the last three) a partial chart-config helper. These
  are 140–340 lines each and mostly clean.
- **2 legacy holdouts** — `heart-rate` (~1,430 lines) and `hrv` (~1,490 lines) — use the *old*
  pattern: inline custom stat-bars, manual `onDateChange` state machines, and **~400 lines of CSS
  duplicated between just these two files**. They carry the bulk of the mess.

No old-dashboard contract debris remains in any metric page (no `readiness`/`sparklines`/`vitals`).
The HRV tab's `overview.correlations` usage is intentional and **stays** (it's the cross-metric
scatter retained in the contract).

The duplication, by magnitude (from a full line-by-line survey):

| Pattern | Where | ~Lines | The fix |
|---|---|---:|---|
| Chart-config boilerplate (~30 configs; scales/plugins/tooltip/options 100% identical) | all 8 | ~900 | extend the chart-helper into builders |
| Page-setup (state + fetch + onMount + onDateChange) | all 8; manual on 2 | ~50/page | adopt `createDateLoader` on the 2 legacy pages |
| Custom stat-bar markup + CSS | heart-rate, hrv | ~80 | a `<StatBar>`/`<StatItem>` (or reuse `StatCard`) |
| Duplicated `.section-*/.stat-*/.day-*/.card-*/.info-hint` CSS | heart-rate, hrv | ~400 | one shared place / shared components |

Feasible consolidation: ~630–700 lines.

## File organization (do this *with* the tab work, not before)

Separate from the line-level DRY above, `src/lib` is flat and the chart layer is scattered.
The key fact that decides *when* to fix it: **the chart pieces and the metric-page component
family are imported by the same 8 metric pages this plan rewrites.** So their import churn lands
on exactly these files — doing a standalone "move + re-import" pass now would touch all 8 pages
twice and lock in a folder shape before the DRY reveals the right abstractions. Fold the
reorganization into this work instead, as an opening structural step per tab batch:

- **Consolidate the chart module.** Today: `components/charts/` holds only `ChartCanvas`, while
  `BarChart`/`LineChart`/`ScatterChart`/`PolarAreaChart`/`ChartCard` sit flat in `components/`,
  and the chart helpers `chart-options.ts`/`chart-scale.ts`/`chart-setup.ts` sit at `lib/` root.
  Move the chart components into `components/charts/` (joining `ChartCanvas`) and the chart
  helpers into a `lib/charts/` (or co-locate). Charts are a *stable* concept — a `LineChart`
  adapter does not change shape because of the page DRY — so this grouping is safe; the only
  reason to defer it is to pay the 8-page import churn once, here. If the chart-config-builder
  extraction (Part A) produces a new builder, it lives in this module too.
- **Group the metric-page component family.** `MetricPageHeader`, `MetricDefinition`, `StatCard`,
  `ChartCard`, `DateSelector`, `TrendRangePicker`, `PageState` → a `components/metric-page/`
  module. Unlike charts, the *right* shape here is whatever the DRY produces (e.g. a `StatBar`
  extraction, a shared page scaffold), so group these as the abstractions settle, not up front.
- **Independent micro-move (any time, not blocked on this plan):** `recovery-format.ts` is used
  only by the recovery components, not the metric pages — it can move into `components/recovery/`
  or a `lib/recovery/` whenever convenient, with zero blast radius.
- **Leave flat:** the primitives `format.ts`/`date.ts`/`colors.ts`/`utils.ts`/`markdown.ts` —
  grouping them is low-value churn. `lib/dashboard/` already exists (the overview refresh bus).

(Captured 2026-06-14 while refactoring the overview into axis sections, which raised the same
flat-`src/lib` observation.)

## Guiding principles (do not violate)

1. **Extend, don't fork.** The 6 modern pages already prove the target pattern. Reuse
   `createDateLoader`, `PageState`, `MetricPageHeader`, `StatCard`, `ChartCard`, and the existing
   chart helper. Do **not** invent a parallel `useMetricPage` mega-composable or a second chart
   factory — that *adds* duplication.
2. **Behavior-preserving per tab.** Each tab must render **screenshot-identical** before/after
   (except where we deliberately apply the axis fix, which is a visible improvement — call those
   out explicitly). `npm run check` clean. One tab per commit.
3. **Improve while we're in there.** Each tab gets the hug-the-data axis (via the shared builder)
   and a quick anti-card review (is a stat-card grid the right form here, or an aligned table?).
   Keep UX changes small and screenshot-reviewed.
4. **No backend change unless required.** If a tab needs data it doesn't have, decide then —
   don't pre-build contract fields.
5. **No activity/workout ingestion in this phase.** Load, strain, and progress remain design docs
   until the generic Garmin metric dashboards are DRY and visually stable.
6. **Central dashboard access is allowed, not central-dashboard expansion.** Keep overview changes
   to drill-down links, historical/context status, or experiment/status entry points that are
   already supported by existing data.

---

## Part A — Shared chart builders (highest impact, ~250–300 lines)

The ~30 chart configs share identical `responsive/maintainAspectRatio/interaction/plugins/scales`
boilerplate; only data, color, and axis label vary. The 3 simplest pages already call a partial
helper — **extend that helper** (don't start a new file) into a small, typed set:

- `buildLineConfig({ labels, datasets, color, yTitle, yOptions?, onClick? })`
- `buildBoxplotConfig({ boxes, color, yTitle })` — the Min/Q1/Median/Q3/Max 5-dataset pattern,
  currently copy-pasted across 5 pages.
- `buildIntradayConfig({ labels, values, color, yTitle })` — single series, time axis.
- `buildDistributionBarConfig({ bins, color, highlighted? })` — histogram bars.

**Bake in two project rules so every chart inherits them for free:**
- the **hug-the-data axis** from `lib/chart-scale.ts` (`tightScale`) on line/scatter y-axes — this
  fixes the flattening problem across *all* metric charts in one move;
- the dark theme (`DARK_GRID/DARK_TICK/chartTooltip`) — already shared, just centralize its
  application in the builder.

Migrate in order of ease: respiration → pulse-ox → skin-temp (already half-there) → sleep →
stress → body-battery → heart-rate → hrv. Each migration is mechanical and screenshot-verified.

## Part B — Modernize the two legacy pages (biggest readability win)

Bring `heart-rate` and `hrv` onto the pattern the other six already use:

- Replace the manual `onDateChange` state machine with `createDateLoader` (or a small multi-fetch
  variant if a page needs insights+intraday+distribution in parallel — extend `createDateLoader`,
  don't fork it).
- Wrap the page in `PageState`; use `MetricPageHeader` + `DateSelector` like the others.
- Replace the inline stat-bar markup with `StatCard` (or a thin `<StatBar>` if the delta/recovery
  pill doesn't fit `StatCard`).
- Delete the ~400 lines of duplicated `.section-*/.stat-*/.day-*/.history-*/.card-*/.info-hint`
  CSS — move anything still needed into the shared component(s) or one small CSS module; keep only
  the genuinely page-specific bits (`.zone-inline*` for HR, `.trajectory-*`/`.corr-*` for HRV).

This is the largest single cleanup; do it after Part A so the charts are already on the builder.

## Part C — Shared stat/section components (tidy-up)

Whatever stat/section markup is *still* inline after Part B (and not a fit for `StatCard`) becomes
a tiny shared component (`<StatBar>` + `<StatItem>`), with its CSS scoped to the component. This
removes the last copy-paste between heart-rate and hrv and gives the other six a consistent option.

---

## Tab-by-tab sequence

Each tab is one increment: migrate its charts to the builder (Part A), modernize if legacy
(Part B), apply the axis fix + a quick anti-card check, `npm run check`, browser-screenshot
before/after, commit.

1. **respiration** — smallest, already half-modern. Establishes the extended chart builder + the
   baked-in tight axis. The reference migration.
2. **pulse-ox**, **skin-temp** — also small/half-modern; confirm the builder generalizes (incl. the
   SpO₂ "days below 90%" and skin-temp diverging cases).
3. **sleep**, **stress**, **body-battery** — modern pattern, more charts (trend/boxplot/intraday).
   Route all through the builder; check the boxplot helper covers them.
4. **heart-rate** — first legacy page: Part A charts, then Part B modernization (createDateLoader,
   PageState, StatCard, CSS purge), then Part C for the residual stat-bar. Big diff — review
   carefully.
5. **hrv** — last and richest: same as heart-rate, plus keep the `overview.correlations` scatter
   and the overnight-trajectory view intact. Verify the correlations still render.

Doing 1–3 first banks the shared builders and de-risks the heavy 4–5.

## Definition of done (per tab)

- Charts go through the shared builder; the y-axis hugs the data (no overshoot/flattening).
- No duplicated chart-config / page-setup / stat / CSS boilerplate remains on that tab.
- Uses `createDateLoader` + `PageState` + the shared components (no inline reimplementations).
- `npm run check` clean; the page renders correctly (browser-verified), with any deliberate UX
  change noted in the commit.
- One commit per tab.

## Explicit non-goals

- Do not redesign the overview (`/`) or turn it into a multi-lane training-state dashboard during
  this refactor.
- Do not remove any information a tab shows (intraday curves, distributions, sleep stages, HR
  zones, circadian profiles, the HRV correlations) — this is a *code* DRY-up + axis/UX polish, not
  a content change.
- Do not introduce a parallel composable/factory that competes with `createDateLoader` /
  `StatCard` / the chart helper.
- Do not add Garmin activity/session/workout ingestion, load/strain metrics, or progress metrics in
  this phase.
