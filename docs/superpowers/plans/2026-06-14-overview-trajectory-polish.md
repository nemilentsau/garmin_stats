# Overview Trajectory Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the noisy raw daily line on the recovery trajectory with a ±1 SD dispersion band, fix the chart axis to hug the average, delete the decorative page background, and fix the evidence table column widths and sparkline color.

**Architecture:** Backend computes a rolling 14-day sample SD of the daily recovery score and emits `band_lo`/`band_hi` (= `ma7 ± SD`) per day on the existing score series. The frontend draws those as a soft filled band, scales the y-axis from the band (not the raw extremes), and applies three contained CSS/markup fixes (background removal, table colgroup, neutral sparkline).

**Tech Stack:** Python 3.14 + FastAPI + Pydantic (backend, `uv`), numpy for the SD; SvelteKit 2 / Svelte 5 runes + Chart.js (frontend). API types flow Pydantic → OpenAPI → generated TS.

---

## File Structure

**Backend (create/modify):**
- Modify `backend/app/domains/garmin_analytics/domain/primitives/trends.py` — add `trailing_sd` rolling-SD primitive.
- Modify `backend/app/domains/garmin_analytics/domain/recovery_score/smoothing.py` — add `seeded_sd` + band window constants.
- Modify `backend/app/domains/garmin_analytics/domain/recovery_score/evidence.py` — add `band_lo`/`band_hi` to `ScorePoint`; compute them in `compute_recovery`.
- Modify `backend/app/domains/garmin_analytics/contracts/dashboard.py` — add `band_lo`/`band_hi` to `RecoveryScorePoint`.
- Modify `backend/app/domains/garmin_analytics/domain/dashboard.py` — map the new fields in `_score_series`.
- Tests: `backend/tests/domains/garmin_analytics/test_analytics_primitives.py`, `.../recovery_score/test_smoothing.py`, `.../recovery_score/test_evidence.py`.

**Frontend (modify):**
- `frontend/src/lib/api-types.ts` — regenerated (do not hand-edit).
- `frontend/src/lib/components/recovery/RecoveryTrajectory.svelte` — band + axis.
- `frontend/src/routes/+layout.svelte` — delete topo background.
- `frontend/src/lib/components/recovery/EvidenceTable.svelte` — colgroup + neutral sparkline color + wider sparkline.

---

## Task 1: Rolling-SD primitive `trailing_sd`

**Files:**
- Modify: `backend/app/domains/garmin_analytics/domain/primitives/trends.py`
- Test: `backend/tests/domains/garmin_analytics/test_analytics_primitives.py`

- [ ] **Step 1: Write the failing tests**

Add to `backend/tests/domains/garmin_analytics/test_analytics_primitives.py` (add the import to the existing `from ...primitives.trends import (...)` block if present, else a new import line):

```python
from app.domains.garmin_analytics.domain.primitives.trends import trailing_sd


def test_trailing_sd_returns_none_below_min_valid():
    # window has only 4 present values, min_valid=5 -> None
    out = trailing_sd([1.0, 2.0, 3.0, 4.0], window=14, min_valid=5)
    assert out == [None, None, None, None]


def test_trailing_sd_skips_none_inside_window():
    # present values are [2,4,6,8,10]; sample SD (ddof=1) of those
    out = trailing_sd([2.0, None, 4.0, 6.0, None, 8.0, 10.0], window=14, min_valid=5)
    import numpy as np
    expected = round(float(np.std([2.0, 4.0, 6.0, 8.0, 10.0], ddof=1)), 3)
    assert out[-1] == expected


def test_trailing_sd_constant_series_is_zero():
    out = trailing_sd([5.0] * 6, window=14, min_valid=5)
    assert out[-1] == 0.0


def test_trailing_sd_window_excludes_old_values():
    # window=3, min_valid=2: last position sees only the final 3 values
    out = trailing_sd([100.0, 1.0, 2.0, 3.0], window=3, min_valid=2)
    import numpy as np
    assert out[-1] == round(float(np.std([1.0, 2.0, 3.0], ddof=1)), 3)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/domains/garmin_analytics/test_analytics_primitives.py -k trailing_sd -v`
Expected: FAIL — `ImportError: cannot import name 'trailing_sd'`.

- [ ] **Step 3: Implement `trailing_sd`**

In `backend/app/domains/garmin_analytics/domain/primitives/trends.py`, add `import numpy as np` to the imports, and add this function after `trailing_ma7`:

```python
def trailing_sd(
    values: list[float | None],
    window: int,
    min_valid: int,
) -> list[float | None]:
    """Rolling sample standard deviation (ddof=1) over a trailing `window`.

    None values inside a window are skipped. Returns None at any position whose
    window holds fewer than `min_valid` non-None values, so a thin left edge or a
    sparse stretch produces no spurious spread. Mirrors the None-skipping policy of
    `trailing_ma7`; used to size the recovery trajectory's dispersion band.
    """
    result: list[float | None] = []
    for i in range(len(values)):
        window_start = max(0, i - (window - 1))
        present = [v for v in values[window_start : i + 1] if v is not None]
        if len(present) < min_valid:
            result.append(None)
        else:
            result.append(round(float(np.std(present, ddof=1)), 3))
    return result
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/domains/garmin_analytics/test_analytics_primitives.py -k trailing_sd -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/app/domains/garmin_analytics/domain/primitives/trends.py backend/tests/domains/garmin_analytics/test_analytics_primitives.py
git commit -m "Add trailing_sd rolling sample-SD primitive"
```

---

## Task 2: Seeded SD wrapper `seeded_sd`

**Files:**
- Modify: `backend/app/domains/garmin_analytics/domain/recovery_score/smoothing.py`
- Test: `backend/tests/domains/garmin_analytics/recovery_score/test_smoothing.py`

- [ ] **Step 1: Write the failing tests**

Add to `backend/tests/domains/garmin_analytics/recovery_score/test_smoothing.py`:

```python
from app.domains.garmin_analytics.domain.recovery_score.smoothing import (
    BAND_MIN_VALID,
    BAND_WINDOW,
    seeded_sd,
)


def test_seeded_sd_returns_only_display_portion():
    seed = [0.0] * BAND_WINDOW  # plenty of prior days
    display = [1.0, 2.0, 3.0]
    assert len(seeded_sd(seed, display)) == 3


def test_seeded_sd_uses_seed_to_fill_left_edge():
    # First display point sees its 13 seed days + itself -> a real SD, not None.
    seed = [1.0] * (BAND_WINDOW - 1)
    display = [2.0]
    out = seeded_sd(seed, display)
    assert out[0] is not None


def test_seeded_sd_none_when_too_few_inputs():
    # No seed, single display value -> below BAND_MIN_VALID -> None.
    assert seeded_sd([], [5.0])[0] is None
    assert BAND_MIN_VALID == 5
    assert BAND_WINDOW == 14
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/domains/garmin_analytics/recovery_score/test_smoothing.py -k seeded_sd -v`
Expected: FAIL — `ImportError: cannot import name 'seeded_sd'`.

- [ ] **Step 3: Implement `seeded_sd`**

In `backend/app/domains/garmin_analytics/domain/recovery_score/smoothing.py`, add the import and the wrapper. Update the top import block to include `trailing_sd`:

```python
from app.domains.garmin_analytics.domain.primitives.trends import (
    trailing_ma7,
    trailing_sd,
)
```

Then add below `seeded_ma7`:

```python
BAND_WINDOW = 14
BAND_SEED_DAYS = BAND_WINDOW - 1
BAND_MIN_VALID = 5


def seeded_sd(
    seed: Sequence[float | None],
    display: Sequence[float | None],
) -> list[float | None]:
    """Trailing 14-day sample SD over seed + display, returning the display portion.

    The band width uses a longer window than the 7-day average center: a 14-day SD
    is a far steadier second-moment estimate, so the dispersion band reads as a calm
    ribbon instead of breathing day to day. The seed only fills the left edge and is
    dropped from the result, exactly like `seeded_ma7`.
    """
    return trailing_sd(
        list(seed) + list(display), BAND_WINDOW, BAND_MIN_VALID
    )[len(seed):]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/domains/garmin_analytics/recovery_score/test_smoothing.py -k seeded_sd -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/app/domains/garmin_analytics/domain/recovery_score/smoothing.py backend/tests/domains/garmin_analytics/recovery_score/test_smoothing.py
git commit -m "Add seeded_sd 14-day dispersion-band wrapper"
```

---

## Task 3: Emit `band_lo`/`band_hi` on the score series

**Files:**
- Modify: `backend/app/domains/garmin_analytics/domain/recovery_score/evidence.py` (`ScorePoint` dataclass ~lines 91-97; `compute_recovery` ~lines 193-208)
- Test: `backend/tests/domains/garmin_analytics/recovery_score/test_evidence.py`

- [ ] **Step 1: Write the failing tests**

Add to `backend/tests/domains/garmin_analytics/recovery_score/test_evidence.py` (reuse the existing `_metric`, `_baseline_series`, `_compute` helpers in that file):

```python
def test_score_points_carry_a_symmetric_dispersion_band():
    # Vary one input day to day so the rolling SD is > 0.
    metrics = []
    for i, day in enumerate(range(1, 41)):
        metrics.append(_metric(f"2025-06-{day:02d}", hr_avg=67.0 + (i % 5)))
    result = _compute(metrics)
    banded = [
        p for p in result.score_series
        if p.ma7 is not None and p.band_lo is not None and p.band_hi is not None
    ]
    assert banded, "expected at least one fully-banded score point"
    for p in banded:
        # band is ma7 +/- sd: symmetric around ma7, and non-degenerate here.
        assert abs((p.band_hi - p.ma7) - (p.ma7 - p.band_lo)) < 1e-6
        assert p.band_hi >= p.ma7 >= p.band_lo


def test_band_is_none_when_ma7_is_none():
    # A single day cannot form a 7-day MA seed nor a 5-point SD window.
    result = _compute(_baseline_series(days=1))
    first = result.score_series[0]
    if first.ma7 is None:
        assert first.band_lo is None and first.band_hi is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/domains/garmin_analytics/recovery_score/test_evidence.py -k dispersion_band -v`
Expected: FAIL — `AttributeError: 'ScorePoint' object has no attribute 'band_lo'`.

- [ ] **Step 3: Add band fields to `ScorePoint`**

In `backend/app/domains/garmin_analytics/domain/recovery_score/evidence.py`, extend the `ScorePoint` dataclass:

```python
@dataclass(frozen=True, slots=True)
class ScorePoint:
    date: str
    raw: float | None
    ma7: float | None
    band_lo: float | None
    band_hi: float | None
    baseline_lo: float
    baseline_hi: float
```

- [ ] **Step 4: Compute the band in `compute_recovery`**

Update the import of smoothing symbols near the top of the file:

```python
from .smoothing import SEED_DAYS, seeded_ma7, seeded_sd
from .smoothing import BAND_SEED_DAYS
```

Add this module-level helper (e.g. just above `compute_recovery`):

```python
def _band_edge(center: float | None, spread: float | None, sign: int) -> float | None:
    """ma7 +/- sd, or None if either is missing for this day."""
    if center is None or spread is None:
        return None
    return center + sign * spread
```

In `compute_recovery`, replace the seed/ma7 block and the `score_series` construction. The current code is:

```python
    display_start = max(0, n - _DISPLAY_DAYS)
    seed_start = max(0, display_start - SEED_DAYS)
    seed = raw_scores[seed_start:display_start]
    display = raw_scores[display_start:]
    ma7 = seeded_ma7(seed, display)

    score_series = [
        ScorePoint(
            date=metrics[display_start + offset].date,
            raw=display[offset],
            ma7=ma7[offset],
            baseline_lo=-_BAND,
            baseline_hi=_BAND,
        )
        for offset in range(len(display))
    ]
```

Replace it with (ma7 keeps its own 6-day seed so its output is unchanged; the SD gets its own wider 13-day seed):

```python
    display_start = max(0, n - _DISPLAY_DAYS)
    ma_seed = raw_scores[max(0, display_start - SEED_DAYS):display_start]
    sd_seed = raw_scores[max(0, display_start - BAND_SEED_DAYS):display_start]
    display = raw_scores[display_start:]
    ma7 = seeded_ma7(ma_seed, display)
    sd = seeded_sd(sd_seed, display)

    score_series = [
        ScorePoint(
            date=metrics[display_start + offset].date,
            raw=display[offset],
            ma7=ma7[offset],
            band_lo=_band_edge(ma7[offset], sd[offset], -1),
            band_hi=_band_edge(ma7[offset], sd[offset], +1),
            baseline_lo=-_BAND,
            baseline_hi=_BAND,
        )
        for offset in range(len(display))
    ]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/domains/garmin_analytics/recovery_score/test_evidence.py -v`
Expected: PASS (existing evidence tests + the 2 new ones).

- [ ] **Step 6: Commit**

```bash
git add backend/app/domains/garmin_analytics/domain/recovery_score/evidence.py backend/tests/domains/garmin_analytics/recovery_score/test_evidence.py
git commit -m "Emit ma7 +/- 14d SD dispersion band on score series"
```

---

## Task 4: Surface band on the API contract + map it

**Files:**
- Modify: `backend/app/domains/garmin_analytics/contracts/dashboard.py` (`RecoveryScorePoint`, ~lines 28-35)
- Modify: `backend/app/domains/garmin_analytics/domain/dashboard.py` (`_score_series`, ~lines 82-92)
- Test: `backend/tests/domains/garmin_analytics/test_dashboard_service.py`

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/domains/garmin_analytics/test_dashboard_service.py` (reuse whatever metric-builder / `compute_dashboard_overview` entrypoint the file already imports; if it builds metrics via a local helper, reuse it):

```python
def test_overview_score_points_expose_band_fields():
    metrics = _metrics_for_overview()  # existing helper in this test module
    overview = compute_dashboard_overview(metrics)
    assert overview.score, "expected a non-empty score series"
    # The band fields exist and, where present, bracket ma7.
    for p in overview.score:
        assert hasattr(p, "band_lo") and hasattr(p, "band_hi")
        if p.ma7 is not None and p.band_lo is not None and p.band_hi is not None:
            assert p.band_lo <= p.ma7 <= p.band_hi
```

> If the test module names its builder/entrypoint differently, substitute the real
> names — grep the file for `compute_dashboard_overview` and the existing metric helper.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/domains/garmin_analytics/test_dashboard_service.py -k band_fields -v`
Expected: FAIL — `AttributeError`/validation: `RecoveryScorePoint` has no `band_lo`.

- [ ] **Step 3: Add fields to the contract**

In `backend/app/domains/garmin_analytics/contracts/dashboard.py`, extend `RecoveryScorePoint`:

```python
class RecoveryScorePoint(DefaultsRequired):
    """One day of the recovery trajectory: raw score, seeded MA7, dispersion band, and typical band."""

    date: str
    raw: float | None = None
    ma7: float | None = None
    band_lo: float | None = None
    band_hi: float | None = None
    baseline_lo: float
    baseline_hi: float
```

- [ ] **Step 4: Map the fields**

In `backend/app/domains/garmin_analytics/domain/dashboard.py`, in `_score_series`, add the two fields to the `RecoveryScorePoint(...)` construction (alongside `raw=_round_opt(point.raw, 3)`):

```python
            band_lo=_round_opt(point.band_lo, 3),
            band_hi=_round_opt(point.band_hi, 3),
```

- [ ] **Step 5: Run test + full backend gate**

Run: `cd backend && uv run pytest tests/domains/garmin_analytics/test_dashboard_service.py -k band_fields -v`
Expected: PASS.

Then the full gate:
Run: `cd backend && uv run ruff check && uv run pyright app/ tests/ && uv run pytest tests/ -v`
Expected: 0 lint errors, 0 type errors, all tests pass.

- [ ] **Step 6: Regenerate API types**

Run: `bash scripts/generate-api-types.sh`
Then confirm the band fields appear:
Run: `grep -n "band_lo\|band_hi" frontend/src/lib/api-types.ts`
Expected: the generated `RecoveryScorePoint` type now includes `band_lo` and `band_hi`.

- [ ] **Step 7: Commit**

```bash
git add backend/app/domains/garmin_analytics/contracts/dashboard.py backend/app/domains/garmin_analytics/domain/dashboard.py backend/tests/domains/garmin_analytics/test_dashboard_service.py frontend/src/lib/api-types.ts
git commit -m "Expose dispersion band on dashboard overview contract"
```

---

## Task 5: Render the band + fix the axis (frontend)

**Files:**
- Modify: `frontend/src/lib/components/recovery/RecoveryTrajectory.svelte`

- [ ] **Step 1: Replace the raw line with a band + scale the axis from the band**

In `RecoveryTrajectory.svelte`:

(a) Change the y-scale source. Replace line 40:

```js
	const yScale = $derived(tightScale(windowed.flatMap((p) => [p.raw, p.ma7])));
```

with (scale from the band edges + the average, ignoring the wide raw extremes; filter nulls):

```js
	const yScale = $derived(
		tightScale(
			windowed.flatMap((p) => [p.band_lo, p.band_hi, p.ma7]).filter((v): v is number => v != null)
		)
	);
```

(b) Replace the two existing `datasets` (the `daily` raw line and the `7-day average` line, lines 72-91) with a band pair drawn behind a top average line. The band is two borderless datasets with a fill between them; order them first so the bold average draws on top:

```js
				datasets: [
					{
						label: 'band-hi',
						data: windowed.map((p) => p.band_hi),
						borderColor: 'transparent',
						borderWidth: 0,
						pointRadius: 0,
						fill: '+1',
						backgroundColor: 'rgba(126,168,216,0.10)',
						tension: 0.3,
						spanGaps: false
					},
					{
						label: 'band-lo',
						data: windowed.map((p) => p.band_lo),
						borderColor: 'transparent',
						borderWidth: 0,
						pointRadius: 0,
						fill: false,
						tension: 0.3,
						spanGaps: false
					},
					{
						label: '7-day average',
						data: windowed.map((p) => p.ma7),
						borderColor: SCORE_COLOR,
						borderWidth: 2.25,
						pointRadius: 0,
						tension: 0.3,
						spanGaps: false
					}
				]
```

(c) The `RAW_COLOR` const (line 32) is now unused — delete it.

(d) Tooltip: the band datasets should not clutter the tooltip. In the `tooltip` config, filter them out. Add a `filter` callback to the existing `tooltip` block (alongside `callbacks`):

```js
					tooltip: {
						...chartTooltip(SCORE_COLOR),
						filter: (item) => item.dataset.label === '7-day average',
						callbacks: {
							title: (items) => fmtFullDate(new Date(items[0].parsed.x ?? 0)),
							label: (item) =>
								`${item.dataset.label}: ${item.parsed.y == null ? '—' : item.parsed.y.toFixed(2)} z`
						}
					},
```

> The existing horizontal `typicalBand` annotation (bordered box + "typical" label) and
> `zeroLine` stay unchanged. The new dispersion band is borderless fill, so the two read
> as distinct. Confirm this visually in Task 8; if ambiguous, add `borderDash: [3,3]` to
> the `typicalBand` box border as the fallback.

- [ ] **Step 2: Verify the frontend compiles**

Run: `cd frontend && npm run check`
Expected: 0 errors. (If `tightScale`'s type guard line trips lint, ensure the `.filter((v): v is number => v != null)` matches the existing usage style in `chart-scale.ts` consumers.)

- [ ] **Step 3: Commit**

```bash
git add frontend/src/lib/components/recovery/RecoveryTrajectory.svelte
git commit -m "Draw dispersion band and scale trajectory axis to it"
```

---

## Task 6: Delete the topo background

**Files:**
- Modify: `frontend/src/routes/+layout.svelte` (markup ~lines 62-82; `.topo-bg` CSS ~lines 131-138)

- [ ] **Step 1: Remove the SVG block**

Delete the entire SVG background block (the comment + `<svg class="topo-bg"> ... </svg>`, lines 63-82):

```html
		<!-- SVG topo pattern background -->
		<svg class="topo-bg" xmlns="http://www.w3.org/2000/svg">
			...
			<rect width="100%" height="100%" filter="url(#topo-noise)" />
			<rect width="100%" height="100%" fill="url(#topo-lines)" />
		</svg>
```

The wrapping `<div class="topo-page">` stays.

- [ ] **Step 2: Remove the now-dead CSS**

Delete the `.topo-bg { ... }` rule (the `position: fixed; inset: 0; ... z-index: 0;` block). Leave `.topo-page`, `.topo-header`, `.topo-content` untouched.

- [ ] **Step 3: Verify no dangling references**

Run: `cd frontend && grep -rn "topo-bg\|topo-noise\|topo-lines" src/`
Expected: no matches.

- [ ] **Step 4: Verify the frontend compiles**

Run: `cd frontend && npm run check`
Expected: 0 errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/routes/+layout.svelte
git commit -m "Remove decorative topo background from data surfaces"
```

---

## Task 7: Evidence table column widths + neutral sparkline

**Files:**
- Modify: `frontend/src/lib/components/recovery/EvidenceTable.svelte`

- [ ] **Step 1: Add a colgroup**

In `EvidenceTable.svelte`, immediately after `<table>` (line 67) and before `<thead>`, insert:

```html
		<colgroup>
			<col style="width: 180px" />
			<col style="width: 96px" />
			<col style="width: 96px" />
			<col style="width: 80px" />
			<col />
		</colgroup>
```

- [ ] **Step 2: Let the sparkline column flex and widen the sparkline itself**

In the `<style>` block, change the `td.spark` rule (lines 189-192) from a fixed 110px to auto, and widen the rendered sparkline. Replace:

```css
	td.spark {
		text-align: center;
		width: 110px;
	}
```

with:

```css
	td.spark {
		text-align: center;
	}
```

Then make the sparkline fill the wider column — pass an explicit width on the `<EvidenceSparkline>` usage (line 92):

```html
					<td class="spark"><EvidenceSparkline points={row.sparkline} {color} width={300} /></td>
```

- [ ] **Step 3: Neutralize the sparkline color**

The sparkline currently shares the Δz status `color`. Decouple it: keep `color` for the Δz cell, pass a fixed neutral to the sparkline. Change line 92 (now also carrying `width`) to use a neutral constant instead of `{color}`:

```html
					<td class="spark"><EvidenceSparkline points={row.sparkline} color="#5e7282" width={300} /></td>
```

Leave line 89 (`<td class="num delta" style="color:{color}">`) untouched — Δz stays semantically colored.

- [ ] **Step 4: Verify the frontend compiles**

Run: `cd frontend && npm run check`
Expected: 0 errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/components/recovery/EvidenceTable.svelte
git commit -m "Fix evidence table column widths and neutralize sparklines"
```

---

## Task 8: Visual verification (non-negotiable)

**Files:** none (verification only).

- [ ] **Step 1: Ensure servers are running**

Backend: `cd backend && uv run uvicorn app.main:app --reload` (if not already up on :8000).
Frontend: `cd frontend && npm run dev` (if not already up on :5173).

- [ ] **Step 2: Desktop screenshots (1440-wide)**

Use browser MCP: navigate to `http://localhost:5173`, resize to 1440×900, screenshot the trajectory canvas and the evidence table. Verify:
- the 7-day average line now fills most of the plot height (no longer squished into the middle third);
- the dispersion band reads as a soft ribbon and is visually distinct from the bordered "typical" box;
- no wavy/grain background texture anywhere on the page;
- evidence table: metric column tightened, sparkline column wide and legible;
- sparklines are neutral gray; the Δz column is still green/red with arrows.

- [ ] **Step 3: Mobile screenshot (390-wide)**

Resize to 390×844, full-page screenshot. Verify the chart still renders the band + line, text fits, and the sparkline column is hidden (existing `max-width: 640px` rule).

- [ ] **Step 4: Edge cases**

Confirm the chart's empty/loading states still render (no console errors); hover a day and confirm the tooltip shows only the `7-day average` value (band datasets filtered out) and the evidence table re-points to that day.

- [ ] **Step 5: If the two bands read ambiguously**

Apply the fallback from Task 5: add `borderDash: [3, 3]` to the `typicalBand` annotation's border, re-check visually, and commit:

```bash
git add frontend/src/lib/components/recovery/RecoveryTrajectory.svelte
git commit -m "Dash the typical-band border to distinguish it from the dispersion band"
```

---

## Self-Review Notes

- **Spec coverage:** Change 1 → Tasks 1-5; Change 2 → Task 6; Change 3 → Task 7 (colgroup); Change 4 → Task 7 (neutral color). Testing section → Tasks 1-4 (backend) + Task 8 (frontend visual).
- **`ma7` unchanged:** Task 3 gives `ma7` its own 6-day seed (`SEED_DAYS`) and the SD a separate 13-day seed (`BAND_SEED_DAYS`), so `ma7` output is byte-for-byte identical to today — no existing ma7 test should change.
- **Type consistency:** `band_lo`/`band_hi: float | None` everywhere (dataclass `ScorePoint`, contract `RecoveryScorePoint`, generated TS); `trailing_sd(values, window, min_valid)` and `seeded_sd(seed, display)` signatures match their call sites; `BAND_WINDOW=14`, `BAND_SEED_DAYS=13`, `BAND_MIN_VALID=5` defined once in `smoothing.py` and imported where used.
