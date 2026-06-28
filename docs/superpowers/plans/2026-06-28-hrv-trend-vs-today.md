# HRV Trend-vs-Today Separation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop the HRV tab from conflating trend (averages) with today (tonight's value): make the recovery verdict delta-only, surface Garmin status as its own labelled signal, and color the historical strip by the averaged trend.

**Architecture:** Backend owns all classification (verdict and a new per-day `trend_state`); the frontend maps backend values to colors/labels and computes nothing. The chart, headline, and B2 gap handling are untouched.

**Tech Stack:** FastAPI + Pydantic (backend), SvelteKit 2 / Svelte 5 runes + Chart.js (frontend), `uv` (Python), generated OpenAPI types.

## Global Constraints

- Python via `uv` only. Backend lint `cd backend && uv run ruff check`; types `cd backend && uv run pyright app/ tests/`; tests `cd backend && uv run pytest tests/ -v`. All must pass (0 errors).
- After any backend schema change: `bash scripts/generate-api-types.sh`, commit the regenerated `frontend/src/lib/api-types.ts`, then `cd frontend && npm run check`.
- Frontend is display-only: no statistics/aggregation/derived values in Svelte — map backend values only.
- Frontend node tests: `cd frontend && node --test tests/hrv-baseline.test.mjs tests/metric-daily-api-usage.test.mjs tests/recovery-health-flags.test.mjs`.
- Visual verification (non-negotiable) via browser MCP at the desktop viewport for every changed page.
- **Do NOT** re-add the raw nightly series to the trend chart. The chart (MA + ribbon + extreme markers), the headline (tonight value + delta), and B2 gap handling are out of scope and must not change.

---

### Task 1: Recovery verdict becomes delta-only

**Files:**
- Modify: `backend/app/domains/garmin_health/domain/daily_metrics/hrv.py` (`classify_hrv_recovery`)
- Modify: `backend/app/domains/garmin_analytics/domain/insights/hrv.py:51` (`_compute_recovery` call site)
- Test: `backend/tests/domains/garmin_analytics/test_analytics_primitives.py:128-133`

**Interfaces:**
- Produces: `classify_hrv_recovery(*, delta: float | None) -> str | None` (the `status` parameter is removed). Returns `"suppressed"` (delta ≤ −10), `"below_baseline"` (≤ −5), `"elevated"` (≥ 8), `"stable"` otherwise, `None` if delta is None.

- [ ] **Step 1: Update the unit test to the delta-only contract**

In `test_analytics_primitives.py`, replace the existing block (lines ~128-133):

```python
    assert classify_hrv_recovery(delta=None) is None
    assert classify_hrv_recovery(delta=-10) == "suppressed"
    assert classify_hrv_recovery(delta=-9.9) == "below_baseline"  # was "suppressed" via the Garmin-status OR
    assert classify_hrv_recovery(delta=-5) == "below_baseline"
    assert classify_hrv_recovery(delta=8) == "elevated"
    assert classify_hrv_recovery(delta=0) == "stable"
    assert classify_hrv_recovery(delta=2.0) == "stable"  # positive delta is never "suppressed"
```

- [ ] **Step 2: Run the test, expect failure**

Run: `cd backend && uv run pytest tests/domains/garmin_analytics/test_analytics_primitives.py -k classify -v`
Expected: FAIL — current signature still requires `status`, and `delta=-9.9` still returns `"suppressed"`.

- [ ] **Step 3: Make `classify_hrv_recovery` delta-only**

In `daily_metrics/hrv.py`, replace the function:

```python
def classify_hrv_recovery(*, delta: float | None) -> str | None:
    """Classify HRV recovery from the nightly-vs-recent-baseline delta alone.

    Tonight's verdict is a "today" signal — it reflects tonight versus the recent
    baseline only. Garmin's multi-day status is a separate trend signal and is
    deliberately NOT folded in here (see docs/HRV_TAB_REFACTOR.md, "Trend vs Today").
    """
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

- [ ] **Step 4: Update the sole caller**

In `insights/hrv.py`, change the `_compute_recovery` return line:

```python
        status=classify_hrv_recovery(delta=delta),
```

- [ ] **Step 5: Run lint, types, and the affected tests**

Run: `cd backend && uv run ruff check && uv run pyright app/ tests/ && uv run pytest tests/domains/garmin_analytics/test_analytics_primitives.py tests/domains/garmin_analytics/test_hrv_service.py -v`
Expected: PASS. (`is_unfavorable_hrv_status` remains used by `heart_rate.py`, so no unused-import error. `test_builds_suppressed_recovery_and_cross_metric_insights` still passes — its delta is −15, suppressed by delta alone.)

- [ ] **Step 6: Commit**

```bash
git add backend/app/domains/garmin_health/domain/daily_metrics/hrv.py \
        backend/app/domains/garmin_analytics/domain/insights/hrv.py \
        backend/tests/domains/garmin_analytics/test_analytics_primitives.py
git commit -m "fix(hrv): recovery verdict is delta-only (decouple Garmin status)"
```

---

### Task 2: Remove the now-impossible contradiction bandaid

**Files:**
- Modify: `backend/app/domains/garmin_analytics/domain/insights/hrv_rules.py` (`recovery_status_rule`)
- Test: `backend/tests/domains/garmin_analytics/test_hrv_service.py` (delete one obsolete test)

**Interfaces:**
- Consumes: delta-only `recovery.status` from Task 1 (so a `_LOW_RECOVERY_STATUSES` status now always implies `delta < 0`).
- Produces: `recovery_status_rule` unchanged in signature; detail text is always the delta sentence when a delta exists, else the fallback.

- [ ] **Step 1: Delete the obsolete test**

In `test_hrv_service.py`, delete the whole test `test_suppressed_status_with_positive_delta_uses_fallback_text` (it manufactures an impossible state — `status="suppressed"` with `delta=+3.0` — that can no longer occur once the verdict is delta-only). Keep `test_suppressed_status_with_negative_delta_keeps_delta_sentence`.

- [ ] **Step 2: Run the kept test, expect PASS already**

Run: `cd backend && uv run pytest tests/domains/garmin_analytics/test_hrv_service.py -k "suppressed_status_with_negative_delta" -v`
Expected: PASS (the negative-delta path is unchanged).

- [ ] **Step 3: Simplify `recovery_status_rule`**

In `hrv_rules.py`, replace the body of `recovery_status_rule` (drop the `delta >= 0` special case):

```python
def recovery_status_rule(ctx: InsightContext) -> HrvInsight | None:
    """Describe the selected day's HRV level versus its recent baseline."""
    status = ctx.recovery.status or ""
    message = _RECOVERY_STATUS_MESSAGES.get(status)
    if message is None:
        return None
    level, title, fallback_detail = message
    delta = ctx.recovery.delta_nightly_from_baseline
    # The verdict is delta-only, so a below-type status always has a negative delta —
    # the old status-vs-delta contradiction can no longer arise.
    detail = (
        f"Nightly HRV is {delta:+.1f} ms versus the prior 7-day baseline."
        if delta is not None
        else fallback_detail
    )
    return HrvInsight(level=level, title=title, detail=detail)
```

- [ ] **Step 4: Run lint, types, full insight tests**

Run: `cd backend && uv run ruff check && uv run pyright app/ tests/ && uv run pytest tests/domains/garmin_analytics/test_hrv_service.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/domains/garmin_analytics/domain/insights/hrv_rules.py \
        backend/tests/domains/garmin_analytics/test_hrv_service.py
git commit -m "refactor(hrv): drop obsolete status-vs-delta contradiction bandaid"
```

---

### Task 3: Add `trend_state` to the nightly trend (backend)

**Files:**
- Modify: `backend/app/domains/garmin_analytics/contracts/analysis.py` (`NightlyHrvTrendPoint`)
- Modify: `backend/app/domains/garmin_analytics/domain/analysis/hrv.py` (`compute_nightly_hrv_trend`)
- Test: `backend/tests/domains/garmin_analytics/test_trailing_band.py`
- Regenerate: `frontend/src/lib/api-types.ts`

**Interfaces:**
- Produces: `NightlyHrvTrendPoint.trend_state: str | None` with values `"below" | "within" | "above"` (None during warmup/gaps), classifying `ma7` against `band_low`/`band_high`.

- [ ] **Step 1: Write the failing test**

In `test_trailing_band.py`, add:

```python
def test_nightly_trend_state_classifies_ma_against_band(tmp_db):
    """trend_state colors the historical strip by the averaged trend: it classifies the
    7-day MA against the trailing typical-range band (below / within / above), and is None
    for warmup/gap points."""
    from datetime import date, timedelta

    start = date(2026, 4, 1)
    # 30 nights so later points have a real band; mostly ~60 ms, then a sustained drop.
    for i in range(25):
        d = (start + timedelta(days=i)).isoformat()
        _insert_metric(_make_daily_metric(date=d, nightly_avg=60.0 + (i % 4)))
    for i in range(25, 35):
        d = (start + timedelta(days=i)).isoformat()
        _insert_metric(_make_daily_metric(date=d, nightly_avg=35.0))  # sustained low -> MA below band

    repo = SqliteBiometricRepository()
    trend = {p.date: p for p in load_hrv_analysis(repo, baseline=30).nightly_trend}

    # Warmup: first point has no band -> no trend_state.
    assert trend[start.isoformat()].trend_state is None
    # After a sustained drop, the MA sits below the trailing band.
    assert trend[(start + timedelta(days=34)).isoformat()].trend_state == "below"
    # Every classified value is one of the allowed states.
    assert {p.trend_state for p in trend.values()} <= {None, "below", "within", "above"}
```

- [ ] **Step 2: Run it, expect failure**

Run: `cd backend && uv run pytest tests/domains/garmin_analytics/test_trailing_band.py -k trend_state -v`
Expected: FAIL — `NightlyHrvTrendPoint` has no `trend_state` attribute.

- [ ] **Step 3: Add the contract field**

In `contracts/analysis.py`, add to `NightlyHrvTrendPoint` (after `is_extreme`):

```python
    trend_state: str | None = None  # "below" | "within" | "above" of the typical-range band
```

- [ ] **Step 4: Classify trend_state in the backend**

In `domain/analysis/hrv.py`, add a helper above `compute_nightly_hrv_trend`:

```python
def _trend_state(
    ma7: float | None, band_low: float | None, band_high: float | None
) -> str | None:
    """Where the 7-day MA sits relative to the trailing typical-range band.

    The historical strip colors by this (the averaged trend), not by a single night's
    status — a single night is noise. None during warmup/gaps (no band or no MA).
    """
    if ma7 is None or band_low is None or band_high is None:
        return None
    if ma7 < band_low:
        return "below"
    if ma7 > band_high:
        return "above"
    return "within"
```

Then in `compute_nightly_hrv_trend`, set it on the real-night point (the `else` branch that builds the populated `NightlyHrvTrendPoint`):

```python
            points_by_date[m.date] = NightlyHrvTrendPoint(
                date=m.date,
                nightly_avg=nightly_values[i],
                ma7=ma7_values[i],
                band_low=band[i].band_low,
                band_high=band[i].band_high,
                z=band[i].z,
                is_extreme=band[i].is_extreme,
                trend_state=_trend_state(ma7_values[i], band[i].band_low, band[i].band_high),
            )
```

(Gap points keep the default `trend_state=None`.)

- [ ] **Step 5: Run the test + lint/types**

Run: `cd backend && uv run ruff check && uv run pyright app/ tests/ && uv run pytest tests/domains/garmin_analytics/test_trailing_band.py -v`
Expected: PASS.

- [ ] **Step 6: Regenerate API types**

Run: `bash scripts/generate-api-types.sh && grep -n "trend_state" frontend/src/lib/api-types.ts`
Expected: `trend_state` appears in the generated `NightlyHrvTrendPoint` schema.

- [ ] **Step 7: Commit**

```bash
git add backend/app/domains/garmin_analytics/contracts/analysis.py \
        backend/app/domains/garmin_analytics/domain/analysis/hrv.py \
        backend/tests/domains/garmin_analytics/test_trailing_band.py \
        frontend/src/lib/api-types.ts
git commit -m "feat(hrv): add trend_state (MA vs typical-range band) to nightly trend"
```

---

### Task 4: Color the historical strip by trend (frontend)

**Files:**
- Modify: `frontend/src/routes/hrv/+page.svelte` (strip color map + legend)
- Test: `frontend/tests/hrv-baseline.test.mjs`

**Interfaces:**
- Consumes: `analysis.nightly_trend[].trend_state` from Task 3.

- [ ] **Step 1: Update the source-text test for the trend-colored strip**

In `hrv-baseline.test.mjs`, add a new test (keep the existing ones):

```javascript
test('hrv history strip is colored by the averaged trend, not per-night status', () => {
	const page = readFileSync(join('src/routes', 'hrv', '+page.svelte'), 'utf8');
	// Strip colors come from the trend_state of the nightly trend (averages), not Garmin per-night status.
	assert.match(page, /TREND_STATE_COLORS/);
	assert.match(page, /nightly_trend[\s\S]*?trend_state/);
	// The day cell color is driven by dayStatusMap built from trend_state.
	assert.match(page, /dayStatusMap\.get\(day\) \?\? UNKNOWN_STATUS_COLOR/);
});
```

- [ ] **Step 2: Run it, expect failure**

Run: `cd frontend && node --test tests/hrv-baseline.test.mjs`
Expected: FAIL — `TREND_STATE_COLORS` not present.

- [ ] **Step 3: Replace the strip color map, `dayStatusMap`, and legend**

In `+page.svelte`, replace the `HRV_STATUS_COLORS` / `dayStatusMap` / `statusLegend` block (the History strip colors section) with the trend-based version. Keep `statusKey`, `HRV_STATUS_COLORS`, and `UNKNOWN_STATUS_COLOR` — `HRV_STATUS_COLORS`/`statusKey` are reused by the Garmin chip in Task 5.

```svelte
	// ── History strip colors: by the AVERAGED TREND (ma7 vs typical-range band), not
	// per-night status — a single night is noise. trend_state comes from the backend. ──
	const TREND_STATE_COLORS: Record<string, string> = {
		below: COLORS.heartRate,          // red — trend below the typical range
		within: COLORS.heartRateResting,  // green — within the typical range
		above: COLORS.respiration         // teal — above the typical range
	};
	const TREND_STATE_LABELS: Record<string, string> = {
		below: 'Below typical',
		within: 'Within typical',
		above: 'Above typical'
	};

	let dayStatusMap = $derived.by(() => {
		const map = new Map<string, string>();
		for (const p of analysis?.nightly_trend ?? []) {
			map.set(p.date, (p.trend_state && TREND_STATE_COLORS[p.trend_state]) || UNKNOWN_STATUS_COLOR);
		}
		return map;
	});

	// Legend entries derived from the trend states actually present, in palette order.
	let statusLegend = $derived.by(() => {
		const present = new Set<string>();
		for (const p of analysis?.nightly_trend ?? []) {
			if (p.trend_state) present.add(p.trend_state);
		}
		return Object.keys(TREND_STATE_COLORS)
			.filter((s) => present.has(s))
			.map((s) => ({ label: TREND_STATE_LABELS[s], color: TREND_STATE_COLORS[s] }));
	});
```

Keep the existing legend markup (`{#each statusLegend as { label, color }}`) and the existing `HRV_STATUS_COLORS` / `statusKey` / `UNKNOWN_STATUS_COLOR` declarations (used by Task 5). The day-cell `style="background: {dayStatusMap.get(day) ?? UNKNOWN_STATUS_COLOR};"` is unchanged.

- [ ] **Step 4: Run node test + svelte-check**

Run: `cd frontend && node --test tests/hrv-baseline.test.mjs && npm run check`
Expected: PASS, 0 errors.

- [ ] **Step 5: Visual verification**

Start the app if not running (`cd backend && uv run uvicorn app.main:app --port 8000` and `cd frontend && npm run dev`). With browser MCP, open `http://localhost:5173/hrv`, set Show=All, screenshot the history strip. Confirm: the strip reads as a smooth direction band (long green stretches, red where the trend dipped), NOT per-night flicker; the legend reads "Below/Within/Above typical" with matching dot colors.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/routes/hrv/+page.svelte frontend/tests/hrv-baseline.test.mjs
git commit -m "feat(hrv): color history strip by averaged trend, not per-night status"
```

---

### Task 5: Garmin status as its own labelled chip (frontend)

**Files:**
- Modify: `frontend/src/routes/hrv/+page.svelte` (chip in the night-detail header; chip near the Tonight headline)
- Test: `frontend/tests/hrv-baseline.test.mjs`

**Interfaces:**
- Consumes: `historicalDayStats.status` (selected night) and `latestDayStats.status` (tonight) — Garmin's per-day HRV status, already on the response.

- [ ] **Step 1: Add the source-text test**

In `hrv-baseline.test.mjs`, add:

```javascript
test('hrv surfaces Garmin status as its own labelled chip, separate from the verdict', () => {
	const page = readFileSync(join('src/routes', 'hrv', '+page.svelte'), 'utf8');
	assert.match(page, /class="garmin-chip"/);
	assert.match(page, /Garmin:/);
	// The chip reads the raw Garmin per-day status, not the recovery verdict.
	assert.match(page, /statusKey\((historicalDayStats|latestDayStats)\?\.status\)/);
});
```

- [ ] **Step 2: Run it, expect failure**

Run: `cd frontend && node --test tests/hrv-baseline.test.mjs`
Expected: FAIL — no `garmin-chip`.

- [ ] **Step 3: Add the chip markup**

Add a reusable snippet near the top of the markup (after `<svelte:head>`), then use it in both places:

```svelte
{#snippet garminChip(status: string | null | undefined)}
	{@const key = statusKey(status)}
	{#if key}
		<span class="garmin-chip" title="Garmin's own multi-day HRV status — a separate signal from tonight's recovery">
			<i class="garmin-dot" style="background: {HRV_STATUS_COLORS[key] ?? UNKNOWN_STATUS_COLOR};"></i>
			Garmin: {key}
		</span>
	{/if}
{/snippet}
```

In the night-detail header (the `.history-detail-header` block, next to the date), render `{@render garminChip(historicalDayStats?.status)}`. In the Tonight headline area (after the `.stat-bar`, before the insight line), render `{@render garminChip(latestDayStats?.status)}`.

- [ ] **Step 4: Add chip styles**

In the `<style>` block:

```css
	.garmin-chip {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		font-family: 'DM Mono', monospace;
		font-size: 10px;
		text-transform: uppercase;
		letter-spacing: 1px;
		color: #8a9baa;
	}
	.garmin-dot {
		width: 7px;
		height: 7px;
		border-radius: 50%;
		display: inline-block;
	}
```

- [ ] **Step 5: Run node test + svelte-check**

Run: `cd frontend && node --test tests/hrv-baseline.test.mjs && npm run check`
Expected: PASS, 0 errors.

- [ ] **Step 6: Visual verification**

With browser MCP at `http://localhost:5173/hrv`: confirm a "Garmin: Unbalanced/Low/Balanced" chip shows near Tonight and in a selected night's detail, visually distinct from the recovery insight text, and that a positive-delta night with Garmin Low shows the chip without the headline/insight calling tonight "suppressed."

- [ ] **Step 7: Commit**

```bash
git add frontend/src/routes/hrv/+page.svelte frontend/tests/hrv-baseline.test.mjs
git commit -m "feat(hrv): surface Garmin status as its own labelled chip"
```

---

### Task 6: Document the trend-vs-today principle

**Files:**
- Modify: `docs/HRV_TAB_REFACTOR.md`

- [ ] **Step 1: Add the principle section**

Add a short, prominent section near the top of `docs/HRV_TAB_REFACTOR.md` (after the intro), verbatim intent:

```markdown
## Trend vs Today — never conflate

The tab shows two distinct signals that must never be merged:

- **Trend / direction** — the 7-day moving average, the typical-range ribbon, and the
  history strip (colored by the averaged trend: where the MA sits vs the typical-range
  band). Built from averages; a single night barely moves it.
- **Today** — tonight's actual value and its delta vs the recent baseline; and, for a
  selected past night, that night's own z. A single, un-smoothed reading.

Rules:
1. Tonight's recovery verdict is decided by the nightly-vs-recent-baseline delta **only**.
2. Garmin's own HRV status is a separate, labelled signal (its own chip) — never folded
   into the verdict and never the strip color.
3. The history strip is colored by the averaged trend, never by a single night's status
   (a single night flips ~63% of consecutive nights — that is noise, not signal).
```

- [ ] **Step 2: Reconcile the rest of the doc**

Update the "Under the hood" and any "what shipped" lines so the recovery verdict is described as delta-only and the strip as trend-colored (remove any wording implying Garmin status drives the verdict or the strip).

- [ ] **Step 3: Commit**

```bash
git add docs/HRV_TAB_REFACTOR.md
git commit -m "docs(hrv): document the trend-vs-today principle"
```

---

## Self-Review

- **Spec coverage:** verdict delta-only (Task 1) ✓; Garmin status as separate chip (Task 5) ✓; strip by averaged trend / `trend_state` (Tasks 3-4) ✓; obsolete bandaid removed (Task 2) ✓; docs (Task 6) ✓; `stable_recovery_rule` kept (no task — intentional, matches the decided spec) ✓; out-of-scope items (chart/headline/B2/nightly) have no task ✓.
- **Placeholder scan:** none — every code step has complete code.
- **Type consistency:** `trend_state: str | None` ("below"/"within"/"above"/None) is defined in Task 3 and consumed identically in Task 4; `classify_hrv_recovery(*, delta)` defined in Task 1 and called in Task 1 Step 4; `statusKey`/`HRV_STATUS_COLORS`/`UNKNOWN_STATUS_COLOR` are preserved in Task 4 and reused in Task 5.

---

## Post-review refinements (2026-06-28)

After visual review, Task 4's strip received three corrections (commit `3577163`) — the code blocks
above show the as-planned version; the shipped version differs as follows:

- Trend colors changed to amber / green / blue (`below` `COLORS.stress`, `within`
  `COLORS.heartRateResting`, `above` `COLORS.spo2`) — green/teal were indistinguishable.
- A no-reading night is colored by the surrounding trend (its `trend_state` is carried on the
  all-null gap point in `compute_nightly_hrv_trend`) so the strip stays continuous; the chart still
  breaks. Gray is limited to warm-up and labelled "Building baseline" in the legend.
- The `.day-strip-legend` is `position: sticky; left: 0` so it stays visible during horizontal scroll.
