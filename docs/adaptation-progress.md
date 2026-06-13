# Adaptation / Progress Data Requirements

This note defines what data is needed before Garmin Stats can add a defensible
**adaptation / progress** lane to the central health-training dashboard.

Progress is not recovery. Progress is not load. Progress asks whether training is producing improved
capability over time.

## Current status

Adaptation / progress is **not implemented**.

The current app has a recovery-first daily mart and no parsed activity-session mart. That means the
app can describe physiological state, but it cannot yet answer whether the user is becoming fitter,
faster, stronger, more durable, or more efficient.

Do **not** infer progress from:

- higher training load alone
- better HRV
- lower resting HR
- higher body battery
- better sleep score
- total lifetime distance
- isolated personal records without context

Those can be context or supporting evidence, but none of them proves adaptation.

## Product meaning

Adaptation / progress should answer:

- Am I becoming more capable at the activity I care about?
- Can I produce the same output at lower physiological cost?
- Can I sustain more work without a recovery collapse?
- Is training consistency turning into performance, or only fatigue?

That makes progress inherently **sport-specific**. Running progress, strength progress, cycling
progress, and mobility progress should not share one generic score unless a later analysis proves
that such a score is useful.

## Vocabulary

### Performance

What the user produced in a session.

Examples:

- pace
- speed
- power
- distance
- duration
- elevation-adjusted output
- best sustained 20- or 30-minute effort
- reps / load / volume for strength work

Performance only means progress when compared under similar effort and context.

### Efficiency

Output at a comparable physiological cost.

Examples:

- faster pace at the same HR
- lower HR at the same pace
- higher power at the same HR
- lower perceived effort at the same output

Efficiency is usually the best first progress construct for endurance training because it is less
dependent on all-out efforts.

### Capacity

The amount of work the user can tolerate or complete.

Examples:

- longest run duration
- longest run distance
- weekly run volume sustained without interruption
- number of sessions completed per week
- ability to complete a planned progression

Capacity is not the same as fitness. More volume can mean better durability, but it can also mean
accumulated fatigue.

### Durability

The ability to handle load without a disproportionate recovery cost.

Examples:

- similar load causes less next-day suppression than before
- long runs no longer produce multi-day recovery drops
- hard sessions are followed by normal recovery within the expected window

Durability requires both activity load data and recovery outcomes.

## Source data needed

### 1. Activity session summaries

The same activity-session mart needed for load is the foundation for progress.

Minimum fields:

| Field | Why it matters |
| --- | --- |
| `id` | Stable session identity. |
| `source_file` | Audit trail back to the FIT file. |
| `local_date` | Trend grouping and recovery joins. |
| `start_time` / `end_time` | Timing, duration, same-day context. |
| `sport` / `sub_sport` / `sport_profile_name` | Sport-specific progress model. |
| `total_elapsed_time_s` | Total session time, including stops. |
| `total_timer_time_s` | Active/timer duration. |
| `total_distance_m` | Pace, volume, and route comparisons. |
| `total_ascent_m` / `total_descent_m` | Hill context and route difficulty. |
| `avg_heart_rate` / `max_heart_rate` | Effort and aerobic cost. |
| `avg_power` / `max_power` | Output when power is available. |
| `avg_cadence` / `max_cadence` | Running/cycling mechanics context. |
| `total_training_effect` | Session stimulus, not progress by itself. |
| `total_anaerobic_training_effect` | Anaerobic stimulus context. |
| `training_load_peak` | Load context for progress interpretation. |
| `num_laps` | Signals whether splits/intervals may be useful. |
| `has_gps_trace` / `has_power` / `has_hr` | Data quality flags. |

Session summaries can support coarse progress views. Serious progress metrics need lap or record
detail.

### 2. Lap and record detail

Progress depends on comparing like with like. Session averages are often too blunt because they mix
warm-up, intervals, pauses, hills, and cool-down into one number.

Useful detail:

- lap splits
- interval structure
- per-record HR
- per-record pace or speed
- per-record power
- per-record cadence
- GPS route trace
- elevation / grade
- moving vs stopped time
- time in HR zones

This enables metrics such as pace at comparable HR, HR drift, steady-state segments, and
route-matched comparisons.

### 3. Garmin `METRICS` files

Garmin `METRICS` files may contain useful vendor-derived progress signals.

Potential fields to discover:

- VO2 max
- training status
- performance condition
- race predictions
- acute load
- chronic load
- training readiness-like values
- endurance score or hill score, if present for this device/export

These should be labeled as Garmin-derived. They can be useful context, but they should not replace
source-derived performance metrics.

### 4. Route, terrain, and weather context

Progress comparisons are fragile without context.

Useful context:

- route identity or route similarity
- elevation profile
- surface / terrain when available
- temperature
- wind
- humidity
- altitude

Weather may require an external data source. It is not mandatory for V1, but without it the app
should avoid overconfident claims from pace/HR changes.

### 5. Manual and routine data

Garmin often does not capture enough structure for strength and mobility progress.

Useful manual/routine data:

- exercise name
- sets
- reps
- load
- RPE / reps in reserve
- progression target
- completion status
- pain or limitation notes
- planned vs completed workout

For strength work, routine logs are likely more valuable than Garmin activity summaries.

## Candidate progress constructs

These are candidates, not validated contracts.

### Running aerobic efficiency

Question:

- At a comparable HR, is pace improving?

Candidate metric:

- pace at a fixed personal aerobic HR band, using steady-state segments or easy runs.

Required filters:

- running only
- GPS and HR present
- exclude intervals/races unless explicitly analyzing hard performance
- control or annotate elevation and route changes
- prefer 30- to 60-minute easy/aerobic sessions

Supporting views:

- HR at comparable pace
- pace/HR scatter by month
- trend of easy-run pace at target HR
- distribution of easy-run HR drift

### Running capacity

Question:

- Can the user sustain more running volume or longer runs?

Candidate metrics:

- longest run duration in the last 28 days
- weekly run duration
- weekly run distance
- number of run sessions per week
- longest easy run without next-day suppression

Required caveat:

- capacity is not automatically positive. Rising volume with worsening recovery may be strain, not
  adaptation.

### Running durability

Question:

- Is a similar load causing less recovery disruption over time?

Candidate metrics:

- next-day recovery response after comparable long runs
- recovery rebound time after hard sessions
- change in HRV/resting-HR response at similar training load

Required data:

- session load
- session type
- next-day recovery metrics
- sleep duration/timing
- illness/alcohol/travel context

### Hard-performance markers

Question:

- Is top-end or threshold-like performance improving?

Candidate metrics:

- best sustained 20-minute pace or power
- best sustained 30-minute pace or power
- high-effort session pace trend
- race/time-trial performance, if explicitly marked

Required caveat:

- hard-performance markers are sparse and biased by when the user chooses to run hard.

### Strength progress

Question:

- Is the user moving more load or volume at comparable effort and form?

Candidate metrics:

- estimated working-set volume by exercise
- load at comparable reps and RPE
- progression completion rate
- top set trend for repeated exercises
- pain-free completion streak

Required data:

- routine logs with exercise-level sets/reps/load/RPE
- Garmin strength activity summaries are not enough by themselves

### Consistency

Question:

- Is the user accumulating enough repeated practice for adaptation to be plausible?

Candidate metrics:

- completed sessions per week
- weeks with target frequency met
- missed planned sessions
- streaks by activity type

Required caveat:

- consistency supports adaptation, but it is not adaptation by itself.

## Dashboard candidates

The central dashboard should not start with one generic progress score.

Better V1 candidates:

1. **Running efficiency trend**: easy-run pace at comparable HR, with coverage/caveat text.
2. **Running capacity trend**: weekly run duration or longest recent run.
3. **Durability check**: similar load with normal vs suppressed next-day recovery.
4. **Strength progression**: only after routine logs contain sets/reps/load/RPE.

The dashboard should show progress beside load and recovery, not blended into them:

- recovery: body state today
- load: stress applied recently
- progress: capability change over weeks/months
- sleep opportunity: whether recovery had enough time
- health exceptions: oxygen, temperature, illness-like signals

## Validation questions

Before shipping an adaptation/progress lane, answer:

1. Which sport has enough repeated, comparable sessions to support progress analysis?
2. Do session summaries alone work, or are lap/record traces required?
3. Are HR and GPS coverage reliable enough for pace-at-HR analysis?
4. Does the candidate metric distinguish easy runs, long runs, workouts, races, and recovery runs?
5. Does the metric remain stable after excluding outliers, illness/travel days, and unusual routes?
6. Does the metric show a trend over weeks/months rather than just day-to-day noise?
7. Does the trend survive comparison against load and recovery context?
8. Does the metric support a user decision, or is it only interesting retrospectively?

## Data quality risks

- **Comparing unlike sessions:** route, elevation, weather, duration, and workout type can dominate
  apparent progress.
- **Survivorship bias:** filtering to successful hard sessions hides fatigue, skipped sessions, and
  recovery runs.
- **Effort ambiguity:** faster pace can mean better fitness or simply harder effort.
- **Sparse hard efforts:** PRs and threshold markers are not sampled regularly.
- **Device changes:** HR, GPS, and power estimates can shift with firmware, device, or sensor source.
- **Manual-log gaps:** strength progress is not measurable without exercise-level logging.
- **Load-progress confusion:** doing more work is not proof of adaptation.
- **Recovery-progress confusion:** feeling better is not proof of improved capability.

## Implementation sequence

1. Parse and store activity session summaries.
2. Profile sport mix, coverage, and repeated-session density.
3. Add lap/record parsing only where session summaries are too coarse.
4. Build sport-specific candidate features, starting with running.
5. Add sleep timing and previous-day load joins for context.
6. Run finding analyses for each candidate metric.
7. Promote only metrics that are stable, interpretable, and decision-relevant.

The product target is a **training state** dashboard with separate aligned lanes. Progress should
mean capability change, not a renamed recovery score and not a reward for higher load.
