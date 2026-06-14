# Central Dashboard Readiness Summary

This note summarizes the dashboard-axis documents and separates what Garmin Stats can responsibly
show on the central dashboard now from what requires new backend derivation, new data ingestion, or
more logged exposure.

**Current sequencing (2026-06-13):** the central dashboard first slate is in place. The active
frontend work is to DRY up and visually improve the generic metric detail dashboards
(`/heart-rate`, `/hrv`, `/sleep`, `/stress`, `/body-battery`, `/respiration`, `/skin-temp`,
`/pulse-ox`). During that refactor, central-dashboard additions should be limited to access points
and status lanes backed by existing data or already-designed backend contracts. Do not begin Garmin
activity/workout ingestion until the generic dashboards are stable.

The critical product conclusion is that the central dashboard should become a **training state**
surface, not a bigger recovery score. Recovery is one validated axis. The other useful lanes answer
different questions:

- recovery: what state is the body in today?
- health exceptions: is there an unusual context that should qualify interpretation?
- sleep opportunity: did recovery have enough time and regularity?
- load / strain: what stressor was applied recently?
- adaptation / progress: is capability improving over weeks or months?
- experiment adherence: what intervention exposure actually happened?

Do not blend these into one score until each lane has its own validated construct.

## Readiness table

| Axis | Product question | Current status | Dashboard now? | What is needed next |
| --- | --- | --- | --- | --- |
| Recovery state | How suppressed or strong is the current physiological recovery state? | Implemented and validated. | **Yes.** This is the current headline axis. | Keep wording narrow: physiological recovery state, not total readiness. |
| Recovery evidence | Which inputs moved the recovery score? | Implemented. | **Yes.** Evidence table should stay near the headline. | Keep Garmin composites labeled as derived context. |
| Health exceptions: oxygen and temperature | Is there an unusual oxygen or thermoregulation context? | Implemented for latest state and historical trajectory hover; broader exception coverage is still partial. | **Yes.** Show as compact flags, not a score. | Add stronger coverage state handling and avoid diagnosis language. |
| Sleep opportunity / regularity | Did the user create enough sleep time and stable timing? | Not implemented as an axis, but sleep-stage data is already parsed. | **Not yet.** | Backend derivation from existing parsed sleep levels: duration, window, midpoint, efficiency, debt, regularity. |
| Experiment adherence | Was the active protocol exposure satisfied? | Experiments, routines, exposure rows, and analysis are wired. Central dashboard integration is not ready. | **Not yet, except perhaps a link/status stub.** | Add central-dashboard contract, analyzability status, suppression reasons, and eventually dose-aware exposure. |
| Experiment response | Did an intervention change an outcome? | Blocked by current exposure history and confounding risk. | **No.** | More logged exposure, enough contrast, confounder joins, and non-circular outcome choices. |
| Load / strain | What training stress was applied recently? | Not implemented. | **No.** | Activity/session ingestion and daily load features. |
| Adaptation / progress | Is capability improving? | Not implemented. | **No.** | Activity/session data, sport-specific comparisons, and likely lap/record or routine exercise logs. |
| Advanced health exceptions | Is there respiratory, illness-like, sleep-disruption, or data-coverage context? | Candidate only. | **No, except simple coverage warnings where already known.** | More coverage states, sleep disruption parsing, manual context, and load/sleep joins. |

## What can go on the central dashboard now

### 1. Recovery state

This is the only fully ready central axis.

Use:

- recovery band and trend: suppressed / typical / strong plus improving / steady / declining
- current score in personal z units
- 7-day smoothed trajectory
- raw daily trace as supporting context
- detected sustained regimes

Do not describe this as "fitness," "training readiness," or "overall health." The score is a
compressed autonomic/recovery-state indicator built from co-moving resting and overnight signals.

### 2. Recovery evidence

The evidence table is dashboard-worthy because it prevents the score from becoming a black box.

Use:

- the seven input rows
- value, personal baseline, and signed delta
- source type, especially for Garmin-derived composites
- links to detail pages

Keep the critical caveat visible in product language: Body Battery and Sleep Score are Garmin
derivations. They are useful context, not independent raw physiology.

### 3. Health exception flags already implemented

Low oxygen and thermoregulation can stay on the central dashboard now.

Use:

- oxygen: normal / below range / no reading
- thermoregulation: normal / below baseline / above baseline / no reading
- current value and personal threshold/band
- historical state when the recovery trajectory is hovered
- missingness as unknown/no reading, not normal
- links to pulse-ox and skin-temperature detail pages

Do not turn these into a blended health score. Named flags are more honest and more useful.

## Near-term lanes that do not require new raw Garmin data

These are not ready for the dashboard today, but they mostly require backend derivation and API work
from data already present in the app.

### Sleep opportunity / regularity

The parser already extracts `sleep_level_mesgs`. That likely unlocks a useful V1 without a new data
source.

Needed before dashboard:

- derive sleep-stage intervals safely
- choose sleep date alignment, probably wake/recovery date
- handle midnight wrapping and final interval boundaries
- expose backend fields for sleep window, asleep duration, awake duration, efficiency, midpoint,
  short-sleep flag, irregular-sleep flag, and 7-day debt/regularity
- validate against Garmin-visible sleep windows and recovery outcomes

Recommended dashboard treatment:

- one sleep-opportunity lane, not another sleep score
- headline: last-night asleep duration vs target or personal baseline
- support: sleep window, efficiency, midpoint consistency, 7-day sleep debt

### Data coverage

Coverage is a legitimate dashboard guardrail because missing data changes interpretation.

Needed before dashboard:

- normalize coverage states for SpO2, HRV, skin temperature, respiration, and sleep
- show `unknown` when a flag cannot be evaluated
- avoid connecting charts across structural gaps

This can probably be built from existing daily metric missingness before adding new source data.

### Basic experiment adherence status

The experiment/routine system already has the right grain: one exposure row per
`experiment_id + date`. That means the dashboard can eventually show adherence state without
inventing a new data source.

Needed before central dashboard:

- a compact dashboard API contract for active experiment status
- explicit "collecting data / not analyzable yet" state
- suppression reason for response estimates
- stable wording around `full`, `partial`, `missed`, and `unknown`
- no effect estimate in the overview

Dose-aware exposure is still needed for better experiments, but basic adherence status can use the
existing exposure model once the dashboard contract is designed.

## Lanes that require new data ingestion or materially richer logs

### Load / strain

Do not infer load from recovery outputs. HRV, resting HR, stress, Body Battery, and sleep score are
not load.

Needed data:

- activity-session summaries from activity FIT files
- sport and sub-sport
- duration, distance, elevation
- average/max HR
- training effect and anaerobic training effect
- Garmin native training load fields if present
- data-quality flags for HR/GPS/power
- daily activity features and previous-day load joins

Optional but likely useful later:

- lap/record intensity detail
- time in HR zones
- Garmin `METRICS` discovery
- manual RPE and soreness

Dashboard should wait until activity coverage and previous-day recovery relationships are profiled.

### Adaptation / progress

Progress is the most data-hungry lane. It cannot be built from recovery and it should not be a
generic score.

Needed data:

- activity-session mart, same foundation as load
- sport-specific grouping
- pace/speed/power at comparable effort
- route/elevation context
- lap or record-level data for serious endurance comparisons
- repeated comparable sessions
- exercise-level routine logs for strength: sets, reps, load, RPE, pain/limitation notes

Dashboard should not show progress until one sport has enough repeated comparable sessions to make
a stable trend.

### Advanced health exceptions

The current oxygen and temperature flags are ready. Broader "illness-like" or respiratory flags are
not.

Needed data:

- sleep disruption and sleep-efficiency fields
- stronger data coverage states
- manual illness/travel/alcohol/altitude/medication context
- load features, so hard training is not mislabeled as illness-like stress

These should be developed as candidate findings before becoming product flags.

### Experiment response

The app should distinguish **experiment adherence** from **experiment response**.

Adherence can be shown once the dashboard contract is ready. Response should stay off the central
dashboard until the experiment is analyzable.

Needed before response claims:

- sustained logged exposure, not one tiny consecutive block
- enough baseline or comparison days
- enough non-missing outcome days
- enough exposure contrast
- expected lag specified before analysis
- confounder joins: sleep, load, health exceptions, manual context
- response metrics that do not circularly include the experiment target

The current meditation experiment is the caution case: five logged exposure days in one block is a
data-collection state, not a response estimate.

## Recommended dashboard sequence

### Now

Central dashboard should show:

1. Recovery state and trajectory.
2. Recovery evidence table.
3. Oxygen and thermoregulation flags.
4. Explicit unknown/missing states where available.
5. Links from central evidence/flags into the metric detail pages.

This is modest, but defensible.

### During the metric-dashboard refactor

The frontend refactor should focus on the detail pages first: shared chart builders, shared page
state, tighter axes, less duplicated CSS, and visual cleanup. Central-dashboard changes should stay
small and access-oriented:

1. Make drill-down paths from recovery evidence and flags obvious.
2. Add lightweight status/access stubs only when the backend contract already exists or is narrowly
   derivable from current data.
3. Avoid adding new dashboard lanes that would need activity/session ingestion.

### Next without new source ingestion

Add:

1. Sleep opportunity / regularity from parsed sleep stages.
2. Data coverage guardrail across the core recovery inputs.
3. Basic experiment adherence/status once the central-dashboard contract is designed.

These lanes explain recovery without pretending to be recovery.

### Later after generic dashboards and new ingestion

Add:

1. Load / strain after activity-session ingestion and validation.
2. Progress after sport-specific comparable-session analysis.
3. Experiment response only after adherence history and confounder coverage are sufficient.
4. Advanced health exceptions only after candidate flags are validated against known episodes and
   false-positive behavior.

## What not to put on the central dashboard

- A single "training state score" made from all lanes.
- A load score inferred from HRV, Body Battery, stress, or sleep score.
- A progress score inferred from higher load or better recovery.
- An experiment-response number for the current meditation experiment.
- A generalized illness score.
- A second sleep score based on Garmin's opaque sleep score.
- More cards for the sake of filling the overview.

The dashboard should earn each lane by tying it to a distinct user question and a distinct data
contract.
