# Strength Training Analysis Questions

> Status: analyst backlog for future finding runs. These questions assume
> activity FIT ingestion exposes the fields proposed in
> `../STRENGTH_ACTIVITY_SCHEMA.md`.

This file is intentionally about session load and HR response. It does not treat
Garmin-inferred reps, exercise names, or set structure as reliable product data.
The useful source is the tracked strength session: duration, calories, HR trace,
HR zones, training effect, and Garmin training load.

Use the `finding-analyst` workflow for each run: define the question, snapshot
the source data, measure coverage/missingness, visualize before trusting
aggregates, and record confidence. Activity-session data can be decoded from raw
FIT files until a persisted activity mart exists; once the mart exists, consume
the mart instead of re-decoding.

## Analyst Controls

Strength questions should treat Garmin strength files as session-load data, not
as exercise programming data. Recovery and interaction analyses should at least
account for:

- same-day and previous-day runs
- meditation, breathing, or other recovery-session exposure
- sleep duration and sleep timing before the outcome day
- illness-like or high-stress days where existing health data suggests a
  non-training explanation
- ignored Garmin reps/exercise categories, so those fields do not leak into
  product-facing conclusions

## Data Readiness Pass

### S0. What strength data is analyzable right now?

Question: Which strength-session fields have enough coverage to support load
and recovery analysis?

Grain: one row per strength session, with optional record-level HR summaries.

Metrics:

- strength session count by month
- duration, calories, avg HR, max HR coverage
- training load and training effect coverage
- HR-zone coverage
- record-trace availability
- ignored Garmin rep/exercise diagnostic coverage

Output:

- coverage table
- missingness and source-regime notes
- recommended V1 strength feature set

Decision value: establishes that analysis should center on load and HR response,
not inferred exercises or reps.

### S1. Are strength sessions comparable, or do they split into different duration/intensity regimes?

Question: Do strength sessions cluster into distinct types based on duration,
HR, calories, and training load?

Grain: session-level strength summaries.

Metrics:

- timer duration
- elapsed duration
- average and max HR
- calories
- aerobic and anaerobic training effect
- training load
- HR-zone distribution

Output:

- distribution plots
- cluster or rule-of-thumb session groups, if defensible
- examples of high-load and low-load sessions

Decision value: determines whether one generic strength exposure flag is enough
or whether the app needs easy/moderate/hard strength categories.

## Load And Recovery

### S2. Does previous-day strength exposure predict next-morning recovery?

Question: Are strength sessions followed by consistent changes in HRV, resting
HR, body battery, sleep score, or stress?

Grain: daily strength features joined to next-day recovery metrics.

Metrics:

- previous-day strength session flag
- previous-day strength duration
- previous-day strength training load
- previous-day max HR / HR-zone time
- next-morning HRV, resting HR, sleep score, body battery, stress

Output:

- no-strength vs strength-day recovery comparison
- effect-size table by recovery metric
- stratification by session duration/load

Decision value: tells whether strength belongs as next-day recovery context and
whether it needs more than a binary exposure flag.

### S3. Which strength-load scalar is most useful?

Question: For strength sessions, does Garmin training load, duration, HR-zone
time, calories, or training effect best explain recovery response?

Grain: daily strength features and session summaries.

Metrics:

- training load
- timer duration
- calories
- avg/max HR
- HR-zone seconds
- aerobic and anaerobic training effect
- next-day recovery metrics

Output:

- scalar comparison table
- missingness-adjusted recommendation for V1 strength load

Decision value: chooses a practical strength-load feature without pretending the
watch knows exercise volume.

### S4. Is Garmin strength load internally consistent with HR response?

Question: Does Garmin strength training load mostly track duration and HR-zone
time, or does it contain extra useful signal?

Grain: session-level strength summaries.

Metrics:

- training load
- duration
- avg/max HR
- HR-zone seconds and percentages
- aerobic and anaerobic training effect
- calories

Output:

- load-vs-HR/duration relationship
- residual examples where Garmin load disagrees with HR response
- recommendation for whether to trust native load or prefer simpler HR/duration
  features

Decision value: validates the core strength-load scalar before using it in
recovery analysis.

### S5. Do hard strength sessions suppress recovery for more than one day?

Question: Are high-load or high-HR strength sessions followed by 1-day, 2-day,
or 3-day recovery changes?

Grain: event-study around high-load strength sessions.

Metrics:

- personal percentile of strength training load
- max HR and HR-zone time
- next 1/2/3 day HRV, resting HR, body battery, stress
- sleep duration as context

Output:

- event-study plots
- recovery-window recommendation
- caveats for sessions close to runs

Decision value: informs lag windows and whether the app should flag strength
load as same-day, next-day, or multi-day context.

### S6. Are hard strength sessions after low-recovery mornings unusually costly?

Question: When a hard strength session follows a low-recovery morning, is the
next-day recovery response worse than hard strength after normal recovery?

Grain: recovery-day metrics, same-day strength load, and next-day recovery
outcomes.

Metrics:

- same-morning HRV, resting HR, body battery, sleep score
- same-day strength load, duration, max HR, HR-zone time
- next-day HRV, resting HR, body battery, stress
- same-day running load as a confounder

Output:

- event comparison for hard-after-low-recovery vs hard-after-normal-recovery
- sample-size warning if the pattern is rare
- candidate threshold only if the effect is stable

Decision value: directly tests a possible dashboard warning condition.

## Interaction With Running

### S7. Does strength training change next-run behavior or cost?

Question: Are runs after strength sessions shorter, slower, higher-HR, or lower
load than comparable runs without prior strength?

Grain: strength-day features joined to the next run.

Metrics:

- prior 24/48 hour strength exposure
- next-run distance, duration, pace, HR, training load
- next-run aerobic efficiency where HR exists

Output:

- next-run comparison with and without recent strength
- filter report for HR availability and run type

Decision value: tests whether strength sessions should be treated as context for
running-progress interpretation.

### S8. Does combined run + strength load produce different recovery response than either alone?

Question: Are days with both running and strength followed by larger recovery
changes than run-only or strength-only days?

Grain: daily activity-type combinations joined to next-day recovery.

Metrics:

- run-only, strength-only, both, neither categories
- total training load
- run load and strength load separately
- next-day recovery metrics

Output:

- category comparison table
- interaction plot
- sample-size warnings for sparse categories

Decision value: decides whether the dashboard needs combined-load context or
separate sport rows are sufficient.

## Consistency And Habit

### S9. What is the sustainable strength-training rhythm?

Question: Is there a weekly strength cadence that appears compatible with stable
recovery?

Grain: weekly strength frequency joined to weekly recovery summaries.

Metrics:

- strength sessions per week
- weekly strength duration
- weekly strength training load
- weekly median HRV, resting HR, sleep score
- run load as a confounder

Output:

- weekly cadence trend
- recovery overlay
- candidate sustainable-frequency range, if any

Decision value: supports habit-level guidance rather than single-session
reaction.

### S10. Are missed strength weeks associated with lower or higher recovery?

Question: Do weeks without strength sessions look like recovery weeks,
interruption weeks, or simply lower-load weeks?

Grain: weekly strength exposure and recovery/load context.

Metrics:

- zero-strength weeks
- run load in the same week
- recovery metrics
- sleep and stress context

Output:

- comparison of zero-strength vs strength weeks
- interpretation caveats

Decision value: prevents overinterpreting missing strength sessions as either
good recovery or bad consistency without evidence.

## Session HR Response

### S11. Are strength sessions producing meaningful cardiovascular load?

Question: How much time do strength sessions spend in elevated HR zones, and
does that vary over time?

Grain: session-level HR-zone summaries.

Metrics:

- HR-zone seconds and percentages
- average and max HR
- training effect
- session duration

Output:

- HR-zone distribution across sessions
- month-over-month intensity trend
- high-cardiovascular-load strength examples

Decision value: determines whether strength should be shown as meaningful
internal load, not just a binary exercise marker.

### S12. Does strength HR response change over time at similar duration/load?

Question: For similar-duration strength sessions, is HR response trending down,
up, or stable?

Grain: session summaries, grouped by comparable duration/load buckets.

Metrics:

- avg HR
- max HR
- HR-zone percentages
- training load
- duration

Output:

- HR response by month within comparable session buckets
- warning if sessions are too heterogeneous

Decision value: possible durability/adaptation signal, but only if session
comparability is strong enough.

## Candidate Scout Passes

Run these as scout passes only; do not promote unless a specific signal appears:

- Are strength sessions more likely after high-recovery mornings?
- Are high-load strength sessions followed by worse sleep that night?
- Does time of day of strength training affect sleep or next-morning recovery?
- Do strength sessions reduce same-day stress or body battery slope?
- Are Garmin inferred reps so erratic that they should be dropped even from raw
  diagnostics?

## First Recommended Analyst Runs

1. S0: field coverage and analyzable slices.
2. S4: Garmin strength load sanity check against HR response.
3. S2: previous-day strength exposure/load vs next-morning recovery.
4. S6: hard strength after low-recovery mornings.
5. S8: combined run + strength load vs single-activity days.
6. S11: cardiovascular load distribution during strength sessions.
