# Activity Analytics Design

> **STATUS: PROPOSED / DEFERRED for strength + the experiment-day mart. Running
> session/lap/record ingest SHIPPED 2026-07.** None of the `ActivitySession` /
> `ExperimentDayRow` generic models, `activity_sessions` / `activity_daily_features`
> tables, or `parse_activity_file` / `parse_activities` generic parser described
> below were built as designed here — running shipped instead as its own
> running-specific tables (`running_activity_sessions`/`_laps`/`_series`),
> series stored as one JSON blob per session (not a `activity_records` row-per-sample
> table), record grain included from day one (not deferred, unlike the "records
> only when a product route needs them" guidance below). Running has routes
> (`/api/activities/runs*`) and pages (`/runs`, `/runs/[id]`) live now — see
> `../reference/run-activities.md` for how it actually works. Strength ingest,
> the generic cross-sport `ActivitySession` model, sleep-timing fields on the
> daily mart, and the experiment-day mart below remain unbuilt; treat those
> portions of this document as a target to build, not a contract that exists.
> The pre-existing foundations it references (the `daily_metrics` mart,
> `parse_all_days`, WELLNESS/SLEEP/HRV/SKIN_TEMP parsing, `alcohol_flag` daily
> check-ins) are real.
>
> Current sequencing: strength parse (this doc's `STRENGTH_ACTIVITY_SCHEMA.md`)
> and association between a prescribed run and its actual activity are next;
> see `../routine-pivot/pivot_roadmap.md` next-steps.

This document defines a future analytical foundation for Garmin Stats.

It exists because the current recovery-first daily aggregate model is correct for overnight and all-day health signals, but it is the wrong grain for tracked activities and for experiment analysis that joins training, sleep timing, alcohol, and recovery.

## Purpose

The app needs to answer three different classes of questions:

- recovery-day questions
- activity-session questions
- experiment questions that join the first two

Those questions do not share one natural grain.

The design goal is to keep each grain explicit and make the backend own all derived features and joins.

## Core Rules

### Choose grain by question

- Use day grain for overnight recovery and all-day wellness.
- Use session grain for tracked activities.
- Use experiment-day grain for lagged joins between exposures and outcomes.

Do not collapse session data into `daily_metrics` just because the current app already has a daily mart.

### Use source-native fields before derived proxies

If Garmin activity FIT files already provide workout-level session summaries, use those first.

Examples:

- `total_training_effect`
- `total_anaerobic_training_effect`
- `training_load_peak`
- `total_distance`
- `avg_heart_rate`
- `avg_power`

Do not infer training load from recovery outputs like HRV, resting HR, body battery, or sleep score.

### Keep the frontend display-only

The frontend should not compute:

- training load
- sleep timing features
- experiment joins
- lagged activity features

Those belong in backend feature builders.

### Start narrow, not generic

The first activity ingest should support the questions already visible in the product:

- what happened in this workout
- how much training stress did the previous day contain
- how did that relate to next-morning recovery

Do not start with full generic sports science ontology work.

## Current State

The current ingest path is:

`FIT files -> garmin_health FIT parser package -> daily metric composition -> daily tables + daily_metrics`

That works for:

- `wellness_data`
- `sleep_data`
- `hrv_data`
- `skin_temp_data`
- `daily_metrics`

It does not work for activity FIT files because activities are session-centric, not day-centric, and because a single day can have zero, one, or many tracked sessions.

## Proposed Analytical Marts

The backend should expose three marts.

### 1. Recovery day mart

This is the current `daily_metrics` concept, expanded but not replaced.

Responsibilities:

- one row per recovery day
- overnight and day-level recovery signals
- sleep timing features
- no session-specific workout detail

Recommended shape:

- keep `DailyMetric` as the recovery mart model in v1 to minimize churn
- extend `DailySleepStats` with derived sleep timing fields

New recovery fields to add:

- `bedtime_local_minutes`
- `wake_time_local_minutes`
- `duration_hours`
- `midpoint_local_minutes`
- `midpoint_consistency_delta_minutes`

These fields should be derived from `sleep_level_mesgs` timestamps in the backend.

### 2. Activity session mart

This is the new source of truth for tracked workouts and guided sessions.

One row per activity FIT file session.

Recommended model:

```python
class ActivitySession:
    id: str
    source_file: str
    source_date_dir: str | None
    local_date: str
    start_time: str
    end_time: str | None
    sport: str | None
    sub_sport: str | None
    sport_profile_name: str | None
    total_elapsed_time_s: float | None
    total_timer_time_s: float | None
    total_distance_m: float | None
    total_calories: int | None
    avg_heart_rate: int | None
    max_heart_rate: int | None
    avg_power: int | None
    max_power: int | None
    avg_cadence: int | None
    max_cadence: int | None
    total_ascent_m: int | None
    total_descent_m: int | None
    total_training_effect: float | None
    total_anaerobic_training_effect: float | None
    training_load_peak: float | None
    total_work: int | None
    num_laps: int | None
    has_gps_trace: bool
    has_power: bool
    has_hr: bool
```

V1 should parse from `session_mesgs`.

Running shipped with its own tables and contracts instead of this generic
model — see `../reference/run-activities.md` for the actual field contract,
unit policy, and session/lap/series split.

For the strength-specific field contract, Garmin set/repetition caveats, and
session-load/record split, see `STRENGTH_ACTIVITY_SCHEMA.md`.

Optional follow-on models:

- `ActivityLap`
- `ActivityRecordTrace`

Those should be added only after session summaries are stable.

### 3. Experiment day mart

This mart exists to answer causal or quasi-causal questions.

One row per outcome day, built from lagged joins between:

- recovery day metrics
- previous-day activity features
- same-day or previous-day checkins

This should not be a raw ingest table in v1.

Build it as a backend feature row in service code first. Persist only if query cost becomes a real problem.

Recommended logical shape:

```python
class ExperimentDayRow:
    date: str
    hrv_nightly: float | None
    resting_hr: int | None
    sleep_score: int | None
    sleep_midpoint_local_minutes: float | None
    sleep_duration_hours: float | None
    prev_day_training_load_total: float | None
    prev_day_run_training_load: float | None
    prev_day_run_duration_minutes: float | None
    prev_day_run_distance_m: float | None
    prev_day_strength_session_flag: bool
    prev_day_meditation_minutes: float | None
    alcohol_flag: bool
    travel_flag: bool
    illness_flag: bool
    workload_subjective: int | None
    exclude_heavy_training: bool
    exclude_alcohol: bool
    exclude_short_sleep: bool
```

## Storage Tables

The current SQLite pattern is JSON-backed tables with a small number of indexed columns. Keep that pattern.

### V1 tables to add

#### `activity_sessions`

Purpose:

- canonical per-session activity summary storage

Suggested schema:

```sql
CREATE TABLE IF NOT EXISTS activity_sessions (
    id TEXT PRIMARY KEY,
    session_date TEXT NOT NULL,
    sport TEXT,
    start_time TEXT NOT NULL,
    data TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_activity_sessions_date_start
    ON activity_sessions (session_date, start_time);

CREATE INDEX IF NOT EXISTS idx_activity_sessions_sport_date
    ON activity_sessions (sport, session_date);
```

#### `activity_daily_features`

Purpose:

- backend-owned daily feature layer derived from `activity_sessions`
- one row per calendar date

Suggested schema:

```sql
CREATE TABLE IF NOT EXISTS activity_daily_features (
    date TEXT PRIMARY KEY,
    data TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
```

### Deferred tables

Do not add these until a concrete use case appears:

- `activity_laps`
- `activity_records`
- `experiment_feature_rows`

For V1, session summaries are enough.

## Parser Boundaries

### Keep day-grouped parsing for wellness and sleep

These file types remain naturally day-grouped:

- `WELLNESS`
- `SLEEP_DATA`
- `HRV_STATUS`
- `SKIN_TEMP`

The existing `parse_all_days()` flow should stay responsible for them.

### Add file-centric activity parsing

Activity FIT ingestion should not depend on a day folder.

The parser should accept:

- activity files stored under a date folder
- activity files stored directly under the data root

Recommended additions to `backend/app/domains/garmin_health/infra/fit_parser/`,
with compatibility exports from `backend/app/parser.py` only if existing ingest
callers need them:

- `parse_activity_file(file_path: Path) -> ActivitySession`
- `parse_activities(data_dir: Path) -> list[ActivitySession]`

Rules:

- parse standard `session_mesgs` as the primary summary
- use `lap_mesgs` and `record_mesgs` only for optional trace/lap outputs
- determine `local_date` from activity start time, not from filesystem location
- store `source_file` so ingest is auditable

### Do not make `METRICS` a blocker

`METRICS` may later provide useful training-adjacent fields, but it should not block V1.

Activity FIT files already provide a robust session summary for tracked runs and other recorded sessions.

The right sequence is:

1. ingest `_ACTIVITY.fit`
2. ship session-level analytics
3. inspect `METRICS` later only when a real gap remains

## Ingest Pipeline

The ingest path should become:

`FIT files -> garmin_health FIT parser package -> canonical day/session models -> derived marts -> SQLite`

### V1 write path

1. Parse day-grain wellness/sleep/HRV/skin-temp data.
2. Compute and upsert `daily_metrics`.
3. Parse activity FIT files into `activity_sessions`.
4. Derive and upsert `activity_daily_features`.
5. Invalidate caches for both recovery and activity read paths.

### Fingerprinting

The ingest fingerprint currently keys off the health data tree.

It must expand to include:

- day-folder activity FIT files
- root-level activity FIT files

Otherwise activity-only changes will not trigger refresh.

## Daily Feature Strategy

The purpose of `activity_daily_features` is not to summarize everything.

Its purpose is to produce stable confounders and experiment inputs.

### Training load definition

Define training load as:

`previous-day deliberate training stress from tracked activity sessions`

Not:

- all-day movement
- wellness HR
- body battery depletion
- resting HR elevation

### Session load definition

For V1:

- `session_training_load = training_load_peak` when Garmin provides it
- keep null when Garmin does not provide it

Do not invent a fake scalar fallback immediately.

Instead, keep adjacent session descriptors alongside load:

- duration
- distance
- sport
- training effect

This is more honest than hiding missing native load behind a guessed formula.

### Activity type handling

- Running: full load participant
- Strength: include as session count or minutes first; promote to scalar load only after real validation
- Meditation: separate exposure, not training load
- Stretching: ignore unless it becomes a tracked session with a concrete analytical use

## First 10 Features To Implement

These are the first backend-owned features worth building because they support both activity analytics and sleep experiments.

1. `sleep.bedtime_local_minutes`
2. `sleep.wake_time_local_minutes`
3. `sleep.duration_hours`
4. `sleep.midpoint_local_minutes`
5. `sleep.midpoint_consistency_delta_minutes`
6. `activity.prev_day_training_load_total`
7. `activity.prev_day_run_training_load`
8. `activity.prev_day_run_duration_minutes`
9. `activity.prev_day_strength_session_flag`
10. `activity.prev_day_meditation_minutes`

Important note:

- `alcohol_flag` already exists in daily checkins and should be joined into experiment rows from checkins, not rebuilt as an activity feature

## Service Boundaries

Recommended new backend modules:

- `backend/app/domains/garmin_health/contracts/`
  Add canonical activity/session contracts only if they are shared below analytics.
- `backend/app/domains/garmin_analytics/domain/activity_sessions.py`
  Shape session-level read models and summaries.
- `backend/app/domains/garmin_analytics/domain/activity_features.py`
  Build day-level activity features from sessions.
- `backend/app/domains/experiments/application/`
  Build experiment-day rows from recovery day + activity features + checkins.

Recommended current-module changes:

- `domains/garmin_health/infra/fit_parser/`
  Add activity file parsing.
- `domains/garmin_health/contracts/`
  Add `ActivitySession`, `ActivityDailyFeatures`, and new sleep timing fields.
- `domains/garmin_sync/infra/sqlite_ingest.py` and owning `schema.py` modules
  Add activity tables, loaders, savers, and ingest wiring.
- `domains/garmin_health/domain/daily_metrics/`
  Extend daily recovery features only for sleep timing, not activities.

## Query Boundaries

Each analysis surface should read from the smallest mart that matches the question.

### Recovery routes

Read from:

- `daily_metrics`
- day-grain raw tables when necessary

Do not join activity sessions by default.

### Activity routes

Read from:

- `activity_sessions`
- optional lap or record data if added later

### Experiment routes

Read from:

- `daily_metrics`
- `activity_daily_features`
- `daily_checkins`

Build lagged joins in one place, not independently inside multiple route handlers.

## Validation Strategy

Before productizing any new feature:

1. decode a real representative file
2. document field presence and null rates
3. generate exploratory plots
4. inspect charts visually
5. only then expose the metric in the app

For activity analytics specifically:

- validate one run
- validate one strength workout
- validate one meditation session
- validate one day with multiple sessions

## Non-Goals For V1

Do not do these in the first activity analytics pass:

- generic sport taxonomy redesign
- lift set counting or rep-level strength analytics
- performance prediction models
- frontend-owned cross-metric computations
- `METRICS` reverse engineering as a prerequisite

## Implementation Order

### Phase 1

- parse and store `ActivitySession`
- add `activity_sessions` table
- accept root-level and day-folder `_ACTIVITY.fit` files

### Phase 2

- derive `activity_daily_features`
- extend `DailySleepStats` with timing fields
- expose loader functions and backend tests

### Phase 3

- build experiment feature rows from lagged joins
- update experiments to use those rows for confounder-aware analysis

### Phase 4

- add dedicated activity routes and UI surfaces
- consider `lap` and `record` endpoints only if a specific view needs them

## Decision Summary

The repo should stop treating all health analytics as one daily aggregate problem.

The correct backend shape is:

- recovery mart at day grain
- activity mart at session grain
- experiment mart at joined day grain

That keeps the data model honest, makes training load defensible, and gives the app a clean path from recovery dashboard to real N-of-1 experiments.
