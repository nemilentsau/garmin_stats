# Garmin Health Data — Analysis Findings

Data schemas and field documentation live in `.claude/skills/garmin-data/references/`. This file is for **analytical observations** — what the data tells us, not how it's structured.

**Device:** Garmin Epix Gen 2 Pro | **Period:** 2026-01-01 to 2026-02-06 (~37 days) | **SDK:** garmin-fit-sdk 21.188.0

---

## Data Quality

### Missingness
- **SpO2: 16% missing days** (6 of 37). **Explained:** SpO2 sensor was recently enabled — early days in the dataset predate activation. Not a sensor failure. The remaining values cluster tightly (92.5-95.5%, sd=0.7).
- **HRV: 3% missing** (1 day). Likely device not worn overnight.
- **Skin Temp: 3% missing** (1 day). Same likely cause.
- **Body Battery: 0% missing.** Complete coverage.
- **Sleep Score: 0% missing.** Complete coverage.
- **HR, Stress, Respiration: 0% missing.** Complete coverage across all 37 days.

### Sensor Artifacts
- **Zero-BPM readings:** The Garmin sensor emits HR=0 when it loses skin contact (wrist lifted, poor fit, etc.). These were contaminating stats — MIN showed 0 bpm, pulling averages down. Fixed by filtering `hr_value > 0` at ingest and as defense-in-depth in aggregation/zone computation. Same pattern already existed for respiration (filtered at `value > 0`).
- HR min values dip to ~40 bpm on some days — could be legitimate resting HR during deep sleep, or sensor artifact during low-motion periods. Cross-referencing with sleeping HR analysis confirms many low values coincide with deep sleep stages.
- HR max hits 160+ bpm — likely exercise peaks. Not artifacts, but they dominate min/max visualizations.

---

## Distribution Observations (from EDA)

| Metric | Mean | Median | SD | Shape | Notes |
|--------|------|--------|-----|-------|-------|
| HR Avg (bpm) | 64.3 | 64.3 | 3.3 | Normal, symmetric | Mean = median, safe to use mean |
| Stress Avg | 28.6 | 28.0 | 5.6 | Slight right skew | Low baseline stress, some high-stress days |
| Body Battery Avg | 45.0 | 44.6 | 14.6 | Roughly symmetric | Wide spread reflects large intraday swings |
| SpO2 Avg (%) | 93.8 | 93.9 | 0.7 | Tight cluster | Very little variation day-to-day |
| Respiration (br/min) | 12.6 | 12.4 | 0.6 | Possibly bimodal | Peaks near 12.2 and 14.2 — may reflect sleep vs wake patterns |
| HRV Nightly (ms) | 57.8 | 61.0 | 11.8 | Left skew | Median > mean suggests low-HRV outlier days pulling down |
| Sleep Score | 69.5 | 72.5 | 15.8 | Left skew | Median > mean; a few bad nights drag the average down |
| Skin Temp Dev (C) | -0.0 | -0.1 | 0.3 | Centered at 0 | Deviation from baseline, as expected |

### Key Observations
1. **Respiration may be bimodal** — the distribution shows two peaks. If confirmed, reporting a single average is misleading. Should investigate whether the two modes correspond to sleep vs awake breathing rates.
2. **HRV is left-skewed** — median (61) is higher than mean (57.8). A few low-HRV nights are dragging the average down. Median is more representative for this metric.
3. **SpO2 has very low variance** (sd=0.7) — daily averages barely move. The interesting analysis for SpO2 is in the *minimums*, not the averages. A day with avg 94% but min 78% is very different from avg 94% min 92%.
4. **Sleep Score is left-skewed** like HRV — median (72.5) > mean (69.5). Both are overnight recovery metrics that share this pattern: a few bad nights pull the mean down while the typical night is better than the average suggests.
5. **Body Battery has the widest relative spread** (sd=14.6 on mean 45.0, CV=32%). This is expected — body battery swings heavily intraday (drains during activity, recharges during rest). The daily average captures the center of that swing.

---

## Visualization Status (from chart inspection)

### IQR Bands — Implemented and Validated
The min/max band readability problem has been fixed. All applicable dashboard panels now use IQR (25th-75th percentile) bands. Quantitative comparison for Heart Rate:
- **Old (min/max):** Band = 135 bpm, avg variation = 16 bpm, **ratio: 8.3x** — average looked flat
- **New (IQR):** Band = 33 bpm, avg variation = 16 bpm, **ratio: 2.0x** — average trend clearly visible

The actual IQR ratio (2.0x) is better than the pre-implementation estimate (3.7x). IQR bands now used on: Heart Rate, Stress, Body Battery, SpO2, Respiration.

### Charts That Work Well
- **HRV:** Nightly avg + weekly avg (two lines, no bands) — clean, shows real variability
- **Skin Temp:** Deviation + 7-day smoothed + zero reference line — good use of smoothing
- **SpO2:** Avg + min line + IQR band + 90% concern threshold — combines trend with clinically relevant context
- **Body Battery:** IQR band with daily avg — wide daily swings are well captured by the band
- **Respiration:** IQR band + 14 br/min "elevated" reference line — provides context for the bimodal distribution
- **Sleep Score:** Raw daily values + 7-day rolling average — smoothing reveals trends hidden by day-to-day volatility

---

## Cross-Metric Correlations

Pearson correlations computed across all available days. Strong correlations (|r| > 0.5) form two coherent clusters.

### Recovery Cluster (positively correlated with each other)
| Pair | r | Interpretation |
|------|---|----------------|
| Body Battery ↔ HRV Nightly | **0.85** | Higher body battery on nights with higher HRV |
| HRV Nightly ↔ Sleep Score | **0.75** | Better HRV predicts better sleep scores |
| Body Battery ↔ Sleep Score | **0.64** | Recovery metrics move together |

### Stress Cluster (inversely correlated with recovery)
| Pair | r | Interpretation |
|------|---|----------------|
| Respiration ↔ HRV Nightly | **-0.87** | Strongest correlation — elevated breathing rate tracks with suppressed HRV |
| Stress ↔ Body Battery | **-0.78** | Higher stress days drain body battery |
| Body Battery ↔ Respiration | **-0.71** | Elevated respiration on low-battery days |
| Stress ↔ HRV Nightly | **-0.65** | Stress suppresses overnight HRV |
| HR Avg ↔ Stress | **0.73** | Higher average HR on higher stress days |
| Stress ↔ Sleep Score | **-0.55** | High-stress days precede worse sleep |
| HR Avg ↔ Body Battery | **-0.57** | Higher HR associated with lower recovery |
| Respiration ↔ Sleep Score | **-0.62** | Elevated respiration tracks with worse sleep |

### Weakly Correlated: SpO2
SpO2 shows no strong correlation with any other metric (all |r| < 0.5). This is consistent with its very low daily variance (sd=0.7) — there isn't enough signal to correlate.

### Key Takeaway
The data tells a consistent physiological story: stress, elevated HR, and elevated respiration form one axis; HRV, body battery, and sleep score form the opposing recovery axis. Respiration ↔ HRV (-0.87) is the single strongest link, suggesting respiration rate may be the most sensitive daily indicator of autonomic stress load.

---

## Heart Rate Analysis Features

Five analysis views were added to the heart rate tab, moving beyond simple daily averages into physiologically meaningful patterns.

### Resting HR Trend (7-Day Moving Average)
Raw daily resting HR overlaid with a trailing 7-day moving average. The MA smooths out day-to-day noise (e.g., a single bad night) so gradual drift becomes visible. A sustained upward MA trend — even 2-3 bpm over two weeks — can indicate overtraining, accumulated stress, or the early stages of illness, often days before subjective symptoms appear.

### HR Distribution (per-day histogram)
Each day's ~1800 HR readings bucketed into 5-bpm bins. Shape tells the story: a unimodal cluster around 55-65 bpm is a quiet day; a bimodal distribution with a second peak at 120+ reveals a distinct exercise bout. Wide, flat distributions indicate constant mode-switching. Comparing histograms across days reveals behavioral patterns invisible to a single "avg HR" number.

### Circadian HR Profile
Average HR for each hour (0-23) aggregated across the entire data period. The characteristic U-shaped curve — nadir at 3-5 AM (deep sleep), rise through the morning, plateau at midday, gradual decline in the evening — reflects the body's circadian autonomic rhythm. Changes in the curve's shape (e.g., an elevated overnight floor, a blunted morning rise) can indicate disrupted sleep patterns, shift changes, or chronic stress.

### Sleeping HR Trend
Average HR during actual sleep stages (light, deep, REM), with awake periods excluded. Uses cross-date correlation: sleep data for date D spans the evening of D-1 through the morning of D, so HR readings from both dates are matched against sleep-stage timestamps. This yields the purest resting signal — unlike "resting HR" which can include sitting at a desk, sleeping HR removes all waking physiology. A rising sleeping HR trend warrants attention even if daytime metrics look normal.

### Weekly Resting HR Boxplot
Five-number summary (min, Q1, median, Q3, max) of daily resting HR grouped by ISO week. Visualized as filled bands with a bold median line. Shows both the central tendency and *variability* of resting HR within each week. A tightening box (Q1 and Q3 converging) means the body is settling into a consistent rhythm; a widening box suggests disrupted recovery patterns. Comparing median lines across weeks provides the clearest long-term resting HR trend.

---

## Undocumented Data Sources (not yet parsed)

### SLEEP_DISRUPTIONS
Discovered: `sleep_disruption_overnight_severity_mesgs` with severity enum (none, low) and `sleep_disruption_severity_period_mesgs` with per-period breakdowns. Could add value to sleep analysis.

### NAP
A `NAP` file type exists in some days. Not yet explored.

### METRICS (14+ unknown message types)
Training metrics files contain 14+ undocumented message types (IDs: 232, 241, 281, 284, 294, 330, 339, 356, 357, 369, 378, 384, 402, 403, 404, 410). Type 369 has 30 fields — likely a comprehensive training summary. Type 403 may contain VO2 max data (values ~5686 which could be 56.86 mL/kg/min scaled by 100). Worth investigating when training analysis is needed.

### Product implication
Current parsed signals are strong enough for a recovery-first assistant: sleep, HRV, resting HR, stress, body battery, respiration, routines, and check-ins can support useful day-to-day guidance. They are not yet strong enough for confident workout-performance attribution, because the richer training summary layer is still largely undocumented.

### Routine runtime implication
The product now has a cleaner boundary for manual interventions and future assistant planning: routines are represented as structured card and schedule specs that compile into live runtime records. That makes mindfulness, mobility, and core work extensible without schema churn, while keeping experiments intentionally paused until they can reference the same runtime cleanly.
Today is now execution-only in its public contract: it logs outcomes against scheduled occurrences. The projection still honors previously persisted date-specific overrides for backward compatibility, but new schedule exceptions are deferred until a dedicated schedule-management flow exists.

### Raw Sensor Data
- Unknown type 233 in WELLNESS (~185 records/file) — possibly raw sensor data
- Unknown type 397 in SKIN_TEMP (~1500 records/file) — likely continuous overnight temperature samples

---

## Open Questions

1. ~~Why is SpO2 missing for 16% of days?~~ **Resolved:** sensor was recently enabled; early days predate activation.
2. Is the respiration bimodality real (sleep vs wake) or an artifact of the daily aggregation method?
3. Can we reconstruct per-reading timestamps for HR data? `monitoring_info_mesgs` contains a base timestamp that may allow decompressing `timestamp_16` offsets.
4. What are the METRICS file message types? Correlating with Garmin Connect API data could decode them.
5. What does the raw sensor data in type 233 contain? At ~185 records per WELLNESS file, it's substantial.
