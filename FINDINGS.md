# Garmin Health Data — Analysis Findings

Data schemas and field documentation live in `.claude/skills/garmin-data/references/`. This file is for **analytical observations** — what the data tells us, not how it's structured.

**Device:** Garmin Epix Gen 2 Pro | **Period:** 2026-01-01 to 2026-02-06 (~37 days) | **SDK:** garmin-fit-sdk 21.188.0

---

## Data Quality

### Missingness
- **SpO2: 16% missing days** (6 of 37). **Explained:** SpO2 sensor was recently enabled — early days in the dataset predate activation. Not a sensor failure. The remaining values cluster tightly (92.5-95.5%, sd=0.7).
- **HRV: 3% missing** (1 day). Likely device not worn overnight.
- **Skin Temp: 3% missing** (1 day). Same likely cause.
- **HR, Stress, Respiration: 0% missing.** Complete coverage across all 37 days.

### Sensor Artifacts
- HR min values dip to ~40 bpm on some days — could be legitimate resting HR during deep sleep, or sensor artifact during low-motion periods. Worth cross-referencing with sleep stages.
- HR max hits 160+ bpm — likely exercise peaks. Not artifacts, but they dominate min/max visualizations.

---

## Distribution Observations (from EDA)

| Metric | Mean | Median | SD | Shape | Notes |
|--------|------|--------|-----|-------|-------|
| HR Avg (bpm) | 64.3 | 64.3 | 3.3 | Normal, symmetric | Mean = median, safe to use mean |
| Stress Avg | 28.6 | 28.0 | 5.6 | Slight right skew | Low baseline stress, some high-stress days |
| SpO2 Avg (%) | 93.8 | 93.9 | 0.7 | Tight cluster | Very little variation day-to-day |
| Respiration (br/min) | 12.6 | 12.4 | 0.6 | Possibly bimodal | Peaks near 12.2 and 14.2 — may reflect sleep vs wake patterns |
| HRV Nightly (ms) | 58.3 | 61.0 | 12.4 | Left skew | Median > mean suggests low-HRV outlier days pulling down |
| Skin Temp Dev (C) | -0.0 | -0.1 | 0.4 | Centered at 0 | Deviation from baseline, as expected |

### Key Observations
1. **Respiration may be bimodal** — the distribution shows two peaks. If confirmed, reporting a single average is misleading. Should investigate whether the two modes correspond to sleep vs awake breathing rates.
2. **HRV is left-skewed** — median (61) is higher than mean (58.3). A few low-HRV nights are dragging the average down. Median is more representative for this metric.
3. **SpO2 has very low variance** (sd=0.7) — daily averages barely move. The interesting analysis for SpO2 is in the *minimums*, not the averages. A day with avg 94% but min 78% is very different from avg 94% min 92%.

---

## Visualization Issues (from chart inspection)

### Min/Max Bands Are Hiding the Signal
Visual inspection of the dashboard charts confirmed the problem quantitatively:
- **Heart Rate:** Min/max band spans 135 bpm (40-175). Average line varies only 16 bpm. **Ratio: 8.3x** — the average looks flat.
- **Stress:** Min/max band spans 0-100 (full scale). Average hovers around 28. The band makes the entire chart useless.
- **Respiration:** Same problem. Band width dwarfs average variation.

**Fix needed:** Replace min/max bands with IQR (25th-75th percentile) bands. Estimated IQR approach reduces the ratio to ~3.7x for HR, making the average trend readable.

### Charts That Work Well
- **HRV:** Nightly avg + weekly avg (two lines, no bands) — clean, shows real variability
- **Skin Temp:** Deviation + 7-day smoothed + zero reference line — good use of smoothing
- **SpO2:** Avg + min line + 90% threshold — the threshold reference line adds real value

---

## Undocumented Data Sources (not yet parsed)

### SLEEP_DISRUPTIONS
Discovered: `sleep_disruption_overnight_severity_mesgs` with severity enum (none, low) and `sleep_disruption_severity_period_mesgs` with per-period breakdowns. Could add value to sleep analysis.

### NAP
A `NAP` file type exists in some days. Not yet explored.

### METRICS (14+ unknown message types)
Training metrics files contain 14+ undocumented message types (IDs: 232, 241, 281, 284, 294, 330, 339, 356, 357, 369, 378, 384, 402, 403, 404, 410). Type 369 has 30 fields — likely a comprehensive training summary. Type 403 may contain VO2 max data (values ~5686 which could be 56.86 mL/kg/min scaled by 100). Worth investigating when training analysis is needed.

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
