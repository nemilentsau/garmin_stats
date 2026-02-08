# Garmin FIT File Analysis Findings

This document tracks discoveries from analyzing Garmin Epix Gen 2 FIT file exports.

**SDK Used:** Official Garmin FIT SDK (`garmin-fit-sdk>=21.188.0`)

---

## Data Structure Overview

### File Organization

Garmin exports health data into **date-based directories** (e.g., `2026-01-14/`) containing multiple FIT files per day.

**File Types (per day):**

| Type | Files/Day | Size/Day | Primary Data |
|------|-----------|----------|--------------|
| WELLNESS | 5-7 | ~75-80 KB | Activity, HR, stress, SpO2, respiration |
| METRICS | 4-8 | ~2-4 KB | Training metrics (mostly undocumented) |
| SKIN_TEMP | 1 | ~12-13 KB | Skin temperature readings |
| SLEEP_DATA | 1 | ~0.8-0.9 KB | Sleep stages and assessment |
| SLEEP_DISRUPTIONS | 1 | ~0.4 KB | Sleep interruptions |
| HRV_STATUS | 1 | ~0.8-1.2 KB | Heart rate variability |

### Why Multiple WELLNESS Files Per Day?

WELLNESS files are **sequential time chunks** covering the 24-hour period. The watch splits files when syncing or when internal buffers fill up.

---

## Message Types - Complete Inventory

### WELLNESS Files (Primary Health Data)

| Message Type | Records/Day | Fields | Description |
|--------------|-------------|--------|-------------|
| `monitoring_mesgs` | ~1,800 | 18 | Core activity data |
| `stress_level_mesgs` | ~1,400 | 2+ | Stress measurements |
| `respiration_rate_mesgs` | ~1,400 | 2 | Breathing rate |
| `spo2_data_mesgs` | ~1,100 | 4 | Blood oxygen (SpO2) |
| `event_mesgs` | ~260 | 8 | Activity events |
| `monitoring_hr_data_mesgs` | ~11 | 3 | Resting heart rate |
| `ohr_settings_mesgs` | ~11 | 2 | Optical HR settings |
| `monitoring_info_mesgs` | 6 | 6 | File metadata |

### SLEEP_DATA Files

| Message Type | Records | Fields | Description |
|--------------|---------|--------|-------------|
| `sleep_level_mesgs` | ~15/night | 2 | Sleep stages (awake, light, deep, REM) |
| `sleep_assessment_mesgs` | 1/night | 10 | Sleep quality scores |
| `event_mesgs` | 2 | - | Sleep start/end markers |

### HRV_STATUS Files

| Message Type | Records | Fields | Description |
|--------------|---------|--------|-------------|
| `hrv_value_mesgs` | ~58/night | 2 | Raw HRV values during sleep |
| `hrv_status_summary_mesgs` | 1 | 8 | HRV baseline and status |

### SKIN_TEMP Files

| Message Type | Records | Fields | Description |
|--------------|---------|--------|-------------|
| `skin_temp_overnight_mesgs` | 1 | 5 | Nightly skin temp summary |
| `unknown_397` | ~1,400 | 2 | Raw temp readings (undocumented) |

### SLEEP_DISRUPTIONS Files

| Message Type | Records | Fields | Description |
|--------------|---------|--------|-------------|
| `sleep_disruption_severity_period_mesgs` | ~6/night | 3 | Disruption periods |
| `sleep_disruption_overnight_severity_mesgs` | 1 | 2 | Overall severity |

### METRICS Files (Mostly Undocumented)

METRICS files contain **training and fitness metrics** but are almost entirely undocumented even in the official Garmin FIT SDK.

**Named message types (metadata only):**
- `file_id_mesgs` - File identification
- `file_creator_mesgs` - Software version
- `device_info_mesgs` - Device details

**Unknown message types (16 total):**

| ID | Records | Fields | Possible Content (speculative) |
|----|---------|--------|-------------------------------|
| 369 | ~11 | 30 | Training status summary (most fields of any message) |
| 403 | ~7 | 12 | VO2 max data (values like 5686 ≈ 56.86 mL/kg/min) |
| 339 | ~10 | 6 | Training load (values in thousands) |
| 281 | ~10 | 9 | Recovery metrics |
| 241 | ~17 | 3 | Timestamps/sync data |
| 404 | ~14 | 4 | Goal tracking? (values like 10000 = step goal?) |
| 357 | ~7 | 4 | Training readiness? (percentage values 95-98) |
| 378 | ~7 | 7 | HR zones? (values include 42, 220 - VO2max, max HR) |
| 356 | ~7 | 7 | Performance metrics |
| 410 | ~7 | 9 | Training effect? |
| 294 | ~7 | 11 | Large numeric values - cumulative stats |
| 232 | ~7 | 5 | Status flags |
| 402 | ~7 | 4 | Binary flags (0/1/2 values) |
| 284 | ~7 | 6 | HR-related (includes value 2359 ≈ HR zones?) |
| 330 | ~3 | 4 | Session markers |
| 384 | ~3 | 26 | Comprehensive session summary |

**Note:** These speculations are based on analyzing sample values. Reverse engineering would require correlating with Garmin Connect data to confirm meanings.

---

## Field Details by Message Type

### `monitoring_mesgs` (Activity Monitoring)

| Field | Type | Description |
|-------|------|-------------|
| `timestamp` | datetime | Record time |
| `heart_rate` | int | Current HR (bpm) |
| `activity_type` | enum | sedentary, walking, running, generic |
| `intensity` | int | 0-7 activity intensity |
| `steps` | int | Step count |
| `cycles` | float | Arm movements/steps |
| `active_calories` | int | Calories burned |
| `active_time` | float | Active seconds |
| `distance` | float | Distance (meters) |
| `ascent` | float | Elevation gain (meters) |
| `descent` | float | Elevation loss (meters) |
| `moderate_activity_minutes` | int | Moderate intensity time |
| `vigorous_activity_minutes` | int | Vigorous intensity time |
| `duration_min` | int | Duration metric |
| `current_activity_type_intensity` | tuple | Packed value |
| `timestamp_16` | int | 16-bit timestamp offset |

### `stress_level_mesgs`

| Field | Type | Description |
|-------|------|-------------|
| `stress_level_time` | datetime | Measurement time |
| `stress_level_value` | int | Stress score (0-100, -1/-2 = invalid) |

### `respiration_rate_mesgs`

| Field | Type | Description |
|-------|------|-------------|
| `timestamp` | datetime | Measurement time |
| `respiration_rate` | float | Breaths per minute (-1 = invalid) |

### `spo2_data_mesgs`

| Field | Type | Description |
|-------|------|-------------|
| `timestamp` | datetime | Measurement time |
| `reading_spo2` | int | SpO2 percentage (0-100) |
| `reading_confidence` | int | Confidence score |
| `mode` | enum | periodic, on_demand |

### `monitoring_hr_data_mesgs`

| Field | Type | Description |
|-------|------|-------------|
| `timestamp` | datetime | Record time |
| `resting_heart_rate` | int | Current resting HR |
| `current_day_resting_heart_rate` | int | Daily resting HR |

### `sleep_level_mesgs`

| Field | Type | Description |
|-------|------|-------------|
| `timestamp` | datetime | Stage start time |
| `sleep_level` | enum | awake, light, deep, rem |

### `sleep_assessment_mesgs`

| Field | Type | Description |
|-------|------|-------------|
| `overall_sleep_score` | int | Total sleep score |
| `deep_sleep_score` | int | Deep sleep quality |
| `light_sleep_score` | int | Light sleep quality |
| `rem_sleep_score` | int | REM sleep quality |
| `awake_time_score` | int | Time awake score |
| `awakenings_count` | int | Number of awakenings |
| `awakenings_count_score` | int | Awakenings score |
| `interruptions_score` | int | Interruptions score |
| `average_stress_during_sleep` | int | Sleep stress |
| `combined_awake_score` | int | Combined awake score |

### `hrv_status_summary_mesgs`

| Field | Type | Description |
|-------|------|-------------|
| `timestamp` | datetime | Summary time |
| `weekly_average` | float | 7-day HRV average |
| `last_night_average` | float | Last night's HRV |
| `last_night_5_min_high` | float | Peak 5-min HRV |
| `baseline_low_upper` | float | Low baseline threshold |
| `baseline_balanced_lower` | float | Balanced range lower |
| `baseline_balanced_upper` | float | Balanced range upper |
| `status` | enum | HRV status |

### `skin_temp_overnight_mesgs`

| Field | Type | Description |
|-------|------|-------------|
| `timestamp` | datetime | Record time |
| `local_timestamp` | datetime | Local time |
| `nightly_value` | float | Overnight temp |
| `average_deviation` | float | Deviation from baseline |
| `average_7_day_deviation` | float | 7-day avg deviation |

---

## Activity Type Distribution (3 days)

| Activity | Count | Percentage |
|----------|-------|------------|
| sedentary | 1,101 | 73.2% |
| walking | 305 | 20.3% |
| generic | 74 | 4.9% |
| running | 25 | 1.7% |

---

## Unknown Message Types

Still undocumented (numeric IDs):

| ID | Records | Likely Purpose |
|----|---------|----------------|
| 233 | 4,247 | High frequency - possibly raw sensor data |
| 397 | 4,174 | In SKIN_TEMP - raw temperature readings |
| 279 | 2,160 | Moderate frequency |
| 24 | 611 | Lower frequency |
| Others | <100 | Various training/body metrics |

---

## Key Insights

1. **Rich biometric data**: SpO2, respiration rate, HRV, skin temp all tracked continuously
2. **Sleep analysis**: Detailed sleep stages + quality scores + disruption tracking
3. **Activity intensity**: 8-level scale (0-7) for activity classification
4. **HR sampling**: ~1-2 minute intervals throughout day, but uses compressed `timestamp_16` (not full `timestamp`)
5. **Stress tracking**: Continuous throughout day with quality indicators
6. **Skin temp deviation**: Reported as deviation from personal baseline, not absolute temperature. 7-day smoothed average useful for trend detection.
7. **HR timestamp caveat**: `monitoring_mesgs` with `heart_rate` use `timestamp_16` (16-bit compressed offset), NOT the standard `timestamp` field. You cannot extract per-reading timestamps without decoding the compressed format. For daily aggregation, group by the date directory the file lives in.

---

## Change Log

| Date | Finding |
|------|---------|
| 2026-01-19 | Switched to official Garmin FIT SDK |
| 2026-01-19 | Discovered respiration_rate, spo2_data, hrv_value messages |
| 2026-01-19 | Documented sleep_assessment with 10 quality metrics |
| 2026-01-19 | Documented skin_temp_overnight with deviation tracking |
| 2026-01-19 | Reduced unknown message types from ~20 to ~10 |
| 2026-01-19 | Analyzed METRICS files - 16 undocumented message types for training data |
| 2026-01-19 | Added speculative field mappings for METRICS based on sample values |
| 2026-02-08 | Discovered HR monitoring_mesgs use timestamp_16, not timestamp — breaks naive timestamp grouping |
| 2026-02-08 | Confirmed skin_temp_overnight_mesgs: 1 per night, deviation-based, 7-day smoothed average included |
