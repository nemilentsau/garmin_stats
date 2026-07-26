# Recovery Dashboard

**Status:** shipped.

The overview presents one validated physiological-recovery axis plus two independent health-context flags. It is not a workout-readiness, training-load, adaptation, sleep-opportunity, or overall-health score.

## Recovery score

The score combines seven daily signals that co-move on the user's recovery axis:

- recovery-positive: nightly HRV, Body Battery, sleep score;
- recovery-negative after sign reversal: resting heart rate, daily average heart rate, stress, respiration.

For each day, the backend:

1. normalizes each available input against the user's expanding prior history with robust median/MAD z-scores, excluding the current day and requiring at least 30 prior present values;
2. reverses the negative-recovery signals so higher consistently means stronger recovery;
3. applies the correlation-deflated weights in `domain/recovery_score/weighting.py`, renormalized across available inputs, and requires at least five of seven;
4. computes the seeded trailing 7-day average used as the displayed trend.

The raw output is a personal z-score: zero is typical, negative is suppressed, and positive is stronger than usual. The frontend does not recompute any part of it.

## State, change, and regimes

- Band: `suppressed` at or below -0.5 z, `typical` strictly between -0.5 and +0.5 z, and `strong` at or above +0.5 z (`domain/recovery_score/thresholds.py::score_band`; exactly ±0.5 resolves to `suppressed`/`strong`, not `typical`).
- Trend: the latest 7-day mean versus the previous 7-day mean; a change of at least 0.97 z is meaningful.
- Acute event: a one-day move of at least 1.86 z is reported separately and never replaces the trend.
- Regime: at least 14 days with the 7-day average outside the typical band, merging returns of at most three days.

The state sentence composes band and trend. These labels describe position on a continuum; they are not physiological archetypes.

## Health flags

Oxygen and thermoregulation remain outside the recovery score:

- oxygen compares nightly average SpO2 with the personal median minus 2.5 MAD;
- skin temperature compares deviation with the personal median plus/minus 2.5 MAD;
- missing readings are `unknown`, never `normal`;
- structural SpO2 coverage gaps are returned explicitly.

The two flags have independent status vocabularies and no blended severity score.

## API and implementation

`GET /api/dashboard` returns `DashboardOverviewResponse`:

| Field | Meaning |
|---|---|
| `state` | current band, trend, and score |
| `score` | daily raw score, seeded 7-day trend, typical band, and display dispersion values |
| `change` | week-over-week and acute comparisons |
| `evidence` | latest per-input value, baseline, signed delta, source, and drill-down link |
| `driver_series` | dated evidence values aligned to the score series for hover inspection |
| `flags` / `flag_series` | current and dated oxygen/temperature context |
| `spo2_gaps` | explicit structural coverage gaps |
| `events` | detected recovery regimes |
| `correlations` | HRV detail-page association context; not an overview lane |

Computation lives in `backend/app/domains/garmin_analytics/domain/recovery_score/` and `domain/dashboard.py`. `application/dashboard.py` loads the data through the repository port; caching lives at the persistence boundary in `adapters.py` (`cache.cached(cache.DAILY_METRICS, ...)`), not in the application use case. The overview renders the shared-axis trajectory, evidence table, and flag strip; metric pages remain drill-downs.

## Product boundary

Running activity data now exists, but it is deliberately not folded into this score. The training-state overview described in [`../routine-pivot/pivot_roadmap.md`](../routine-pivot/pivot_roadmap.md) must present progress, load, and constraints as distinct backend-owned lanes instead of stretching the recovery construct.
