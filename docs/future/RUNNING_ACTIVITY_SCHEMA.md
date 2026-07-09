# Running Activity Schema

> Status: proposed parser/read-model schema, based on the downloaded activity FIT
> files in `data/garmin_activities/` as of 2026-06-28.

This schema is the running-specific extension of the broader activity-session
mart described in `ACTIVITY_ANALYTICS_DESIGN.md`.

It keeps three grains separate:

- one row per run session
- one row per lap/split
- one row per timestamped record sample

The session row should be the first implementation target. Lap and record rows
are source-rich, but they are heavier and should not block session-level load,
volume, and trend features.

## Observed Coverage

Running files inspected:

- `271` running FIT files
- `271` session summaries
- `271` files with GPS traces
- `271` files with lap/split data
- `271` files with record traces
- `99` files with heart-rate data

Decoded running kinds:

| Kind | Files |
| --- | ---: |
| `running_generic` | 270 |
| `running_trail` | 1 |

Heart-rate coverage is date-patterned. Most older runs do not contain HR; nearly
all runs from March 2026 onward do.

## Unit Policy

The backend owns all unit normalization. The frontend should receive display-ready
units and should not compute pace, cadence conversion, or derived load fields.

| Concept | Canonical field/unit | Source note |
| --- | --- | --- |
| Distance | meters | FIT `total_distance`, record `distance` |
| Duration | seconds | FIT `total_timer_time`, `total_elapsed_time` |
| Pace | minutes per kilometer | derived from timer duration and distance |
| Speed | meters per second | FIT `enhanced_avg_speed`, `enhanced_speed` |
| Elevation | meters | FIT ascent/descent and enhanced altitude |
| Heart rate | beats per minute | nullable; present in 99/271 running files |
| Power | watts | FIT avg/max/normalized/record power |
| Cadence | steps per minute | FIT running cadence fields are half-cadence in observed files; multiply by 2 for canonical display |
| Ground contact time | milliseconds | FIT `avg_stance_time`, record `stance_time` |
| Vertical oscillation | millimeters | FIT `avg_vertical_oscillation`, record `vertical_oscillation` |
| Vertical ratio | percent | FIT `avg_vertical_ratio`, record `vertical_ratio` |
| Step length | millimeters | FIT `avg_step_length`, record `step_length` |
| Training effect | Garmin scalar | FIT `total_training_effect`, `total_anaerobic_training_effect` |
| Training load | Garmin scalar | FIT `training_load_peak` / JSON `activityTrainingLoad` |

## `RunningActivitySession`

One row per running activity FIT file.

Recommended Python contract:

```python
class RunningActivitySession(BaseModel):
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

    distance_m: float | None
    pace_min_per_km: float | None
    avg_speed_mps: float | None
    max_speed_mps: float | None
    grade_adjusted_avg_speed_mps: float | None

    total_ascent_m: int | None
    total_descent_m: int | None
    min_altitude_m: float | None
    max_altitude_m: float | None

    avg_heart_rate_bpm: int | None
    max_heart_rate_bpm: int | None
    has_heart_rate: bool

    avg_power_w: int | None
    max_power_w: int | None
    normalized_power_w: int | None
    total_work_j: int | None
    has_power: bool

    avg_cadence_spm: float | None
    max_cadence_spm: float | None
    avg_ground_contact_time_ms: float | None
    avg_vertical_oscillation_mm: float | None
    avg_vertical_ratio_pct: float | None
    avg_step_length_mm: float | None

    total_steps: int | None
    total_calories: int | None
    aerobic_training_effect: float | None
    anaerobic_training_effect: float | None
    training_load: float | None
    vo2max: float | None

    lap_count: int
    record_count: int
    has_gps_trace: bool
    has_laps: bool
    has_records: bool

    start_lat: float | None
    start_lon: float | None
    end_lat: float | None
    end_lon: float | None
    swc_lat: float | None
    swc_lon: float | None
    nec_lat: float | None
    nec_lon: float | None

    source_summary: dict
```

### Session Source Mapping

| Field | Primary source |
| --- | --- |
| `activity_id` | JSON sidecar `activityId` |
| `activity_name` | JSON sidecar `activityName` |
| `start_time_local` | JSON sidecar `startTimeLocal` |
| `start_time_utc` | FIT `session_mesgs.start_time` or JSON `startTimeGMT` |
| `elapsed_time_s` | FIT `session_mesgs.total_elapsed_time` |
| `timer_time_s` | FIT `session_mesgs.total_timer_time` |
| `moving_time_s` | JSON sidecar `movingDuration` |
| `distance_m` | FIT `session_mesgs.total_distance` |
| `pace_min_per_km` | backend-derived from `timer_time_s / distance_m` |
| `avg_speed_mps` | FIT `session_mesgs.enhanced_avg_speed` |
| `max_speed_mps` | FIT `session_mesgs.enhanced_max_speed` |
| `grade_adjusted_avg_speed_mps` | JSON sidecar `avgGradeAdjustedSpeed` |
| `avg_heart_rate_bpm` | FIT `session_mesgs.avg_heart_rate` |
| `max_heart_rate_bpm` | FIT `session_mesgs.max_heart_rate` |
| `avg_power_w` | FIT `session_mesgs.avg_power` |
| `max_power_w` | FIT `session_mesgs.max_power` |
| `normalized_power_w` | FIT `session_mesgs.normalized_power` or JSON `normPower` |
| `avg_cadence_spm` | FIT `avg_running_cadence * 2` |
| `max_cadence_spm` | FIT `max_running_cadence * 2` |
| `avg_ground_contact_time_ms` | FIT `session_mesgs.avg_stance_time` |
| `avg_vertical_oscillation_mm` | FIT `session_mesgs.avg_vertical_oscillation` |
| `avg_vertical_ratio_pct` | FIT `session_mesgs.avg_vertical_ratio` |
| `avg_step_length_mm` | FIT `session_mesgs.avg_step_length` |
| `training_load` | FIT `session_mesgs.training_load_peak` |
| `vo2max` | JSON sidecar `vO2MaxValue` |

## `RunningActivityLap`

One row per lap in a run.

```python
class RunningActivityLap(BaseModel):
    id: str
    session_id: str
    lap_index: int

    start_time_utc: str | None
    timer_time_s: float | None
    elapsed_time_s: float | None
    distance_m: float | None
    pace_min_per_km: float | None

    avg_speed_mps: float | None
    max_speed_mps: float | None
    avg_heart_rate_bpm: int | None
    max_heart_rate_bpm: int | None
    avg_power_w: int | None
    max_power_w: int | None
    normalized_power_w: int | None

    avg_cadence_spm: float | None
    max_cadence_spm: float | None
    avg_ground_contact_time_ms: float | None
    avg_vertical_oscillation_mm: float | None
    avg_vertical_ratio_pct: float | None
    avg_step_length_mm: float | None

    total_ascent_m: int | None
    total_descent_m: int | None
    total_calories: int | None
    total_work_j: int | None
    intensity: str | None
    lap_trigger: str | None
```

Lap data is useful for split analysis, interval detection, and pace/HR drift.
It should stay separate from the session row because a session can have many
laps and the fields repeat at a different grain.

## `RunningActivityRecord`

One row per timestamped record sample.

```python
class RunningActivityRecord(BaseModel):
    session_id: str
    sample_index: int
    timestamp_utc: str

    distance_m: float | None
    speed_mps: float | None
    pace_min_per_km: float | None
    altitude_m: float | None
    position_lat: float | None
    position_lon: float | None

    heart_rate_bpm: int | None
    cadence_spm: float | None
    power_w: int | None
    accumulated_power_w: int | None

    ground_contact_time_ms: float | None
    vertical_oscillation_mm: float | None
    vertical_ratio_pct: float | None
    step_length_mm: float | None
```

Record data is the right source for pace/HR drift, route maps, time-in-zone
rebuilds, and within-run interval analysis. It is too heavy for the first
activity-summary pass.

## Storage Shape

The existing SQLite pattern stores JSON payloads with a small number of indexed
columns. Keep that pattern.

```sql
CREATE TABLE IF NOT EXISTS running_activity_sessions (
    id TEXT PRIMARY KEY,
    activity_id TEXT,
    session_date TEXT NOT NULL,
    start_time_local TEXT NOT NULL,
    sub_sport TEXT,
    distance_m REAL,
    timer_time_s REAL,
    training_load REAL,
    data TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_running_activity_sessions_date_start
    ON running_activity_sessions (session_date, start_time_local);

CREATE INDEX IF NOT EXISTS idx_running_activity_sessions_activity_id
    ON running_activity_sessions (activity_id);
```

Lap and record storage should only be added when there is a concrete read path:

```sql
CREATE TABLE IF NOT EXISTS running_activity_laps (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    lap_index INTEGER NOT NULL,
    data TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES running_activity_sessions(id)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_running_activity_laps_session_lap
    ON running_activity_laps (session_id, lap_index);
```

Record samples are high-volume. Prefer file-backed parsing for exploratory work
until a product route needs persisted traces.

## Data Quality Flags

Every parsed session should expose these booleans:

```python
has_gps_trace = record_count > 0 and any GPS point exists
has_heart_rate = avg_heart_rate_bpm is not None or record HR exists
has_power = avg_power_w is not None or record power exists
has_running_dynamics = avg_ground_contact_time_ms is not None
has_laps = lap_count > 0
has_records = record_count > 0
```

These flags matter because HR missingness is not random across time. Any
analysis that uses HR should state the date window and coverage explicitly.

## First Backend Features To Build

Session-level features:

- `run.distance_m`
- `run.timer_time_s`
- `run.pace_min_per_km`
- `run.training_load`
- `run.aerobic_training_effect`
- `run.total_ascent_m`
- `run.avg_power_w`
- `run.avg_cadence_spm`
- `run.has_heart_rate`

Daily features derived from sessions:

- `activity.run_count`
- `activity.run_distance_total_m`
- `activity.run_timer_time_total_s`
- `activity.run_training_load_total`
- `activity.longest_run_distance_m`
- `activity.prev_day_run_distance_m`
- `activity.prev_day_run_training_load`

Do not use HR-based daily features until HR coverage is profiled per date range.
