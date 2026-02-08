---
name: garmin-data
description: Garmin FIT file data dictionary — schemas, parsing patterns, and data contracts for health metrics
version: 1.1.0
---

# Garmin Data Analysis Skill

You are a data analyst working with Garmin wearable health data stored in FIT (Flexible and Interoperable Data Transfer) files. This skill gives you documented schemas for all known FIT structures and tools to verify and extend them.

## When to Explore vs When to Trust Schemas

**Trust the schemas** for message types and fields already documented in `references/`. Do not waste tokens re-decoding files for information that's already captured.

**Run the verify script** when:
- Code breaks unexpectedly (SDK update? firmware change?)
- You get unexpected null values or wrong types
- After upgrading `garmin-fit-sdk`

**Run the discover script** when:
- You need a metric not yet in the schemas
- A new FIT file type appears (e.g., NAP files)
- The verify script reports DRIFT
- You want to explore undocumented message types (e.g., METRICS files)

**Update the reference schemas** whenever you learn something new. Schemas are living documents — they should grow as the project grows.

## Scripts

Run from `backend/` directory:

```bash
# Verify schemas match real data (run after SDK upgrades or when things break)
uv run python ../.claude/skills/garmin-data/scripts/verify_schemas.py

# Discover all file types and message types (overview)
uv run python ../.claude/skills/garmin-data/scripts/discover_fields.py --all

# Discover fields for a specific file type
uv run python ../.claude/skills/garmin-data/scripts/discover_fields.py --file-type METRICS

# Discover a specific message type
uv run python ../.claude/skills/garmin-data/scripts/discover_fields.py --file-type WELLNESS --message 233
```

## Data Source

FIT files from a Garmin watch, organized on disk as `data/YYYY-MM-DD/*.fit`. Files are named `{garmin_timestamp}_{TYPE}.fit`.

## FIT File Types

| Type | Files/Day | Status | Description |
|------|-----------|--------|-------------|
| WELLNESS | 5-7 | Parsed | Activity, HR, stress, SpO2, respiration (sequential time chunks) |
| SLEEP_DATA | 1 | Parsed | Sleep stages and quality assessment |
| HRV_STATUS | 1 | Parsed | Heart rate variability (overnight) |
| SKIN_TEMP | 1 | Parsed | Skin temperature deviation (overnight) |
| METRICS | 4-8 | Not parsed | Training metrics (14+ unknown message types, ~30 fields each) |
| SLEEP_DISRUPTIONS | 1 | Not parsed | Sleep disruption severity (overnight_severity, period_severity) |
| NAP | rare | Not parsed | Nap data (discovered, not yet documented) |

## Message Type Quick Reference

Before writing any parser code, consult the schema files in `references/`:

- **`references/wellness-messages.json`** — monitoring_mesgs, stress_level_mesgs, spo2_data_mesgs, respiration_rate_mesgs, monitoring_hr_data_mesgs + acknowledged unknowns
- **`references/sleep-messages.json`** — sleep_level_mesgs, sleep_assessment_mesgs + event_mesgs + unknowns
- **`references/hrv-messages.json`** — hrv_value_mesgs, hrv_status_summary_mesgs
- **`references/skin-temp-messages.json`** — skin_temp_overnight_mesgs + unknown_397 (~1500 raw temp readings)
- **`references/sleep-disruptions-messages.json`** — sleep_disruption_overnight_severity_mesgs, sleep_disruption_severity_period_mesgs
Each schema file documents:
- Field names, types, units, scale factors, valid ranges
- Filtering rules (what to discard)
- Gotchas specific to that message type
- `"extracted": false` for fields present in data but not yet used by parsers
- `"rare": true` for fields that don't appear in every file
- `"status": "not_parsed"` for acknowledged but unused message types
- `"fields_undocumented"` for numeric SDK field IDs with unknown meaning

## Critical Data Rules

1. **HR has no usable timestamps.** Heart rate in `monitoring_mesgs` uses `timestamp_16` (compressed 16-bit offset), NOT `timestamp`. The `timestamp` field is `None` for HR entries. Group HR data by the file's parent directory date, not by timestamp.

2. **Multiple WELLNESS files per day.** The watch splits WELLNESS data into sequential time chunks (5-7 files). Always iterate ALL files for a given day.

3. **Skin temp is deviation, not absolute.** `average_deviation` and `average_7_day_deviation` are offsets from a personal baseline in Celsius. `nightly_value` is the absolute temperature.

4. **HRV values use scale 128.** The SDK auto-scales, but raw values in the FIT profile are divided by 128 to get milliseconds.

5. **Stress uses a non-standard timestamp field.** Stress messages use `stress_level_time`, not `timestamp`.

6. **Filtering rules:**
   - HR: `heart_rate > 0` (zero = no reading)
   - Stress: `stress_level_value >= 0` (negative = invalid: -1 unknown, -2 calculating)
   - Respiration: `respiration_rate > 0` (negative = invalid: -300 invalid, -200 motion, -100 off-wrist)
   - SpO2: `reading_spo2` truthy (0 = no reading)
   - HRV: `value` truthy (0 = no reading)

## Parsing Pattern

All parsers follow this pattern:
```python
def parse_X_data(data_dir: Path, date: str | None = None) -> dict:
    files_by_day = get_files_by_day(data_dir)
    # Filter to requested date if provided
    # Iterate files, decode with decode_fit_file()
    # Extract fields per schema, apply filters
    # Return { days: [...], metric_name: [...] }
```

## When Adding New Metrics

1. Check `references/` schemas first — the field may already be documented (possibly with `"extracted": false`)
2. If the field isn't there, run the discover script: `uv run python ../.claude/skills/garmin-data/scripts/discover_fields.py --file-type <TYPE> --message <MSG>`
3. Add the discovered fields to the appropriate reference JSON
4. Write the parser code using the documented field names and filter rules
5. Run the verify script to confirm the schema matches: `uv run python ../.claude/skills/garmin-data/scripts/verify_schemas.py`
6. If adding a new endpoint, regenerate TypeScript types: `bash scripts/generate-api-types.sh`
