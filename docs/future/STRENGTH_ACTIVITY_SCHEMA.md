# Strength Activity Schema

> Status: proposed parser/read-model schema, based on the downloaded activity FIT
> files in `data/garmin_activities/` as of 2026-06-28.

This schema is the strength-specific extension of the broader activity-session
mart described in `ACTIVITY_ANALYTICS_DESIGN.md`.

It keeps two product grains separate:

- one row per strength session
- one row per timestamped record sample

The session row should be the first implementation target. It is consistently
populated and already supports daily load, duration, calorie, heart-rate, and
experiment-adherence joins. The timestamped record row is useful for HR-response
analysis, but should not block session-level features.

Garmin also emits `set_mesgs`, exercise-set endpoint rows, and rep counters.
Those are source diagnostics only for this project. The user does not track
exercises/reps in Garmin, and Garmin's inferred reps/exercise categories are not
reliable enough to become product-facing strength metrics.

## Observed Coverage

Strength files inspected:

- `180` strength-training FIT files
- `180` session summaries
- `180` files with timestamped record traces
- `180` files with heart-rate data
- `180` files with `set_mesgs`
- `0` files with lap/split data

Decoded strength kind:

| Kind | Files |
| --- | ---: |
| `training_strength_training` | 180 |

Set-message shape:

| Set messages per file | Files |
| ---: | ---: |
| 1 | 179 |
| 3 | 1 |

The practical consequence is important: these files do not preserve a useful
"exercise -> set -> reps -> weight" gym log. Almost every activity has one
active set spanning the whole workout, with Garmin-inferred repetition counts
and probabilistic exercise-category guesses. One activity has two active set
messages plus one rest message.

Garmin Connect's `get_activity_exercise_sets(activity_id)` endpoint returns the
same set grain as the FIT `set_mesgs`: `duration`, `repetitionCount`, `weight`,
`setType`, `startTime`, `messageIndex`, and a list of candidate exercise
categories with probabilities. In the sampled activities, exercise `name` is
null and `weight` is usually null.

## What The Data Can Support

Reliable now:

- strength session count per day
- duration, elapsed time, and timer time
- calories
- average and max heart rate
- full heart-rate trace during the session
- Garmin aerobic and anaerobic training effect
- Garmin training load
- HR time in zones

Not reliable from the current files:

- total reps as a training metric
- exact exercise names
- per-exercise set boundaries
- per-set weight
- precise rest intervals for most sessions
- lifted volume or tonnage
- muscle-group load without manual enrichment

The `category` candidates in `set_mesgs` should be treated as low-confidence
classifier output, not as user-entered exercise labels.

## Unit Policy

The backend owns all unit normalization. The frontend should receive
display-ready units and should not compute load, rep totals, or HR-zone
durations.

| Concept | Canonical field/unit | Source note |
| --- | --- | --- |
| Duration | seconds | FIT `total_timer_time`, `total_elapsed_time`, set `duration` |
| Heart rate | beats per minute | FIT session and record messages; present in all inspected strength files |
| Calories | kilocalories | FIT `total_calories` / JSON `calories` |
| Training effect | Garmin scalar | FIT `total_training_effect`, `total_anaerobic_training_effect` |
| Training load | Garmin scalar | FIT `training_load_peak` / JSON `activityTrainingLoad` |
| HR-zone time | seconds per zone | FIT `time_in_zone_mesgs.time_in_hr_zone` |

## `StrengthActivitySession`

One row per strength-training activity FIT file.

Recommended Python contract:

```python
class StrengthActivitySession(BaseModel):
    id: str
    activity_id: str | None
    source_file: str
    source_date_dir: str | None
    local_date: str

    start_time_local: str
    start_time_utc: str | None
    end_time_local: str | None
    elapsed_time_s: float | None
    timer_time_s: float | None
    moving_time_s: float | None

    sport: str
    sub_sport: str
    sport_profile_name: str | None
    activity_name: str | None

    total_calories: int | None

    avg_heart_rate_bpm: int | None
    max_heart_rate_bpm: int | None
    has_heart_rate: bool

    aerobic_training_effect: float | None
    anaerobic_training_effect: float | None
    training_load: float | None

    hr_zone_seconds: list[float] | None
    hr_zone_boundaries_bpm: list[int] | None
    hr_zone_calc_type: str | None

    event_count: int
    record_count: int
    has_records: bool
    has_garmin_set_diagnostics: bool

    source_summary: dict
```

### Session Source Mapping

| Field | Primary source |
| --- | --- |
| `activity_id` | JSON sidecar `activityId` |
| `activity_name` | JSON sidecar `activityName` |
| `start_time_local` | JSON sidecar `startTimeLocal` |
| `start_time_utc` | FIT `session_mesgs.start_time` or JSON `startTimeGMT` |
| `elapsed_time_s` | FIT `session_mesgs.total_elapsed_time` / JSON `elapsedDuration` |
| `timer_time_s` | FIT `session_mesgs.total_timer_time` / JSON `duration` |
| `moving_time_s` | JSON sidecar `movingDuration` |
| `total_calories` | FIT `session_mesgs.total_calories` / JSON `calories` |
| `avg_heart_rate_bpm` | FIT `session_mesgs.avg_heart_rate` / JSON `averageHR` |
| `max_heart_rate_bpm` | FIT `session_mesgs.max_heart_rate` / JSON `maxHR` |
| `aerobic_training_effect` | FIT `session_mesgs.total_training_effect` / JSON `aerobicTrainingEffect` |
| `anaerobic_training_effect` | FIT `session_mesgs.total_anaerobic_training_effect` / JSON `anaerobicTrainingEffect` |
| `training_load` | FIT `session_mesgs.training_load_peak` / JSON `activityTrainingLoad` |
| `hr_zone_seconds` | FIT `time_in_zone_mesgs` with `reference_mesg == "session"` |

## `StrengthActivityRecord`

One row per timestamped record sample.

The record trace is useful for HR-response analysis, but it is much heavier than
session rows. It should not block session-level strength features.

```python
class StrengthActivityRecord(BaseModel):
    session_id: str
    timestamp_utc: str
    timestamp_local: str | None
    elapsed_time_s: float | None

    heart_rate_bpm: int | None
    distance_m: float | None

    source_fields: dict
```

Observed record fields are sparse and partly undocumented. All 180 strength
files have `timestamp`, `heart_rate`, `distance`, and numeric FIT fields `135`,
`136`, `141`, and `143`. Keep the unknown numeric fields in `source_fields`
until they are decoded against the FIT profile or shown to support a useful
question.

## Daily Feature Candidates

For experiment and recovery joins, start from daily session-level features:

```python
class StrengthDailyFeatures(BaseModel):
    local_date: str

    strength_session_count: int
    strength_timer_time_total_s: float
    strength_elapsed_time_total_s: float
    strength_calories_total: int

    strength_training_load_total: float | None
    strength_aerobic_effect_max: float | None
    strength_anaerobic_effect_max: float | None

    strength_avg_hr_weighted_bpm: float | None
    strength_max_hr_bpm: int | None
    strength_hr_zone_seconds_total: list[float] | None

    strength_has_hr: bool
    strength_has_record_trace: bool
```

Recommended first backend features:

- `strength_session_count`
- `prev_day_strength_session_flag`
- `strength_timer_time_total_s`
- `strength_training_load_total`
- `strength_avg_hr_weighted_bpm`
- `strength_max_hr_bpm`
- `strength_hr_zone_seconds_total`

Avoid rep, exercise, muscle-group, and lifted-volume features unless a future
data source captures them manually or at a trustworthy grain.

## Garmin Set Diagnostics

Do not expose these as stable product metrics in V1:

```python
class StrengthGarminSetDiagnostic(BaseModel):
    session_id: str
    message_index: int | None
    set_type: str | None
    duration_s: float | None
    inferred_repetition_count: int | None
    inferred_weight: float | None
    candidate_categories: list[str]
    candidate_probabilities_pct: list[float]
    source_summary: dict
```

This diagnostic shape is mainly useful for parser auditing:

- confirming that `totalSets` / `activeSets` do not imply reliable set rows
- checking whether a future watch firmware starts emitting better strength data
- preserving raw context if a future analysis asks why Garmin counted an
  unusually high or low number of reps

## Data Quality Flags

Persist these flags with the session row so downstream analysis can filter
without re-decoding FIT files:

| Flag | Meaning |
| --- | --- |
| `has_heart_rate` | session or records include HR |
| `has_records` | timestamped trace exists |
| `has_garmin_set_diagnostics` | FIT set messages exist, but they are not trusted as exercise logs |
| `garmin_reps_ignored` | Garmin rep counters exist and were deliberately excluded from product metrics |
| `garmin_exercise_categories_ignored` | Garmin category guesses exist and were deliberately excluded from product metrics |

## Implementation Notes

- Parse session rows from FIT plus JSON sidecars first.
- Treat JSON `totalSets`, `activeSets`, and `totalReps` as Garmin Connect
  summary artifacts, not as strength-training features.
- Skip Garmin Connect exercise-set enrichment for V1. It requires extra API
  calls and returns mostly the same unreliable grain as `set_mesgs` in the
  sampled files.
- If set messages are persisted at all, keep them under a diagnostic/raw-source
  name rather than a product-facing `ExerciseSet` model.
- Preserve unknown FIT record fields in a raw/source dictionary until they are
  decoded. Do not promote them into stable API fields without a specific
  analysis question.
