# Garmin Health Data Findings

This file records analytical observations from the current local dataset, not product plans or schema notes.

Snapshot date: `2026-05-17`
Device: Garmin Epix Gen 2 Pro
Coverage: `2025-06-01` through `2026-05-16` (`347` days)

The numbers below were refreshed from live persisted `daily_metrics` data and
visually checked with the chart-inspection workflow in
`.claude/skills/data-analysis/scripts/inspect_charts.py`.

## Data Quality

### Coverage and missingness

- Heart rate, resting heart rate, stress, body battery, and respiration have full daily coverage across all `347` days.
- HRV nightly is missing on `13` days (`3.7%`).
- Sleep score and skin temperature deviation are each missing on `10` days (`2.9%`).
- SpO2 average and minimum are missing on `68` days (`19.6%`).

### Missingness pattern

- SpO2 missingness is front-loaded and clustered. SpO2 is absent from `2025-06-01` through `2025-07-12`, then again from `2025-12-12` through `2026-01-06`. The most recent `14` days have complete SpO2 coverage.
- HRV, sleep, and skin-temperature gaps still cluster around a small set of dates, especially `2025-11-05` through `2025-11-20`, with later single-day gaps on `2025-12-12`, `2026-01-24`, `2026-04-21`, and `2026-04-22`.
- The zero-BPM heart-rate artifact fix remains important. Garmin emits `0` when wrist contact is lost; filtering those values keeps minima and averages usable.

## Distribution Snapshot

| Metric | Mean | Median | SD | IQR | Min | Max | Notes |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Resting HR | 50.5 | 50.0 | 4.7 | 47.0-53.0 | 41.0 | 69.0 | Stable center, with November still the clear high-stress block |
| HR Avg | 67.4 | 66.9 | 5.4 | 63.7-70.3 | 54.6 | 85.6 | Strongly tracks stress |
| Stress Avg | 34.0 | 32.4 | 9.8 | 27.1-38.8 | 14.7 | 70.7 | Broad range; late April and early May add another elevated patch |
| Body Battery Avg | 31.3 | 30.6 | 17.5 | 17.1-44.0 | 5.0 | 76.1 | Widest day-level spread; average alone hides large swings |
| SpO2 Avg | 92.9 | 93.1 | 1.5 | 92.4-93.8 | 82.4 | 95.7 | Usually stable, but late April contains a real low-average cluster |
| SpO2 Min | 79.8 | 80.0 | 3.7 | 77.0-82.0 | 72.0 | 90.0 | Minimum remains more informative than average |
| Respiration Avg | 13.0 | 12.9 | 0.8 | 12.4-13.5 | 11.4 | 15.5 | Sensitive stress-side metric |
| HRV Nightly | 52.6 | 53.0 | 13.9 | 41.2-62.8 | 21.0 | 87.0 | Broad but coherent recovery-side signal |
| Sleep Score | 62.0 | 66.0 | 19.0 | 47.0-77.0 | 12.0 | 93.0 | Left skew persists; median is a better typical-night summary |
| Skin Temp Dev | -0.0 | -0.0 | 0.4 | -0.3-0.2 | -1.4 | 1.2 | Centered near baseline with a few meaningful outliers |

### Interpretation

- HRV nightly and sleep score remain left-skewed. Median is a better "typical night" summary than mean for both.
- Body battery average has the largest relative spread and behaves more like a recovery-state index than a stable baseline metric.
- SpO2 average is usually weakly varying, but `2026-04-21` through `2026-04-27` contains a visible low-average cluster. That window should be treated as a data-quality or health-context question before drawing causal conclusions.

## Temporal Observations

### One major suppression block still dominates the dataset

- The worst `14`-day recovery window is `2025-11-05` through `2025-11-18`.
- The five worst composite recovery days are `2025-11-18`, `2025-11-17`, `2025-11-12`, `2025-11-08`, and `2026-03-30`.
- November 2025 remains the clearest system-wide stress month:
  - Resting HR: `57.3`
  - Stress: `47.2`
  - Body Battery: `15.1`
  - HRV nightly: `41.7`
  - Sleep score: `38.8`
  - Respiration: `13.5`

### Recovery improved through February, then softened in late April and May

- The best `14`-day window remains `2026-02-19` through `2026-03-04`.
- January and February 2026 are still the strongest recovery months in the current sample:
  - January: resting HR `47.9`, HRV `58.6`, sleep `72.1`, body battery `46.6`
  - February: resting HR `46.0`, HRV `60.7`, sleep `72.6`, body battery `46.2`
- The last `30` days (`2026-04-17` through `2026-05-16`) are worse than the full-period average on several stress-side metrics:
  - Resting HR: `+0.60`
  - Stress: `+4.18`
  - Body Battery: `-9.04`
  - HRV nightly: `-3.91`
  - Sleep score: `+0.28`
  - Respiration: `+0.18`

## Cross-Metric Relationships

The dataset still resolves into one stress-side cluster and one recovery-side cluster.

### Strong positive relationships

- HR Avg ↔ Stress: `0.869`
- Body Battery ↔ HRV Nightly: `0.801`
- Stress ↔ Respiration: `0.776`
- Body Battery ↔ Sleep Score: `0.776`

### Strong inverse relationships

- Respiration ↔ HRV Nightly: `-0.830`
- Stress ↔ Body Battery: `-0.748`
- Body Battery ↔ Respiration: `-0.727`
- HR Avg ↔ Body Battery: `-0.685`
- Stress ↔ HRV Nightly: `-0.670`

### Weak signal: SpO2

- SpO2 Avg ↔ Sleep Score: `0.174`
- SpO2 Avg ↔ HRV Nightly: `0.168`
- SpO2 Avg ↔ Stress: `-0.316`

Daily SpO2 average still behaves like a secondary context signal rather than a main recovery driver, but the late-April low cluster deserves manual context review.

## Visualization Status

- The chart-inspection script works against the current repo state after switching its data-root lookup to `app.core.config.get_app_config()`.
- Refreshed charts are in `.claude/chart-inspections/findings-refresh-20260517/`.
- Visual inspection confirms nonblank charts across the expected `2025-06-01` to `2026-05-16` range, the same November 2025 suppression block, the February 2026 recovery peak, and a late-April SpO2/skin-temperature anomaly.
- The IQR-band charts remain the right choice. They preserve day-to-day trend readability without letting extreme min/max spikes flatten the useful signal.

## Analytical Takeaways

- This is still a strong recovery dataset, not yet a strong training-performance dataset.
- The most reliable daily recovery indicators remain HRV nightly, resting HR, sleep score, body battery, stress, and respiration.
- Respiration continues to be one of the most sensitive stress-side signals. It moves strongly against HRV and rises during the same low-recovery windows.
- Experiments should build on this recovery stack first. The data does not yet justify strong performance-attribution claims for training outcomes.

## Open Questions

1. What caused the concentrated November 2025 suppression block, and do manual logs already capture it somewhere else in the product?
2. What happened around `2026-04-21` through `2026-04-27`, when SpO2 averages and skin-temperature readings both moved sharply?
3. Should SpO2 minimum, not SpO2 average, become the default surfaced oxygen metric in the recovery context?
4. Should HRV and sleep defaults favor median or rolling median summaries instead of mean-heavy summaries?
5. Which undocumented `METRICS` message types matter for the next phase, once experiments begin to ask training-adjacent questions?
