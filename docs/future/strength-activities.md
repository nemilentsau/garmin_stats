# Strength Activity Ingest

**Status:** concrete next implementation; not built.

Garmin Connect already downloads strength FIT files and JSON sidecars into the activity tree. The app does not discover, parse, store, serve, display, or associate those sessions. This spec defines the narrow first implementation needed by the active training system.

## Product boundary

The first useful grain is one tracked strength session. It should answer:

- when the session occurred;
- how long it lasted;
- whether heart-rate evidence is present and where time was spent by HR zone;
- Garmin training effect and training load when present;
- which prescribed strength occurrence it satisfied.

Garmin's inferred `set_mesgs`, repetition counts, exercise categories, and weights are not training-log truth. In the locally observed files, those messages usually collapse the workout into one broad active set and provide probabilistic categories rather than the athlete's actual exercise/set structure. The v3 training capture log remains authoritative for exercises, sets, repetitions, load, RIR, tonnage, and e1RM inputs.

Do not create a generic cross-sport activity ontology as a prerequisite. Running already has a stable sport-specific session/lap/series model; strength should follow the same ownership boundaries with a smaller contract.

## Session contract

Add a canonical `StrengthActivitySession` under `garmin_health` with FIT-native units and local timestamps established at ingest:

```text
id
activity_id
source_file
session_date
start_time_local
utc_offset_hours
elapsed_time_s
timer_time_s
moving_time_s
sport
sub_sport
activity_name
total_calories
avg_heart_rate_bpm
max_heart_rate_bpm
hr_source
aerobic_training_effect
anaerobic_training_effect
training_load
hr_zone_seconds
hr_zone_boundaries_bpm
record_count
has_heart_rate
has_records
has_garmin_set_diagnostics
```

Use FIT session/time-in-zone messages as the primary source and the Connect sidecar for identifiers, local start time, display name, and a fallback only when the corresponding FIT summary is absent. Preserve source fields needed to audit a discrepancy, but do not expose an unbounded raw dictionary in the product API.

## Optional record evidence

Timestamped heart-rate records are consistently useful for session response and coverage checks. Store them only if the first product read requires the trace; they must not block session ingest.

If added, use one JSON-blob series row per session, matching the running storage pattern rather than one SQLite row per sample:

```text
elapsed_s[]
heart_rate_bpm[]
```

Unknown numeric FIT record fields remain parser diagnostics until a documented product question and real-file validation justify a stable name.

## Ownership and flow

```text
strength FIT + sidecar
  -> garmin_health parser/contracts
  -> garmin_sync fingerprint-gated ingest and SQLite tables
  -> garmin_analytics strength read model/API
  -> training-owned prescription association through an injected local port
  -> Today execution evidence
```

- `garmin_health` owns field decoding, units, and UTC-to-local timestamp shifting.
- `garmin_sync` owns discovery, idempotent persistence, schema, and cache invalidation.
- `garmin_analytics` owns the session read model and any display-ready projection.
- `training` owns association with `strength.v3` occurrences and effective execution policy; it must not import Garmin persistence/contracts directly.
- The frontend displays backend values and performs no aggregation.

Use separate storage (`strength_activity_sessions`, plus an optional `strength_activity_series`) rather than forcing strength rows into the running tables.

## Association rules to decide in implementation

Strength association must be deterministic and preserve manual control. Before coding, pin down these cases with real dates from the threshold-development authored program:

- zero, one, or multiple `strength.v3` cards on the same date;
- zero, one, or multiple tracked strength sessions on the same date;
- a manually linked session that later disappears after re-ingest;
- an explicit detach that suppresses automatic matching.

Do not infer an exercise match from Garmin's category guesses. When there is exactly one card and one session, date-level matching is sufficient. Ambiguous days require an explicit user choice unless a stronger authored key is added to the schema.

## Backend features unlocked

The session mart may provide backend-owned daily inputs such as:

- strength session count;
- total timer time;
- Garmin training-load total where available;
- max aerobic/anaerobic training effect;
- total HR-zone seconds;
- previous-day strength-session flag.

These are context/load inputs. They do not replace captured tonnage or e1RM estimators.

## Acceptance criteria

- Representative real strength files decode with documented field presence and null handling.
- All parsed timestamps are local-time aligned at ingest.
- Missing activity tree, already-in-sync tree, and changed tree are tested, including a second unchanged run that performs no decoding or writes.
- Per-file failures are isolated and reported without aborting the batch.
- Re-ingest can rebuild already-downloaded strength rows after parser changes.
- Session API values are backend-owned and the frontend performs no statistics.
- Association/effective-execution precedence is covered for manual link, detach, unambiguous auto-match, ambiguity, and stale manual link.
- A real-tree smoke check proves counts, idempotence, and at least one FIT/sidecar/API field match before shipping.
