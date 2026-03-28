# Garmin Health Data Findings

This file records analytical observations from the current local dataset, not product plans or schema notes.

Snapshot date: `2026-03-28`  
Device: Garmin Epix Gen 2 Pro  
Coverage: `2025-06-01` through `2026-03-27` (`297` days)

The numbers below were refreshed from live `daily_metrics` data and from the repaired chart-inspection workflow in `.claude/skills/data-analysis/scripts/inspect_charts.py`.

## Data Quality

### Coverage and missingness

- Heart rate, resting heart rate, stress, body battery, and respiration have full daily coverage across all `297` days.
- HRV nightly is missing on `12` days (`4.0%`).
- Sleep score and skin temperature deviation are each missing on `9` days (`3.0%`).
- SpO2 average and minimum are missing on `68` days (`22.9%`).

### Missingness pattern

- SpO2 missingness is front-loaded, not random. The first non-null SpO2 day is `2025-07-13`, the last missing SpO2 day is `2026-01-06`, and the most recent `14` days have complete SpO2 coverage.
- HRV, sleep, and skin-temperature gaps cluster around a small set of dates, especially `2025-11-05` through `2025-11-20`, plus `2025-12-12` and `2026-01-24`. That pattern looks more like non-wear or overnight capture failure than sensor drift.
- The zero-BPM heart-rate artifact fix remains important. Garmin emits `0` when wrist contact is lost; filtering those values keeps minima and averages usable.

## Distribution Snapshot

| Metric | Mean | Median | SD | IQR | Min | Max | Notes |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Resting HR | 50.6 | 50.0 | 4.8 | 47.0-54.0 | 41.0 | 69.0 | Moderate spread with a clear high-stress period in November |
| HR Avg | 67.2 | 66.6 | 5.5 | 63.4-69.9 | 54.6 | 85.6 | Strongly tracks stress |
| Stress Avg | 33.8 | 32.2 | 9.8 | 26.9-38.8 | 14.7 | 70.7 | Broad range, with a distinct suppression/rebound story over time |
| Body Battery Avg | 31.6 | 30.8 | 17.6 | 17.4-44.3 | 5.0 | 76.1 | Widest day-level spread; average alone hides large swings |
| SpO2 Avg | 93.1 | 93.2 | 1.0 | 92.5-93.8 | 88.7 | 95.7 | Average is stable; minimum is the more interesting signal |
| SpO2 Min | 79.9 | 80.0 | 3.6 | 77.0-83.0 | 72.0 | 89.0 | Meaningful overnight dips exist despite flat averages |
| Respiration Avg | 13.0 | 12.9 | 0.8 | 12.4-13.5 | 11.4 | 15.5 | Sensitive stress-side metric |
| HRV Nightly | 52.2 | 53.0 | 13.8 | 41.0-62.0 | 22.0 | 85.0 | Slight left skew; bad nights drag the mean down |
| Sleep Score | 61.4 | 65.0 | 19.3 | 46.0-77.0 | 12.0 | 93.0 | Also left skewed; typical nights are better than the mean suggests |
| Skin Temp Dev | -0.01 | -0.06 | 0.37 | -0.25-0.22 | -1.37 | 1.22 | Centered near baseline as expected |

### Interpretation

- HRV nightly and sleep score remain left-skewed. Median is a better "typical night" summary than mean for both.
- Body battery average has the largest relative spread and behaves more like a recovery-state index than a stable baseline metric.
- SpO2 average barely moves day to day. The useful daily SpO2 story is in the minimum values, not the mean.

## Temporal Observations

### One major suppression block dominates the dataset

- The worst `14`-day recovery window is `2025-11-05` through `2025-11-18`.
- The five worst composite recovery days are `2025-11-17`, `2025-11-18`, `2025-11-12`, `2025-11-08`, and `2025-12-07`.
- November 2025 is the clearest system-wide stress month in the data:
  - Resting HR: `57.3`
  - Stress: `47.2`
  - Body Battery: `15.1`
  - HRV nightly: `41.7`
  - Sleep score: `38.8`
  - Respiration: `13.5`

### Recovery materially improves after that block

- The best `14`-day window is `2026-02-19` through `2026-03-04`.
- January and February 2026 are the strongest recovery months in the current sample:
  - January: resting HR `47.9`, HRV `58.6`, sleep `72.1`, body battery `46.6`
  - February: resting HR `46.0`, HRV `60.7`, sleep `72.6`, body battery `46.2`
- The last `30` days are still better than the full-period average:
  - Resting HR: `-4.05`
  - Stress: `-2.89`
  - Body Battery: `+4.77`
  - HRV nightly: `+7.16`
  - Sleep score: `+6.57`
  - Respiration: `-0.45`

## Cross-Metric Relationships

The dataset still resolves into one stress-side cluster and one recovery-side cluster.

### Strong positive relationships

- HR Avg ↔ Stress: `0.881`
- Body Battery ↔ HRV Nightly: `0.796`
- Body Battery ↔ Sleep Score: `0.796`
- HRV Nightly ↔ Sleep Score: `0.647`

### Strong inverse relationships

- Respiration ↔ HRV Nightly: `-0.836`
- Resting HR ↔ HRV Nightly: `-0.750`
- Stress ↔ Body Battery: `-0.747`
- HR Avg ↔ Body Battery: `-0.693`
- Stress ↔ HRV Nightly: `-0.674`

### Weak signal: SpO2

- SpO2 Avg ↔ Sleep Score: `0.151`
- SpO2 Avg ↔ HRV Nightly: `0.096`

Daily SpO2 average still behaves like a weakly varying background signal rather than a main recovery driver.

## Visualization Status

- The chart-inspection script now works against the current repo state. The fix was to resolve the actual Garmin data root and reuse the parsed aggregate payload instead of reparsing from the wrong default path four times.
- The refreshed charts are in `.claude/chart-inspections/findings-refresh-20260328/`.
- The dashboard overview confirms the same story as the direct query pass: a strong suppression block in November 2025, a rebound through January and February 2026, and much cleaner recent recovery.
- The IQR-band charts remain the right choice. They preserve day-to-day trend readability without letting extreme min/max spikes flatten the useful signal.

## Analytical Takeaways

- This is a strong recovery dataset, not yet a strong training-performance dataset.
- The most reliable daily recovery indicators remain HRV nightly, resting HR, sleep score, body battery, stress, and respiration.
- Respiration continues to be one of the most sensitive stress-side signals. It moves strongly against HRV and rises during the same low-recovery windows.
- Experiments should build on this recovery stack first. The data does not yet justify strong performance-attribution claims for training outcomes.

## Open Questions

1. What caused the concentrated November 2025 suppression block, and do manual logs already capture it somewhere else in the product?
2. Should SpO2 minimum, not SpO2 average, become the default surfaced oxygen metric in the recovery context?
3. Should HRV and sleep defaults favor median or rolling median summaries instead of mean-heavy summaries?
4. Which undocumented `METRICS` message types matter for the next phase, once experiments begin to ask training-adjacent questions?
