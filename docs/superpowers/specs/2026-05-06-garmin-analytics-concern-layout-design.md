# Garmin Analytics Concern Layout Design

## Goal

Normalize the Garmin analytics slice around concern-based boundaries before
continuing the broader domain ownership drain. The cleanup must make analytics
code easier to read and change without altering API behavior.

This is a structural refactor. It should not introduce new endpoints, new
response fields, new calculations, or frontend changes.

## Current Problem

`backend/app/domains/garmin_analytics/application/` now owns the right behavior,
but it is still doing too many kinds of work in one layer:

- use-case orchestration: repository reads, cache keys, selected-date behavior,
  and missing-date errors
- pure aggregate calculations: daily metrics, period summaries, biometric
  response shaping
- chart/read-model analysis: trends, weekly boxplots, distributions, dashboard
  sparklines, correlations
- insight rules: recovery labels, data quality, streaks, warnings, explanatory
  messages
- low-level analytical primitives: nullable averages, percentiles, moving
  averages, ISO-week grouping

The worst example is `compute_period_summary`. It currently combines raw value
extraction, per-metric policy, thresholds, null handling, rounding, and response
construction for heart rate, stress, respiration, HRV, SpO2, skin temperature,
sleep, and body battery. That shape is hard to test and unsafe to change.

## Chosen Approach

Use concern-based subpackages, not metric-based folders.

Metric-based folders would put `sleep`, `hrv`, and `heart_rate` in charge of
everything related to those metrics, but Garmin analytics has important
cross-metric surfaces: dashboard overview, period summaries, correlations,
readiness, and future experiment evidence. Concern folders make those surfaces
more natural.

The target package shape is:

```text
backend/app/domains/garmin_analytics/
  application/
    biometrics.py          # raw biometric read use cases
    analysis.py            # chart/read-model use cases and cache orchestration
    insights.py            # insight use cases and selected-date orchestration
    overview.py            # dashboard overview orchestration
    period_summary.py      # windowed period-summary orchestration
    ports.py               # application-facing repository protocols

  domain/
    primitives/
      numeric.py           # nullable avg, median, percentile
      trends.py            # moving averages, ISO-week grouping, baselines
      windows.py           # standard analytical window mechanics

    aggregates/
      biometric_responses.py
      daily.py
      period.py

    analysis/
      body_battery.py
      heart_rate.py
      hrv.py
      sleep.py
      stress.py

    insights/
      heart_rate.py
      hrv.py

  infra/
    biometric_repository.py
```

## Boundary Rules

`application/` files may:

- depend on `BiometricReadRepository`
- choose cache keys
- load data from repositories
- choose selected dates and raise lookup errors
- call pure domain functions
- assemble existing API response models

`domain/` files may:

- compute read models from already-loaded records
- import Pydantic response/data models from `app.models`
- import Garmin analytics domain primitives
- call other Garmin analytics domain functions when the dependency is explicit
  and acyclic

`domain/` files must not:

- import `app.infra.cache`
- import repository ports or concrete repositories
- call SQLite or database helpers
- import FastAPI
- read from disk or environment

`infra/` files may:

- perform SQLite reads and persistence mechanics
- depend on shared infrastructure primitives such as `app.infra.sqlite` and
  `app.infra.cache`
- hydrate Pydantic models from stored JSON

## Application Layer Shape

The application layer should become thin orchestration.

For example, sleep analysis should have this shape:

```python
def load_sleep_analysis(repo: BiometricReadRepository) -> SleepAnalysisResponse:
    return cache.cached(
        cache.SLEEP_ANALYSIS,
        lambda: compute_sleep_analysis(repo.load_daily_metrics()),
    )
```

The pure calculation should live in `domain/analysis/sleep.py`:

```python
def compute_sleep_analysis(metrics: list[DailyMetric]) -> SleepAnalysisResponse:
    return SleepAnalysisResponse(
        score_trend=compute_sleep_trend(metrics),
        weekly_boxplots=compute_weekly_sleep_boxplots(metrics),
    )
```

This pattern should apply to sleep, stress, body battery, heart rate analysis,
and HRV analysis.

## Period Summary Decomposition

`compute_period_summary(days)` remains the public domain assembler, but it should
only delegate:

```python
def compute_period_summary(days: list[DayData]) -> PeriodSummary:
    return PeriodSummary(
        heart_rate=compute_period_heart_rate(days),
        stress=compute_period_stress(days),
        respiration=compute_period_respiration(days),
        hrv=compute_period_hrv(days),
        spo2=compute_period_spo2(days),
        skin_temp=compute_period_skin_temp(days),
        sleep=compute_period_sleep(days),
        body_battery=compute_period_body_battery(days),
    )
```

Each helper should own one metric policy:

- `compute_period_heart_rate`: raw-reading weighted average, per-day resting HR
  last-value behavior, percentile band, zones
- `compute_period_stress`: raw stress average and percentile band
- `compute_period_respiration`: raw respiration average and percentile band
- `compute_period_hrv`: nightly/weekly null exclusion, balanced percentage, day
  count
- `compute_period_spo2`: raw average, lowest daily minimum, low-day threshold
  where `< 90` is low and `90` is not
- `compute_period_skin_temp`: deviation null exclusion, min/max rounding,
  nightly average, tracked-day count
- `compute_period_sleep`: score/deep-score null exclusion and tracked-day count
- `compute_period_body_battery`: per-day min/max extraction and tracked-day count

Helpers should be public within the module so tests can target them directly.
They are not route-facing contracts.

## Analysis Versus Insights

Analysis produces structured chart/read-model data:

- trends
- weekly boxplots
- histograms
- distribution buckets
- correlations
- sparklines
- pattern windows

Insights produce interpreted signals:

- recovery labels
- warnings
- data-quality states
- streak interpretations
- explanatory messages
- readiness or rest/moderate/ready labels

HRV currently mixes these concerns heavily. It should be split so distribution,
trajectory, baseline bands, and day-of-week buckets live in `domain/analysis/hrv.py`,
while recovery, status mix, streaks, quality, long baseline interpretation, and
messages live in `domain/insights/hrv.py`.

Heart-rate histogram and trend logic belongs to `domain/analysis/heart_rate.py`.
Heart-rate recovery and messages belong to `domain/insights/heart_rate.py`.

## Test-First Refactor Rule

Any analytics refactor that changes, moves, splits, or renames a production
analytics function must be preceded by tests that characterize the behavior being
preserved.

The required loop is:

1. Add or verify focused tests for the behavior before touching production code.
2. For newly extracted helpers, write helper-level tests before introducing the
   helper.
3. Run the focused test and confirm it fails for the missing helper or missing
   import when appropriate.
4. Move or extract the production code.
5. Run the focused test and confirm it passes.
6. Run architecture tests after boundary changes.
7. Run full backend validation before committing.

For pure moves where an existing test already exercises the behavior, the plan
must say which existing test is the characterization test. If no test exists for
that behavior, write one first.

## Period Summary Test Matrix

Before decomposing `compute_period_summary`, add or verify tests for every metric
helper.

Heart rate:

- empty days produce null average, null resting average, null percentile band,
  and empty zones
- period average uses all raw readings, not average of daily averages
- resting HR uses the last available per-day resting value and then averages
  across days
- zone boundaries keep `60`, `100`, and `130` in the upper zone

Stress:

- empty days produce null average and null percentile band
- raw values produce average, 25th percentile, and 75th percentile

Respiration:

- empty days produce null average and null percentile band
- raw values produce average, 25th percentile, and 75th percentile

HRV:

- empty summaries produce null averages, null balanced percentage, and zero days
- null nightly values are excluded from nightly average
- null weekly values are excluded from weekly average
- balanced percentage is rounded from statuses only

SpO2:

- empty readings produce null average, null lowest minimum, zero low days, and
  zero total days
- low-day threshold treats `89` as low and `90` as not low
- lowest minimum is computed from per-day minima

Skin temperature:

- empty overnight records produce null averages, null min/max, and zero tracked
  days
- null deviations are excluded from deviation average and tracked-day count
- min/max deviation are rounded to two decimals
- nightly values are averaged separately from deviations

Sleep:

- empty assessments produce null averages and zero tracked days
- null overall scores are excluded from score average and tracked-day count
- null deep scores are excluded from deep-score average

Body battery:

- empty readings produce null average min/max and zero tracked days
- each day contributes its own min and max before period-level averaging

## Architecture Tests

Add guardrails as part of the cleanup:

- Garmin analytics domain modules do not import `app.infra.cache`.
- Garmin analytics domain modules do not import repository ports or concrete
  repositories.
- Garmin analytics domain modules do not import FastAPI.
- Application modules may import domain modules, but domain modules do not import
  application modules.
- `domain/analysis/*` does not import `domain/insights/*`.
- `domain/insights/*` may import `domain/analysis/*` only if the imported
  function is a pure calculation and the dependency is explicit in the allowlist.

## Migration Order

1. Add architecture tests for the new domain/application boundary.
2. Move primitives: `numeric.py`, `trends.py`, and `windows.py`.
3. Move aggregate modules: `biometric_responses.py`, `daily_aggregates.py`, and
   `period_aggregates.py`.
4. Add period summary helper-level characterization tests.
5. Decompose `compute_period_summary`.
6. Split tab analysis calculators from application cache wrappers.
7. Split HRV and heart-rate insight rules from analysis calculations.
8. Update architecture allowlists after each boundary shrink.
9. Run backend lint, type check, and full tests.

## Non-Goals

- No API response schema changes.
- No frontend changes.
- No new metrics.
- No statistical behavior changes.
- No generic shared analytics package outside Garmin analytics unless a second
  domain starts using the same primitive.
- No repository or SQLite persistence rewrite beyond imports required by file
  moves.

## Validation

For the implementation phase, run:

```bash
cd backend && uv run ruff check app/ tests/
cd backend && uv run pyright app/ tests/
cd backend && uv run pytest tests/ -v
```

If any route or Pydantic schema file changes unexpectedly, regenerate API types:

```bash
bash scripts/generate-api-types.sh
cd frontend && npm run check
```

The expected outcome is no API type generation, because this cleanup should move
and split internal analytics functions only.

## Spec Self-Review

- Placeholder scan: no placeholders, open TODOs, or unspecified behavior.
- Internal consistency: the chosen concern-based layout matches the stated
  analysis-versus-insights boundary and period-summary decomposition.
- Scope check: this is a single cleanup phase focused only on Garmin analytics
  structure and tests.
- Ambiguity check: test-first requirements are explicit, including the case where
  an existing characterization test is acceptable.
