# Running Analysis Questions

> Status: analyst backlog for future finding runs. Running FIT ingestion now
> exists and exposes the fields these questions assume — see
> `../../reference/run-activities.md` for the shipped contract. None of the
> analyses below have been run yet.

This file is not a dashboard spec. It is a queue of question-led analyses that
should be run before deciding which running metrics deserve product surface.

Use the `finding-analyst` workflow for each run: define the question, snapshot
the source data, measure coverage/missingness, visualize before trusting
aggregates, and record confidence. Activity-session data can be decoded from raw
FIT files until a persisted activity mart exists; once the mart exists, consume
the mart instead of re-decoding.

## Analyst Controls

Running questions should not be analyzed as isolated run-only slices unless the
question is purely about running data quality. Recovery and progress runs should
at least account for:

- same-day and previous-day strength sessions
- meditation, breathing, or other recovery-session exposure
- sleep duration and sleep timing before the outcome day
- illness-like or high-stress days where existing health data suggests a
  non-training explanation
- source coverage regimes, especially the date-patterned HR availability

## Data Readiness Pass

### R0. What running data is analyzable right now?

Question: Which running fields have enough coverage to support analysis across
the downloaded range?

Grain: one row per run session, with optional lap and record summaries.

Metrics:

- run count by month
- HR coverage by month
- distance, duration, pace, elevation, training load, training effect coverage
- power, cadence, stride, stance, vertical oscillation coverage
- GPS/lap/record availability

Output:

- coverage table
- field missingness by month
- recommended V1 running feature set

Decision value: prevents building questions around fields that only exist for a
small or biased slice of runs.

### R1. Are there device or firmware coverage breaks?

Question: Did the meaning or availability of running fields change during the
year?

Grain: session and record coverage over time.

Metrics:

- first/last date per field
- abrupt starts/stops in HR, power, running dynamics, VO2 max, training load
- distribution shifts around coverage breaks

Output:

- timeline of source coverage regimes
- list of fields that require regime-aware filtering

Decision value: separates physiology changes from data-source changes.

## Load And Recovery

### R2. Does previous-day running load predict next-morning recovery?

Question: After a run, do next-morning HRV, resting HR, body battery, sleep
score, or stress shift in a consistent direction?

Grain: daily running features joined to next-day recovery metrics.

Metrics:

- previous-day run training load
- previous-day run duration and distance
- previous-day max aerobic and anaerobic training effect
- same-day strength and recovery-session exposure as context
- next-morning HRV, resting HR, sleep score, body battery, stress

Output:

- effect-size table by recovery metric
- stratified plots for no-run, easy-run, moderate-run, and hard-run days
- caveat list for sleep duration and missing HR coverage

Decision value: tells whether running load belongs in the recovery dashboard as
context and which lag window is useful.

### R3. Which running-load scalar is most informative?

Question: Among Garmin training load, duration, distance, training effect, and
HR-zone time, which best explains next-day recovery changes?

Grain: daily features and session-level run summaries.

Metrics:

- training load
- timer duration
- distance
- aerobic / anaerobic training effect
- time in HR zones where HR exists
- next-day recovery metrics

Output:

- correlation/effect-size comparison
- missingness-adjusted recommendation for a V1 load scalar

Decision value: chooses the simplest defensible running load feature.

### R4. What is the useful running lag window?

Question: Is recovery response more associated with yesterday's run, 2-day load,
7-day load, or acute-vs-baseline load?

Grain: daily running features with rolling windows.

Metrics:

- 1-day, 2-day, 7-day, and 28-day running load sums
- acute-to-baseline ratios
- next-day and next-2-day recovery outcomes

Output:

- lag comparison table
- plots of load windows against recovery outcomes

Decision value: informs whether the dashboard should show yesterday's load,
rolling load, or both.

### R5. Do recovery signals influence next-run choices?

Question: After low-recovery mornings, does the next run become shorter, easier,
or less frequent?

Grain: recovery-day metrics joined to the next run within 24-72 hours.

Metrics:

- morning HRV, resting HR, body battery, sleep score, stress
- next-run distance, duration, pace, training load, training effect
- next-run HR where available
- time since prior hard session

Output:

- comparison of next-run behavior after low, typical, and high recovery mornings
- evidence for or against self-regulation in training choices

Decision value: tells whether recovery metrics should be interpreted as
decision support before activity, not only as an outcome after load.

### R6. Are hard runs after low-recovery mornings unusually costly?

Question: When a hard run follows a low-recovery morning, is the next-day
recovery response worse than hard runs after normal recovery?

Grain: recovery-day metrics, same-day run load, and next-day recovery outcomes.

Metrics:

- same-morning HRV, resting HR, body battery, sleep score
- same-day run load, duration, training effect, HR-zone time
- next-day HRV, resting HR, body battery, stress

Output:

- event comparison for hard-after-low-recovery vs hard-after-normal-recovery
- sample-size warning if the pattern is rare
- candidate threshold only if the effect is stable

Decision value: directly tests a possible dashboard warning condition.

## Running Progress

### R7. Is easy-run aerobic efficiency changing?

Question: At comparable aerobic effort, is pace improving, worsening, or stable?

Grain: session summaries first; record-level steady-state segments if needed.

Filters:

- running only
- HR present
- exclude obvious hard/interval/race sessions unless separately labeled
- control or annotate elevation

Metrics:

- pace at comparable average HR band
- HR at comparable pace band
- elevation-adjusted pace where available
- month-over-month distribution

Output:

- pace-vs-HR scatter by month
- trend of easy-run pace at target HR
- coverage and filter-exclusion report

Decision value: first candidate for a real running progress surface.

### R8. Do route and elevation differences dominate pace comparisons?

Question: Before claiming pace/HR progress, are route, elevation, and surface
differences large enough to explain the apparent trend?

Grain: session summaries plus GPS/elevation-derived route features where
available.

Metrics:

- distance, ascent, descent, grade-adjusted speed if available
- route similarity or coarse route buckets if derivable
- pace and HR by route/elevation bucket
- month-over-month pace/HR trend after route/elevation filtering

Output:

- route/elevation comparability report
- recommendation for whether R7 can use session averages or needs route/segment
  filtering

Decision value: prevents false progress claims from comparing unlike runs.

### R9. Is running capacity increasing without recovery cost?

Question: Is weekly running volume or longest-run duration rising, and does that
increase coincide with stable recovery?

Grain: weekly running features joined to daily recovery summaries.

Metrics:

- weekly run duration
- weekly run distance
- longest run duration in trailing 28 days
- run frequency
- weekly median HRV / resting HR / sleep score

Output:

- weekly capacity trend
- recovery overlay
- periods of volume increase with and without recovery suppression

Decision value: distinguishes useful capacity growth from strain accumulation.

### R10. Do long runs have a different recovery signature than ordinary runs?

Question: Are long runs followed by larger or longer recovery changes than
shorter runs?

Grain: session-level long-run classification joined to next 1-3 recovery days.

Metrics:

- longest-run percentile within personal history
- duration and distance
- training load
- next 1/2/3 day HRV, resting HR, body battery, stress

Output:

- event-study plot around long-run days
- comparison to ordinary-run days

Decision value: supports long-run-specific guidance instead of generic load
warnings.

## Session Quality

### R11. How often are runs easy, moderate, hard, or interval-like?

Question: What is the actual intensity distribution of running sessions?

Grain: session summaries; lap/record detail where HR exists.

Metrics:

- aerobic and anaerobic training effect
- training load
- avg/max HR
- HR-zone time
- pace variability and lap variability

Output:

- session classification rules proposed from observed data
- monthly intensity mix
- examples of ambiguous sessions

Decision value: determines whether the app can describe training balance.

### R12. Is within-run HR drift measurable?

Question: On steady runs with HR records, does HR rise relative to pace over the
session?

Grain: record-level running traces.

Filters:

- HR present
- continuous GPS/speed trace
- exclude very short runs and obvious intervals
- control or annotate elevation

Metrics:

- first-half vs second-half HR at comparable pace
- pace change at comparable HR
- temperature unavailable caveat

Output:

- HR-drift distribution
- candidate drift threshold for flagging unusually costly runs

Decision value: could support a session-quality signal, but only if the data is
stable enough.

## Candidate Scout Passes

Run these as scout passes only; do not promote unless a specific signal appears:

- Do running dynamics change before recovery dips?
- Is cadence associated with pace or HR efficiency after controlling for speed?
- Are trail/hilly runs too rare to model separately?
- Does VO2 max move with source-derived efficiency metrics, or is it just Garmin
  vendor context?
- Are runs after poor sleep measurably slower, shorter, or higher-HR?
- Does run time of day affect that night's sleep or next-morning recovery?
- Are seasonal/weather effects large enough that pace/HR progress needs an
  external weather source before product claims?

## First Recommended Analyst Runs

1. R0: field coverage and analyzable slices.
2. R2: previous-day running load vs next-morning recovery.
3. R6: hard runs after low-recovery mornings.
4. R11: intensity distribution and candidate session classes.
5. R8: route/elevation comparability gate.
6. R7: easy-run aerobic efficiency trend.
