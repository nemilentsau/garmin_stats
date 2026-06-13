# Sleep Opportunity / Regularity Data Requirements

This note defines what data is needed before Garmin Stats can add a defensible
**sleep opportunity / regularity** lane to the central health-training dashboard.

Sleep opportunity is not recovery. Recovery describes the body's current physiological state. Sleep
opportunity describes whether enough time was available for recovery. Sleep regularity describes
whether that opportunity happened at a stable time.

## Current status

Sleep opportunity / regularity is **not implemented** as a dashboard axis.

The parser already extracts `sleep_level_mesgs` from `SLEEP_DATA` files. These provide timestamped
sleep-stage markers (`awake`, `light`, `deep`, `rem`) and are the best current source for deriving
duration and timing. The daily mart currently persists only Garmin sleep scores (`sleep_score`,
`deep_score`, `rem_score`), so it cannot yet answer opportunity or regularity questions.

Do **not** use Garmin `sleep_score` as the main input for this axis. Sleep score is an opaque
Garmin-derived composite. It can be useful context, but opportunity and regularity should come from
timing and duration fields first.

## Product meaning

Sleep opportunity / regularity should answer:

- Did I give recovery enough time?
- Was my sleep window consistent enough to support adaptation?
- Was poor recovery plausibly explained by short or irregular sleep?
- Did I sleep enough before or after high training load?

That makes this lane explanatory. It helps interpret recovery and load, but it should not be folded
into the recovery score.

## Vocabulary

### Sleep opportunity

The time available for sleep.

Candidate definitions:

- sleep window from first sleep-stage marker to final wake marker
- bedtime to wake time, if Garmin sleep event messages provide better boundaries
- target-relative duration, such as hours below an 8-hour target or personal target

Opportunity answers "was there enough time?" It does not prove the sleep was good.

### Sleep duration

The amount of time classified as asleep.

Candidate definition:

- total time in `light`, `deep`, and `rem` stages, excluding `awake`

Duration answers "how much sleep happened inside the opportunity window?"

### Sleep efficiency

The share of the sleep window spent asleep.

Candidate definition:

- `asleep_duration_hours / sleep_window_hours`

Efficiency separates "went to bed for long enough" from "actually slept for long enough."

### Sleep regularity

The consistency of sleep timing.

Candidate definitions:

- bedtime variability
- wake-time variability
- sleep-midpoint variability
- rolling 7-day or 14-day deviation from personal typical midpoint

Midpoint is probably the cleanest headline because it captures both late nights and late wake-ups.

### Sleep debt

Accumulated shortfall against a target.

Candidate definition:

- sum over the last 7 days of `max(0, target_sleep_hours - asleep_duration_hours)`

The target should be explicit. It may start as 8 hours, but personal median or outcome-optimized
targets should be tested before using it as a durable dashboard contract.

## Source data needed

### 1. Sleep-stage intervals

The current parser extracts:

| Source | Field | Current status |
| --- | --- | --- |
| `sleep_level_mesgs` | `timestamp` | Parsed and shifted to local time through the sleep timestamp path. |
| `sleep_level_mesgs` | `sleep_level` | Parsed as `awake`, `light`, `deep`, `rem`, or `unknown`. |

Needed derived fields:

| Field | Meaning |
| --- | --- |
| `bedtime_local_minutes` | Sleep-window start, in local minutes after midnight. |
| `wake_time_local_minutes` | Sleep-window end, in local minutes after midnight. |
| `sleep_window_hours` | Time from sleep-window start to end. |
| `asleep_duration_hours` | Total light + deep + REM duration. |
| `awake_duration_hours` | Total awake duration inside the window. |
| `sleep_efficiency` | Asleep duration divided by sleep window. |
| `sleep_midpoint_local_minutes` | Midpoint of the sleep window or asleep interval. |
| `light_duration_hours` | Light sleep duration. |
| `deep_duration_hours` | Deep sleep duration. |
| `rem_duration_hours` | REM sleep duration. |
| `stage_unknown_duration_hours` | Unknown/unusable stage duration, if present. |

Implementation caveat: stage markers are starts, not necessarily complete intervals by themselves.
Durations require ordering markers and deciding how to handle the final interval. If Garmin event
messages provide more accurate start/stop boundaries, prefer them for window endpoints.

### 2. Sleep event and metadata messages

The sleep schema records `event_mesgs` as not parsed and several unknown sleep messages as possible
metadata. These may contain better sleep start/stop boundaries.

Needed work:

- inspect `event_mesgs` for sleep start and stop events
- inspect `unknown_273`, `unknown_382`, and `unknown_521` only if stage markers are insufficient
- document field names, units, and coverage before using them
- prefer event start/stop for window boundaries if they are reliable

### 3. Garmin sleep assessment fields

The parser already extracts:

- `overall_sleep_score`
- `deep_sleep_score`
- `light_sleep_score`
- `rem_sleep_score`
- `awake_time_score`
- `awakenings_count`
- `average_stress_during_sleep`

The schema also documents unextracted assessment fields:

- `sleep_duration_score`
- `sleep_quality_score`
- `sleep_recovery_score`
- `sleep_restlessness_score`
- `interruptions_score`
- `awakenings_count_score`

These are Garmin-derived scores. They may help validate or explain derived timing fields, but they
should not replace raw duration and timing as the source of the axis.

### 4. Context for interpretation

Sleep opportunity is most useful when joined with:

- previous-day training load
- next-morning recovery state
- alcohol
- illness
- travel
- routines/experiments
- planned wake constraints, if logged

Without context, short sleep is descriptive. With context, it can explain why a high-load day or low
recovery day happened.

## Candidate daily features

Recommended V1 fields on the recovery day mart:

| Field | Meaning |
| --- | --- |
| `sleep.bedtime_local_minutes` | Sleep-window start in local time. |
| `sleep.wake_time_local_minutes` | Sleep-window end in local time. |
| `sleep.sleep_window_hours` | Opportunity window. |
| `sleep.asleep_duration_hours` | Actual sleep duration. |
| `sleep.awake_duration_hours` | Awake time inside window. |
| `sleep.sleep_efficiency` | Asleep/window ratio. |
| `sleep.midpoint_local_minutes` | Sleep timing anchor. |
| `sleep.midpoint_consistency_delta_minutes` | Difference from personal typical midpoint. |
| `sleep.duration_delta_hours` | Difference from target or personal baseline. |
| `sleep.short_sleep_flag` | Duration below personal or fixed threshold. |
| `sleep.irregular_sleep_flag` | Midpoint deviation above personal threshold. |

Recommended rolling features:

| Field | Meaning |
| --- | --- |
| `sleep.sleep_debt_7d_hours` | Seven-day accumulated shortfall. |
| `sleep.asleep_duration_ma7_hours` | Seven-day average actual sleep. |
| `sleep.midpoint_sd_7d_minutes` | Seven-day regularity spread. |
| `sleep.efficiency_ma7` | Seven-day average efficiency. |

The frontend should display these fields only. It should not compute duration, midpoint, sleep debt,
or regularity.

## Candidate dashboard metrics

These are candidates, not validated contracts.

### Sleep opportunity

Primary candidate:

- **last-night asleep duration vs target**

Supporting values:

- sleep window
- asleep duration
- awake duration
- sleep efficiency
- 7-day average asleep duration

### Sleep debt

Primary candidate:

- **7-day sleep debt**

Supporting values:

- number of short-sleep nights in the last 7 days
- biggest single-night shortfall
- trend vs previous week

### Regularity

Primary candidate:

- **7-day sleep-midpoint variability**

Supporting values:

- bedtime variability
- wake-time variability
- latest midpoint deviation from personal typical midpoint

### Context flags

Candidate flags:

- short sleep before high load
- high load after short sleep
- low recovery after adequate sleep
- low recovery after short or irregular sleep
- irregular sleep during a rising-load week

These should explain the training state. They should not be blended into the recovery score.

## Validation questions

Before shipping this lane, answer:

1. Do derived sleep start/end times match Garmin-visible sleep windows closely enough?
2. Do stage-marker-derived durations match Garmin's duration-related assessment fields?
3. Is asleep duration, sleep window, or sleep efficiency most useful for explaining recovery?
4. Is midpoint regularity more useful than bedtime or wake-time regularity?
5. Does short sleep predict next-day recovery suppression after controlling for previous-day load?
6. Does irregular sleep predict next-day recovery, or does it mostly proxy stress/travel?
7. Should sleep debt use a fixed 8-hour target, a personal target, or an outcome-derived target?
8. How should naps be represented: separate recovery opportunity, separate habit, or ignored in V1?

## Data quality risks

- **Overnight date alignment:** the sleep date should usually be the wake/recovery date.
- **Local-time handling:** FIT timestamps are UTC and must go through the local timestamp shift path.
- **Midnight wrapping:** naive averages of bedtime or midpoint can be wrong across midnight.
- **Missing final interval:** sleep-stage markers may not include explicit end timestamps.
- **Event ambiguity:** stage markers may not equal lights-out or out-of-bed.
- **Naps:** nap files are rare and not parsed; they should not silently merge into nighttime sleep.
- **Travel and DST:** timezone shifts can look like irregularity unless explicitly handled.
- **Garmin score leakage:** sleep score and sub-scores are derived summaries, not raw opportunity.

## Implementation sequence

1. Derive sleep intervals from existing `sleep_level_mesgs`.
2. Validate derived start/end/duration against available assessment fields and visible examples.
3. Inspect `event_mesgs` if stage markers do not give reliable window boundaries.
4. Add daily sleep timing fields to the recovery day mart.
5. Add rolling duration, debt, and regularity features in the backend.
6. Join sleep features with load and next-morning recovery for validation.
7. Promote only metrics that explain user decisions better than Garmin sleep score alone.

The product target is a **training state** dashboard with separate aligned lanes. Sleep opportunity
should explain whether recovery had enough time and regularity to happen; it should not become a
renamed recovery score.
