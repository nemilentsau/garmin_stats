# HRV Enhancement Plan

## Goal

Add 9 new HRV analysis features to the `/api/hrv/insights` endpoint and frontend HRV page. Each feature uses data already parsed from FIT files — no parser changes needed.

---

## Feature 1: Nightly HRV Volatility (stdev)

**What:** Standard deviation of intraday HRV readings within a single night. High volatility indicates fragmented or restless sleep even when the average looks fine.

### Backend

**Model (`models.py`):**
- Add field to `HrvIntradaySegment`: `stdev: float | None = None`

**Service (`services/hrv.py`):**
- In `_build_intraday_segment()`, compute `stdev` from `sample_values` using `statistics.stdev` (or `pstdev` for population). Only when `len(sample_values) >= 2`.

**Insight rule (`_build_insights`):**
- If stdev > 25ms and recovery status is suppressed/below_baseline → caution insight: "High HRV variability overnight may indicate fragmented sleep."

### Frontend

- Add stdev to the intraday segment stat card (next to avg/min/max).

---

## Feature 2: Garmin Baseline Band Overlay

**What:** Surface Garmin's own baseline zones (`baseline_low_upper`, `baseline_balanced_lower`, `baseline_balanced_upper`) on the daily trend chart. Shows where nightly HRV falls relative to the device's personalized bands.

### Backend

**Model (`models.py`):**
- New model `HrvBaselineBands`:
  ```
  baseline_low_upper: float | None
  baseline_balanced_lower: float | None
  baseline_balanced_upper: float | None
  ```
- Add to `HrvInsightsResponse`: `baseline_bands: HrvBaselineBands | None = None`

**Service (`services/hrv.py`):**
- In `load_hrv_insights()`: load HRV summaries for the selected date, extract the three baseline fields from the first summary.

**Stats (`stats.py`):**
- Also persist `last_night_5_min_high` into `DailyHrvStats` so it's available for the trend chart and stat cards.
- Add field to `DailyHrvStats`: `five_min_high: float | None = None`

### Frontend

- On the daily trend chart, add two horizontal shaded regions:
  - Red-tinted band below `baseline_low_upper` (unhealthy zone)
  - Green-tinted band between `baseline_balanced_lower` and `baseline_balanced_upper` (healthy zone)
- Add 5-min high to day snapshot stat card.

---

## Feature 3: Overnight HRV Trajectory (early/mid/late thirds)

**What:** Split overnight HRV readings into three equal-time segments (early, mid, late sleep) and compare averages. A rising trajectory (low→high) suggests good parasympathetic recovery; falling suggests disrupted sleep.

### Backend

**Model (`models.py`):**
- New model `HrvTrajectory`:
  ```
  early_avg: float | None
  mid_avg: float | None
  late_avg: float | None
  direction: str | None  # "rising", "falling", "flat", or None
  ```
- Add to `HrvInsightsResponse`: `trajectory: HrvTrajectory | None = None`

**Service (`services/hrv.py`):**
- New function `_compute_trajectory(hrv_values: list[HrvValue]) -> HrvTrajectory | None`:
  1. Parse and sort timestamps.
  2. Split the time range into 3 equal segments.
  3. Compute avg HRV for each segment.
  4. Direction: if late_avg - early_avg > 5 → "rising"; if < -5 → "falling"; else "flat".
  5. Return None if < 6 readings (need at least 2 per segment).

**Insight rule:**
- If direction == "falling" and recovery status is suppressed → warning: "HRV declined through the night, suggesting disrupted recovery."

### Frontend

- Small 3-bar chart (early/mid/late) or arrow indicator showing trajectory direction.
- Add to the recovery stat card area.

---

## Feature 4: Day-of-Week HRV Patterns

**What:** Average nightly HRV grouped by day of week across the full dataset. Surfaces lifestyle patterns (e.g., consistently lower HRV after weekend nights).

### Backend

**Model (`models.py`):**
- New model `HrvDayOfWeekBucket`:
  ```
  day: str         # "Mon", "Tue", etc.
  day_index: int   # 0=Mon, 6=Sun
  avg_nightly: float | None
  sample_count: int
  ```
- Add to `HrvInsightsResponse`: `day_of_week: list[HrvDayOfWeekBucket] = []`

**Service (`services/hrv.py`):**
- New function `_compute_day_of_week(metrics: list[DailyMetric]) -> list[HrvDayOfWeekBucket]`:
  1. Group nightly_avg by ISO weekday.
  2. Compute average per day.
  3. Return 7 buckets sorted Mon→Sun.

### Frontend

- Horizontal bar chart showing avg HRV per weekday, color-coded (highlight days that are notably above/below overall average).

---

## Feature 5: Consecutive Status Streak

**What:** Count consecutive days of the same HRV status (especially "Low"/"Unbalanced" streaks). A 3+ day suppressed streak is a stronger recovery signal than a single bad night.

### Backend

**Model (`models.py`):**
- New model `HrvStreak`:
  ```
  current_status: str | None  # normalized status
  streak_days: int
  worst_recent_streak: int    # longest suppressed streak in last 14 days
  ```
- Add to `HrvInsightsResponse`: `streak: HrvStreak | None = None`

**Service (`services/hrv.py`):**
- New function `_compute_streak(metrics: list[DailyMetric], selected_index: int) -> HrvStreak`:
  1. Walk backwards from selected_index while status matches.
  2. Count consecutive days.
  3. Also scan the 14-day window for the longest "Low"/"Unbalanced" run.

**Insight rule:**
- If current streak of "Low"/"Unbalanced" >= 3 → warning: "HRV has been suppressed for {N} consecutive days."

### Frontend

- Add streak indicator to recovery stat card area (e.g., "3-day Low streak").

---

## Feature 6: Cross-Domain Correlations (HRV vs Sleep, HRV vs Resting HR)

**What:** Scatter plots showing the relationship between nightly HRV and other recovery metrics across the full dataset. Expected: HRV↔Sleep positive correlation, HRV↔Resting HR inverse correlation.

### Backend

**Model (`models.py`):**
- New model `HrvCorrelationPoint`:
  ```
  date: str
  nightly_avg: float
  other_value: float
  ```
- New model `HrvCorrelation`:
  ```
  metric: str              # "sleep_score", "resting_hr"
  label: str               # "Sleep Score", "Resting HR"
  points: list[HrvCorrelationPoint]
  r_value: float | None    # Pearson correlation coefficient
  ```
- Add to `HrvInsightsResponse`: `correlations: list[HrvCorrelation] = []`

**Service (`services/hrv.py`):**
- New function `_compute_correlations(metrics: list[DailyMetric]) -> list[HrvCorrelation]`:
  1. Pair nightly_avg with sleep_score and resting HR where both are present.
  2. Compute Pearson r using `numpy.corrcoef` (already a dependency).
  3. Return correlation objects. Skip if < 7 paired data points.

### Frontend

- Two scatter plots side by side: HRV vs Sleep Score, HRV vs Resting HR.
- Display r-value as a subtitle (e.g., "r = -0.62").

---

## Feature 7: 30-Day Rolling Baseline

**What:** Longer-term trend line beyond the current 7-day window. Helps distinguish "bad week" from "bad month" — a declining 30-day trend is more concerning than a single-week dip.

### Backend

**Model (`models.py`):**
- New model `HrvLongBaseline`:
  ```
  baseline_30d: float | None
  delta_7d_vs_30d: float | None  # positive = recent week is above monthly trend
  ```
- Add to `HrvInsightsResponse`: `long_baseline: HrvLongBaseline | None = None`

**Service (`services/hrv.py`):**
- New function `_compute_long_baseline(metrics: list[DailyMetric], selected_index: int) -> HrvLongBaseline | None`:
  1. Collect nightly_avg from the 30 days prior to selected_index.
  2. Compute 30-day average.
  3. Compare the existing 7-day baseline to the 30-day baseline.
  4. Return None if < 14 data points in the 30-day window.

**Insight rule:**
- If delta_7d_vs_30d < -5 → caution: "Your 7-day HRV average is trending below your monthly baseline."

### Frontend

- Add 30-day baseline as a dashed line on the daily trend chart.
- Show delta in recovery stat card.

---

## Feature 8: Readiness Score

**What:** Composite 0–100 score combining HRV recovery status, sleep score, resting HR delta, and HRV trend direction into a single actionable number.

### Backend

**Model (`models.py`):**
- New model `HrvReadiness`:
  ```
  score: int | None         # 0-100
  components: dict[str, float]  # breakdown: {"hrv_recovery": 30, "sleep": 25, ...}
  label: str | None         # "Ready", "Moderate", "Rest"
  ```
- Add to `HrvInsightsResponse`: `readiness: HrvReadiness | None = None`

**Service (`services/hrv.py`):**
- New function `_compute_readiness(selected: DailyMetric, recovery: HrvRecovery, resting_delta: float | None) -> HrvReadiness | None`:
  1. Score components (each 0–25, total 0–100):
     - **HRV recovery** (25pts): based on `recovery.status` — elevated=25, stable=20, below_baseline=10, suppressed=0
     - **Sleep** (25pts): based on `sleep.score` — scaled linearly from 0 (score<40) to 25 (score>=90)
     - **Resting HR** (25pts): based on `resting_delta` — delta <= -3 → 25, delta 0 → 20, delta >= 6 → 5
     - **HRV status** (25pts): based on device status — Balanced=25, High=20, Low=5, Unbalanced=0
  2. Label: score >= 75 → "Ready", >= 50 → "Moderate", < 50 → "Rest"
  3. Return None if sleep score and HRV status are both missing.

### Frontend

- Large circular gauge or prominent number at the top of the page.
- Breakdown bar showing the 4 component contributions.

---

## Feature 9: Period-Level Nightly HRV Distribution

**What:** Histogram of all nightly averages across the full dataset, with a marker showing where today falls. Gives context for whether today's value is truly unusual or within normal range.

### Backend

**Model (`models.py`):**
- New model `HrvDistributionBin`:
  ```
  bin_start: float
  bin_end: float
  count: int
  ```
- New model `HrvDistribution`:
  ```
  bins: list[HrvDistributionBin]
  total_days: int
  selected_value: float | None       # today's nightly avg
  selected_percentile: float | None   # where today falls (0-100)
  ```
- Add to `HrvInsightsResponse`: `distribution: HrvDistribution | None = None`

**Service (`services/hrv.py`):**
- New function `_compute_distribution(metrics: list[DailyMetric], selected_index: int) -> HrvDistribution | None`:
  1. Collect all nightly_avg values.
  2. Build 5ms-wide histogram bins (same pattern as HR distribution in `heart_rate_analysis.py`).
  3. Compute percentile rank of selected day's value.
  4. Return None if < 7 data points.

### Frontend

- Bar chart histogram with the selected day's value highlighted (vertical line or colored bin).
- Subtitle: "Your HRV tonight is at the Xth percentile."

---

## Implementation Order

1. **Feature 1 (Volatility)** — smallest change, extends existing segment model
2. **Feature 5 (Streak)** — pure computation, no chart work
3. **Feature 7 (30-day baseline)** — extends existing recovery logic
4. **Feature 2 (Baseline bands)** — needs chart overlay, data already parsed
5. **Feature 9 (Distribution)** — reuses histogram pattern from HR analysis
6. **Feature 3 (Trajectory)** — needs new mini-chart
7. **Feature 4 (Day-of-week)** — needs new bar chart
8. **Feature 6 (Correlations)** — needs scatter plot (new chart type)
9. **Feature 8 (Readiness)** — most complex, depends on other features being stable

---

## Files Changed

| File | Features |
|------|----------|
| `backend/app/models.py` | 1–9 — new models + new fields on existing models |
| `backend/app/services/hrv.py` | 1–9 — new compute functions + insight rules |
| `backend/app/stats.py` | 2 — persist `five_min_high` into DailyHrvStats |
| `backend/app/routers/hrv.py` | No changes (response model auto-includes new fields) |
| `frontend/src/lib/api-types.ts` | Regenerated via script |
| `frontend/src/routes/hrv/+page.svelte` | 1–9 — new charts + stat cards |
| `backend/tests/test_hrv_service.py` | 1–9 — new test cases |

---

## Validation Checklist

```bash
cd backend && uv run ruff check
cd backend && uv run pyright app/ tests/
cd backend && uv run pytest tests/ -v
bash scripts/generate-api-types.sh
cd frontend && npm run check
```

Re-ingest needed only for Feature 2 (persisting `five_min_high` into daily metrics):
```bash
cd backend && uv run python ../scripts/reingest.py
```
