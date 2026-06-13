# Health Exceptions Data Requirements

This note defines what data is needed before Garmin Stats can add a defensible
**health exceptions** lane to the central health-training dashboard.

Health exceptions are not recovery, load, progress, or sleep opportunity. They are guardrail flags:
signals that something unusual may be happening and that today's recovery/load/progress should be
interpreted cautiously.

## Current status

Health exceptions are **partially implemented**.

The dashboard already computes two per-day flags:

- **Low oxygen** from nightly `spo2_avg`, with `spo2_min` as supporting nadir detail.
- **Thermoregulation** from skin-temperature deviation.

These flags are deliberately outside the recovery score. They answer "is there an unusual health
context?" rather than "how recovered am I?"

Do **not** combine health exceptions into one health score. A compact strip of named flags is more
honest and more actionable than a blended number.

## Product meaning

Health exceptions should answer:

- Is there a low-oxygen or thermoregulation signal that changes how I read today's state?
- Is a low recovery day possibly illness-like rather than training-load-related?
- Is missing sensor coverage hiding the very signal I would need to interpret the day?
- Should today's load/progress/recovery claims be softened because a health context is present?

This lane should use descriptive language only. It should not diagnose illness, altitude exposure,
infection, or medical risk.

## Flag states

Every health exception should use an explicit state:

| State | Meaning |
| --- | --- |
| `clear` | Data is present and the rule did not fire. |
| `watch` | Mild or partial pattern; worth noticing, not a strong flag. |
| `flag` | Rule fired decisively. |
| `unknown` | Required data is missing or coverage is too weak. |

Missing data must never be treated as `clear`.

Each rendered flag should show:

- current value
- personal threshold or band
- whether the signal is one-day or sustained
- coverage state
- link to the relevant detail page

## Implemented flags

### Low oxygen

Purpose:

- Detect unusually low overnight oxygen relative to personal history.

Current source fields:

- `spo2_avg` as the primary flag metric
- `spo2_min` as supporting nadir detail
- SpO2 coverage/missingness

Current rule:

- `spo2_avg < personal median - 2.5 * MAD`

Current evidence:

- The threshold lands near 90.5% on the validated snapshot.
- It catches the real Apr 21-27 low-oxygen episode as a coherent block.
- `spo2_min` is too coarse as the primary flag and catches fewer episode days.
- Missing SpO2 occurs in structural blocks and must be surfaced as `unknown`.

Dashboard behavior:

- show `clear`, `flag`, or `unknown`
- show current `spo2_avg`, threshold, and `spo2_min`
- show structural coverage gaps instead of connecting across missing spans

### Thermoregulation

Purpose:

- Detect unusually high or low skin-temperature deviation relative to personal history.

Current source fields:

- `skin_temp_deviation`
- `skin_temp_nightly_value` as supporting detail

Current rule:

- `skin_temp_deviation` outside `personal median +/- 2.5 * MAD`

Current evidence:

- The validated snapshot produces a personal band around `[-0.91, +0.83] C`.
- This flag is independent of the low-oxygen flag in the Apr episode.

Dashboard behavior:

- show `clear`, `flag`, or `unknown`
- show deviation, personal band, and direction
- avoid sticky multi-day recent chips unless validated; temperature flags can become too noisy if
  the lookback window is too long

## Candidate future flags

These are candidates, not validated contracts.

### Respiratory stress

Question:

- Is there a respiratory-looking pattern that changes how we interpret recovery?

Candidate ingredients:

- low `spo2_avg`
- low `spo2_min`
- elevated respiration
- elevated resting HR
- normal or non-flagged skin temperature

Use case:

- distinguish a low-oxygen/respiration context from generic low recovery or thermoregulation.

Validation target:

- catch coherent respiratory-looking blocks without firing on ordinary training fatigue.

### Illness-like multi-system pattern

Question:

- Are several physiological signals moving in a pattern consistent with illness-like stress?

Candidate ingredients:

- skin-temperature deviation high or low
- resting HR elevated
- HRV suppressed
- respiration elevated
- sleep disrupted
- stress elevated
- subjective illness flag, if logged

Use case:

- explain why recovery is low when load does not explain it.

Required caveat:

- label as "illness-like pattern" or "multi-system flag," never as a diagnosis.

### Sleep disruption exception

Question:

- Was sleep unusually fragmented or disrupted, separate from simply being short?

Candidate ingredients:

- awakenings count
- awake duration inside sleep window
- sleep efficiency
- `SLEEP_DISRUPTIONS` file fields, once parsed
- Garmin restlessness/interruption assessment fields as supporting vendor context

Use case:

- explain low recovery after apparently adequate sleep duration.

### Data coverage exception

Question:

- Is required sensor coverage too weak to trust the day's interpretation?

Candidate ingredients:

- missing SpO2
- missing HRV
- missing skin temperature
- low sleep-stage coverage
- off-wrist / invalid respiration or stress readings
- structural gap spans

Use case:

- prevent "no flag" from being read as "all clear" when data is absent.

This is a first-class health exception. Data absence can be the reason the dashboard should be
cautious.

### Manual health context

Question:

- Did the user explicitly log something that should frame the day?

Candidate ingredients:

- illness
- travel
- alcohol
- altitude
- medication
- unusual heat/cold exposure
- vaccination or other acute stressor, if logged

Use case:

- add human context that sensor data cannot infer safely.

Manual health context should be shown as context, not backfilled into biometric flag rules unless
validated.

## Source data needed

### Current Garmin sources

| Source | Fields | Current role |
| --- | --- | --- |
| SpO2 readings | `spo2_avg`, `spo2_min`, coverage gaps | Low-oxygen flag. |
| Skin temperature | `skin_temp_deviation`, `skin_temp_nightly_value` | Thermoregulation flag. |
| Heart rate | resting HR, HR avg | Candidate illness-like context. |
| Respiration | respiration avg and coverage | Candidate respiratory/illness-like context. |
| HRV | nightly HRV | Candidate illness-like context and recovery context. |
| Stress | stress avg | Candidate illness-like context. |
| Sleep | awakenings, sleep stages, future disruption fields | Candidate sleep-disruption context. |

### Sources to add or expand

| Source | Needed fields |
| --- | --- |
| `SLEEP_DISRUPTIONS` | overnight severity, period severity, timestamps/coverage. |
| Sleep timing fields | sleep efficiency, awake duration, disruption-oriented features. |
| Manual check-ins | illness, travel, alcohol, altitude, medication, subjective symptoms. |
| Activity/load features | previous-day load to avoid confusing hard training with illness-like patterns. |

## Candidate daily features

Recommended explicit fields:

| Field | Meaning |
| --- | --- |
| `health.oxygen_state` | `clear` / `flag` / `unknown`. |
| `health.oxygen_value` | Current `spo2_avg`. |
| `health.oxygen_threshold` | Personal low threshold. |
| `health.oxygen_nadir` | Supporting `spo2_min`. |
| `health.oxygen_coverage_state` | Present, partial, missing, or structural gap. |
| `health.thermo_state` | `clear` / `flag` / `unknown`. |
| `health.thermo_value` | Current skin-temperature deviation. |
| `health.thermo_band_low` / `health.thermo_band_high` | Personal thermoregulation band. |
| `health.respiratory_state` | Future respiratory-stress flag state. |
| `health.illness_like_state` | Future multi-system flag state. |
| `health.sleep_disruption_state` | Future sleep-disruption flag state. |
| `health.data_quality_state` | Coverage guardrail state. |

Store the ingredients used for each flag alongside the state so the frontend can explain why a flag
fired.

## Threshold policy

Use personal robust thresholds by default:

- median as the center
- MAD scaled by 1.4826 as robust spread
- one-sided thresholds where physiology has one concerning direction
- two-sided thresholds where both high and low deviations matter
- minimum history before a threshold is trusted

Absolute medical-style thresholds can be shown as context only when appropriate. They should not
replace personal thresholds without evidence. In this dataset, absolute SpO2-min cutoffs are
misleading because the nightly minimum usually runs low.

## Dashboard behavior

The dashboard should show health exceptions as a compact flag strip or aligned lane, not as gauges.

Recommended display:

- Oxygen: `clear` / `flag` / `unknown`
- Temperature: `clear` / `flag` / `unknown`
- Illness-like: `clear` / `watch` / `flag` / `unknown`
- Data coverage: `ok` / `partial` / `missing`

Each flag should be clickable into its detail page or evidence panel.

Avoid:

- one blended health score
- red/green color as the only encoding
- diagnosis language
- hiding missingness
- surfacing noisy one-day blips as major events without persistence rules

## Validation questions

Before shipping additional health exceptions, answer:

1. How often does each flag fire?
2. Does it fire in coherent blocks or random one-offs?
3. Does it catch known unusual periods, such as the Apr 21-27 low-oxygen episode?
4. Does it stay quiet during ordinary training fatigue and recovery variation?
5. Does adding load and sleep context reduce false illness-like flags?
6. Does missingness cluster structurally, and is it rendered as `unknown`?
7. Does the flag help interpret recovery/load/progress, or does it merely duplicate a detail chart?
8. Does the flag support a user decision without implying medical diagnosis?

## Data quality risks

- **Missingness as false clear:** absent SpO2 or HRV can hide the relevant signal.
- **Sensor artifacts:** wrist contact, motion, and fit can create bad readings.
- **Structural gaps:** long coverage gaps need explicit rendering.
- **Training confounding:** hard training can elevate HR, stress, and respiration without illness.
- **Travel/altitude confounding:** oxygen, sleep, HR, and temperature can shift for non-illness
  reasons.
- **Temperature ambiguity:** skin temperature is deviation from personal baseline, not a diagnosis.
- **Over-alerting:** one-day mild deviations can make the dashboard noisy.
- **Medical overclaiming:** the app should describe data patterns, not diagnose conditions.

## Implementation sequence

1. Keep oxygen and thermoregulation as explicit flags outside the recovery score.
2. Add structured coverage states for SpO2, HRV, skin temperature, respiration, and sleep.
3. Parse `SLEEP_DISRUPTIONS` only after sleep timing/coverage basics are stable.
4. Add manual health-context check-ins where they already fit product flows.
5. Prototype respiratory and illness-like candidates as finding runs, not product contracts.
6. Validate firing frequency, persistence, and known-event capture.
7. Promote only flags that improve interpretation without excessive noise.

The product target is a **training state** dashboard with separate aligned lanes. Health exceptions
should sit beside recovery, load, progress, and sleep opportunity as guardrails that explain when
ordinary training-state interpretation may be incomplete.
