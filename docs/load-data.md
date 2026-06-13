# Load Data Requirements

This note defines what data is needed before Garmin Stats can add a defensible **load / strain**
axis to the central health-training dashboard.

It is intentionally separate from the recovery score. Recovery describes the body's current
physiological state. Load describes the stressor applied to the body. Strain describes that stressor
relative to recent capacity, context, and recovery.

## Current status

Load / strain is **not implemented**.

The current daily mart is recovery-first: HRV, heart rate, stress, respiration, body battery, sleep,
SpO2, and skin temperature. That is the right grain for overnight and all-day recovery signals, but
it is the wrong source of truth for training load.

Do **not** infer training load from recovery outputs such as HRV, resting HR, body battery, sleep
score, stress average, or a recovery score. Those are outcomes or context. They may help explain the
effect of load, but they are not the load itself.

The load axis requires activity/session data.

## Vocabulary

### External load

The work performed, independent of how hard it felt physiologically.

Examples:

- duration
- distance
- elevation gain
- work / power, when available
- sport type
- session count
- run duration or run distance

External load is sport-specific. A 45-minute run, 45-minute strength session, and 45-minute
meditation session should not be collapsed into one generic number without validation.

### Internal load

The body's measured response during the session.

Examples:

- average HR
- max HR
- time in HR zones
- training effect
- anaerobic training effect
- Garmin native training load, if present
- session RPE, if logged manually

Internal load is closer to strain than external load, but still belongs to the activity/session
side of the model, not the recovery side.

### Strain

The burden imposed by recent load relative to recent baseline, capacity, and context.

Candidate examples:

- yesterday's training load
- 7-day load
- 28-day load
- acute-to-chronic load ratio
- high-load day flag
- hard-session-after-low-recovery flag
- load ramp rate

Strain should be validated against next-day recovery and performance outcomes before it is promoted
to a dashboard headline.

## Source data needed

### 1. Activity session summaries

The first requirement is a canonical activity-session mart with one row per tracked session.

Minimum fields:

| Field | Why it matters |
| --- | --- |
| `id` | Stable session identity. |
| `source_file` | Audit trail back to the FIT file. |
| `local_date` | Daily joins and previous-day load features. |
| `start_time` / `end_time` | Session timing, same-day vs previous-day alignment. |
| `sport` / `sub_sport` / `sport_profile_name` | Sport-specific load interpretation. |
| `total_elapsed_time_s` | Session duration including pauses. |
| `total_timer_time_s` | Active/timer duration. |
| `total_distance_m` | External load for running/cycling/walking. |
| `total_ascent_m` / `total_descent_m` | Hill load context. |
| `avg_heart_rate` / `max_heart_rate` | Internal load and intensity. |
| `avg_power` / `max_power` | External/internal workload where power exists. |
| `avg_cadence` / `max_cadence` | Running/cycling mechanics context. |
| `total_training_effect` | Garmin-native aerobic effect. |
| `total_anaerobic_training_effect` | Garmin-native anaerobic effect. |
| `training_load_peak` | Best native V1 scalar if available. |
| `total_work` | Power-based load when present. |
| `num_laps` | Signals whether lap detail may matter. |
| `has_gps_trace` / `has_power` / `has_hr` | Data quality flags. |

V1 should parse activity `session_mesgs` first. Lap and record-level data can wait unless session
summaries are missing the fields needed for load.

### 2. Garmin `METRICS` files

The project already sees daily `METRICS` FIT files, but they are not parsed. They may contain
training-adjacent fields that Garmin computes outside activity sessions.

Needed work:

- discover which message types contain load, training status, VO2 max, acute load, or training
  readiness-like values
- document field names, units, and coverage
- decide whether each field is source-like, Garmin-derived, or opaque vendor summary
- keep opaque Garmin summaries separate from source-native load fields

`METRICS` should not block V1 activity-session load if activity FIT sessions already expose
`training_load_peak` and training effect.

### 3. Lap / record intensity detail

Session summaries may be enough for V1. If not, load needs finer-grain intensity data:

- HR samples over the session
- time in HR zones
- pace/speed samples
- power samples
- lap splits
- interval structure
- grade-adjusted or elevation-aware context

This unlocks HR-based or power-based load models, but it is more expensive to parse and validate.
It should come after the native session-summary path.

### 4. Manual or contextual data

Some load/strain questions cannot be answered from Garmin alone.

Useful context:

- session RPE
- soreness
- fatigue
- illness
- travel
- alcohol
- planned workout vs completed workout
- strength session details not captured by Garmin load
- meditation or recovery-session exposure

Manual context should be joined as explanation or confounder data. It should not be mixed into the
load number unless a specific model is validated.

## Daily load features

Once activity sessions exist, derive a daily activity feature row.

Recommended V1 daily features:

| Feature | Meaning |
| --- | --- |
| `session_count` | Number of tracked sessions that day. |
| `training_load_total` | Sum of session `training_load_peak` where available. |
| `run_training_load` | Running-only load. |
| `run_duration_minutes` | Running volume. |
| `run_distance_m` | Running distance. |
| `strength_session_count` | Strength exposure, not necessarily scalar load. |
| `strength_duration_minutes` | Strength volume proxy. |
| `hard_session_flag` | Training effect/load above a personal threshold. |
| `max_training_effect` | Hardest aerobic session that day. |
| `max_anaerobic_training_effect` | Hardest anaerobic session that day. |

Recommended lagged features for recovery joins:

| Feature | Meaning |
| --- | --- |
| `prev_day_training_load_total` | Stress applied before next-morning recovery. |
| `prev_day_run_training_load` | Run-specific previous-day stress. |
| `prev_day_run_duration_minutes` | Run volume before recovery outcome. |
| `prev_day_run_distance_m` | Run distance before recovery outcome. |
| `prev_day_strength_session_flag` | Strength exposure before recovery outcome. |
| `prev_day_meditation_minutes` | Recovery/habit exposure, not training load. |

Do not join all sessions into `daily_metrics` directly. Keep session grain and daily feature grain
separate.

## Candidate dashboard metrics

These are candidates, not validated contracts.

### Load

Primary candidate:

- **7-day training load** = rolling sum of daily source-native training load.

Supporting values:

- yesterday's load
- 28-day training load
- run-specific 7-day load
- hard-session count in last 7 days
- longest session in last 7 days

### Strain

Primary candidate:

- **load vs baseline** = current 7-day load compared with personal 28-day or 42-day baseline.

Supporting values:

- load ramp rate
- acute-to-chronic load ratio
- high-load-after-low-recovery flag
- high-load-with-short-sleep flag

Strain can use recovery as context, but recovery should not become a hidden component of the load
number. A combined "training state" surface can show load and recovery side by side.

### Adaptation / progress

This is adjacent to load but should not be confused with it.

Candidate data:

- pace or power at comparable HR
- distance and duration capacity over time
- training effect distribution
- long-run duration trend
- sport-specific performance markers

Progress should be studied after session ingestion exists. It likely needs sport-specific models,
not one generic score.

## Validation questions

Before shipping load / strain as a dashboard headline, answer:

1. Does native Garmin session load have enough coverage across tracked sessions?
2. Does previous-day load predict next-morning recovery shifts after controlling for sleep and
   recent recovery state?
3. Are run load, strength exposure, and meditation/recovery sessions separable enough to display as
   different concepts?
4. Does a 7-day load window or a shorter window better match observed recovery response?
5. Does a 28-day or 42-day baseline make strain more stable without hiding real load ramps?
6. Are missing/untracked activities common enough to make the metric misleading?
7. Does the metric support a user decision, or is it just a retrospective chart?

## Data quality risks

- **Untracked sessions:** no device record means no load. Missing training is not zero training.
- **Sport heterogeneity:** running, strength, cycling, walking, and meditation should not share one
  load formula by default.
- **Native field gaps:** `training_load_peak` may be absent for some sports or files.
- **Opaque Garmin metrics:** useful, but should be labeled as Garmin-derived and not treated like raw
  physiology.
- **All-day movement leakage:** steps, daily HR, and body battery depletion are not deliberate
  training load.
- **Recovery circularity:** a model that uses recovery outputs to define load cannot later claim to
  test load's effect on recovery.

## Implementation sequence

1. Parse activity FIT session summaries.
2. Store canonical `activity_sessions`.
3. Derive `activity_daily_features`.
4. Add previous-day load features for recovery joins.
5. Profile coverage, missingness, and sport mix.
6. Run a finding-analysis pass: previous-day load vs next-day recovery.
7. Only then decide what belongs on the central dashboard.

The product target is not "one load score." The target is a defensible **training state** view:
recovery state, recent load, sleep opportunity, health exceptions, and behavior context shown as
separate but aligned lanes.
