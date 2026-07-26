# HRV Detail

**Status:** shipped.

The HRV tab answers two separate questions: what the multi-night trend is doing, and how the latest or selected night compares with its recent baseline. Those signals intentionally use different grains and must not be collapsed into one status.

## Trend versus one night

- **Trend** is the backend-computed 7-day moving average of nightly HRV compared with a trailing typical-range band for the selected 30/60/90-day baseline window. `trend_state` colors the history strip and represents the smoothed series, not a raw night.
- **Latest/selected night** is one unsmoothed nightly value with its delta or z-score against the chosen recent baseline. `classify_hrv_recovery` uses that nightly delta only.
- **Garmin HRV status** is displayed as a separate vendor signal. It does not determine the app's nightly recovery classification or trend color.
- **Missing HRV** remains missing. Trend lines break across gaps and missing state is rendered neutrally.

The selected-night insight currently maps the prior-7-day delta to categorical
copy (`suppressed`, `below baseline`, or `above baseline`; the stable bucket emits
no recovery-status insight). The analysis record recommends eventually replacing
that category with continuous delta/z copy, but that change is not shipped; see
[`FINDINGS.md`](../../FINDINGS.md#resolved-questions).

This boundary also applies to the weekday chart: the backend classifies each weekday mean relative to the sample-weighted grand mean for that window. A weekday pattern describes group averages, not a prediction for one night.

## Backend ownership

- `garmin_health/domain/daily_metrics/hrv.py` computes (does not persist) the nightly and weekly Garmin summaries and the nightly delta classification; `garmin_sync` owns persisting the resulting `daily_metrics` rows.
- `garmin_analytics/domain/analysis/hrv.py` owns the gap-aware nightly trend, moving average, trailing band, extremes, pattern windows, weekday states, and counts.
- `garmin_analytics/domain/insights/hrv.py` owns latest/selected-night baseline comparisons and recovery insights.
- `/api/hrv/daily`, `/api/hrv/analysis`, and `/api/hrv/insights` expose those values. The dashboard response supplies the compact cross-metric correlations shown at the bottom of the tab.

The frontend chooses ranges, formats values, maps backend states to presentation tokens, and handles selection/loading. It does not compute baselines, moving averages, weekday means, extremes, correlations, or classifications.

## Current surface

The page contains:

1. latest nightly HRV and Garmin's separate status;
2. the nightly trend hero with selectable baseline and visible time range;
3. a keyboard-accessible nightly history strip and selected-night details;
4. backend-computed weekday patterns for predefined windows;
5. compact recovery co-movement context labeled as association, not cause.

The trend hero is the primary analytical surface. The selected-night panel is detail on demand; it must not replace or recolor the trend.
