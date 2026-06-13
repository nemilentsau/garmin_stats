# Experiment Adherence Data Requirements

This note defines what data is needed before Garmin Stats can add a defensible
**experiment adherence** lane to the central health-training dashboard.

Experiment adherence is not recovery, load, progress, sleep opportunity, or a health exception. It
is the behavioral exposure layer: what intervention was prescribed, what the user actually did, and
whether the exposure history is strong enough to interpret outcome changes.

## Current status

Experiment adherence is **partially implemented**.

The experiment domain already has the right grain:

- one `ExperimentExposure` row per `experiment_id + date`
- exposure derived from all linked routine entries for that experiment-date
- adherence states: `full`, `partial`, `missed`, `unknown`
- analysis adherence calendar that preserves unknown days inside the treatment window

This is the correct foundation. The important product constraint is that exposure is an
experiment-day property, not a routine-card property.

The current derivation is intentionally simple:

- completed entries count as `1.0`
- partial entries count as `0.5`
- skipped entries count as `0.0`
- pending-only days do not create an exposure row
- `full` requires every linked entry to be completed
- `missed` means every linked entry was skipped
- all other non-pending combinations are `partial`

That is enough to prevent a false card-level model, but it is not yet enough for robust
dose-response analysis.

## Product meaning

Experiment adherence should answer:

- What protocol was active on this date?
- What dose or routine work was prescribed?
- Did the user satisfy the protocol for the date?
- Was the exposure partial, missed, or unknown?
- Is there enough sustained exposure and contrast to study an outcome?
- Are confounders strong enough that any response claim should be suppressed?

This lane should not present behavior as physiology. It explains the input side of an experiment so
recovery, load, progress, sleep, and health exceptions can be interpreted against what the user did.

## Non-negotiable grain

The durable row should be:

```text
experiment_id + date
```

Do not derive experiment adherence from a single "best" routine card status. Do not treat multiple
linked routine cards on the same date as ambiguity. Multiple same-day cards are valid and expected
when the protocol prescribes multiple sessions or split doses.

The frontend should receive experiment-day exposure fields from the backend. It should not compute
adherence, exposure scores, dose totals, moving averages, or analyzability gates.

## Exposure states

Every experiment-day should resolve to one of these states for display:

| State | Meaning |
| --- | --- |
| `full` | The prescribed daily exposure was satisfied. |
| `partial` | Some exposure happened, but the daily prescription was not fully satisfied. |
| `missed` | The intervention was prescribed and explicitly skipped or missed. |
| `unknown` | The app cannot distinguish no exposure from missing tracking or pending logs. |

Missing data must never be treated as `missed`, and pending logs must never be treated as `full`.

## Source data needed

### Experiment protocol

Required fields:

- `experiment_id`
- name, goal, and hypothesis
- status: draft, active, completed
- baseline window
- treatment window
- expected lag days
- target outcome metrics and effect direction
- minimum effect size worth surfacing
- minimum adherence threshold
- linked routine ids
- confounder watch list

Needed extensions:

- explicit prescribed dose unit, such as minutes, reps, sessions, mg, servings, or binary exposure
- daily or weekly target dose
- acceptable completion window
- minimum valid partial threshold
- whether the intervention is additive, avoidant, or substitutional
- planned washout or rest days
- protocol version

### Routine prescription

Required fields:

- routine id
- assignment id
- card template id
- assignment date
- slot
- position
- `prescription_override_json`

Needed extensions:

- normalized prescribed quantity
- normalized prescribed unit
- expected duration when duration is the dose
- expected repetition count when reps are the dose
- whether an assignment is required, optional, or supporting context
- stable link from assignment to experiment exposure role

The existing routine artifact model already supports assignment-level prescription overrides. That
is the right place for day-specific duration, instructions, dose, and progression.

### Routine execution logs

Required fields:

- routine entry id or assignment occurrence id
- assignment id
- card template id
- log date
- status: pending, completed, partial, skipped
- completion timestamp in local date
- notes

Needed extensions:

- actual completed quantity
- actual completed unit
- actual duration when relevant
- partial-completion reason
- skipped reason
- source of the log: user, assistant, import, or correction
- edit history for protocol-critical changes

### Outcome and context data

Experiment adherence is only useful if it can be joined to outcomes and confounders.

Needed fields:

- recovery metrics by outcome date
- target metric values by lagged outcome date
- sleep opportunity and sleep regularity
- previous-day load/strain
- health exception flags
- alcohol, travel, illness, medication, altitude, or manual context logs
- data coverage flags for each outcome metric

For HRV-targeted experiments, avoid using a recovery composite that includes HRV as the primary
response. Otherwise the app risks circular interpretation.

## Derived fields

Candidate backend-owned fields for each `experiment_id + date` row:

| Field | Meaning |
| --- | --- |
| `prescribed_session_count` | Number of linked required routine occurrences for the date. |
| `completed_session_count` | Number completed. |
| `partial_session_count` | Number partially completed. |
| `skipped_session_count` | Number skipped. |
| `pending_session_count` | Number still pending or unlogged. |
| `prescribed_dose_total` | Sum of required dose for the date, if normalized. |
| `completed_dose_total` | Sum of actual completed dose, if normalized. |
| `dose_unit` | Minutes, reps, sessions, servings, etc. |
| `exposure_score` | Normalized 0-1 exposure completion. |
| `adherence_state` | `full`, `partial`, `missed`, or `unknown`. |
| `linked_routine_entry_ids` | All routine occurrences used for derivation. |
| `invalid_reason` | Why a row is unknown or excluded from analysis. |
| `protocol_version` | Version of the prescription used that date. |

The existing `exposure_score` can remain, but the app should eventually distinguish count-based
completion from dose-based completion.

## Dashboard behavior

The central dashboard should treat experiment adherence as a status and context lane.

Useful display elements:

- active experiment name
- today's prescribed exposure
- today's adherence state
- last 7/14/28-day adherence rate
- exposure streak or block length
- missed/partial/unknown day count
- whether the experiment is currently analyzable
- reason an effect estimate is suppressed

The dashboard should not show an experiment-response number until the analyzability gate passes.
Adherence can be displayed immediately; effect claims need stronger evidence.

## Analyzability gate

Before surfacing an effect estimate, require:

- enough treatment exposure days
- enough baseline or comparison days
- enough non-missing outcome days
- enough exposure contrast, not merely one tiny consecutive block
- adherence above the protocol threshold
- confounder coverage for the watched context fields
- no dominant health-exception block overlapping the treatment window
- lag window specified before analysis

The current `meditation-hrv-2026-03` finding is the caution case: five logged exposure days in one
consecutive block is a data gap, not an effect estimate. The dashboard should show that as
"collecting exposure data" or "not enough contrast," not as a weak positive or negative response.

## Validation questions

Before promoting this lane to a central dashboard axis:

- Do exposure rows exactly match the expected `experiment_id + date` grain?
- Are same-day multiple routine cards aggregated correctly?
- Can the app distinguish missed from unknown?
- Does partial exposure mean the same thing across renderers?
- Does the exposure score reflect dose or only card completion count?
- Are protocol changes versioned rather than silently rewriting history?
- Are outcome metrics joined at the correct lag?
- Are response claims suppressed when exposure history is too thin?
- Are manual confounders visible next to adherence rather than hidden inside the score?

## Data quality risks

- **Card-count bias:** a protocol with three short cards can look harder than one long card unless
  dose is normalized.
- **Partial ambiguity:** `partial` is currently weighted as half exposure, but the real dose could
  be 5% or 95%.
- **Unknown/missed confusion:** no log is not the same as a skipped intervention.
- **Protocol drift:** changing instructions mid-experiment can invalidate before/after comparisons.
- **Circular outcomes:** a target metric should not be tested primarily through a composite that
  contains the same target signal.
- **Confounded treatment blocks:** illness, travel, sleep loss, or training-load spikes can dominate
  the physiology during an exposure period.

## Implementation sequence

1. Keep the existing `experiment_id + date` exposure grain as the contract.
2. Add normalized prescribed and completed dose fields where card renderers can provide them.
3. Version protocol and prescription changes that affect exposure interpretation.
4. Expand exposure derivation from status/count based to dose-aware where possible.
5. Add an analyzability status and suppression reason to experiment analysis responses.
6. Join exposure rows to sleep, load, recovery, health exceptions, and manual confounders in an
   experiment-day mart.
7. Surface adherence immediately, but surface response estimates only after the analyzability gate
   passes.

