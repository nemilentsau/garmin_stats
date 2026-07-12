# Run Activities

**Status:** shipped (running only) — parse, strap channels, stamina/performance-condition, GPS route map, and run↔prescription association are all live. Strength/breathing activity files still download but are not parsed (see `../routine-pivot/pivot_roadmap.md` next steps).

How tracked runs get from `data/garmin_activities/` FIT files into the `/runs` UI. For the two-tree data topology, download/sync mechanics, and config paths, see `data-and-ingest.md` — this page only covers the running-specific parse → store → serve → display path.

## Pipeline

`*_running_*.fit (+ .json sidecar) → garmin_health FIT parser → garmin_sync ingest → running_activity_* tables → garmin_analytics read model → /api/activities/runs* → /runs, /runs/[id]`

### Parse (`garmin_health`)

- `backend/app/domains/garmin_health/infra/fit_parser/activities.py` — `discover_running_activity_files(activities_dir)` globs `*/*_running_*.fit` (running only; strength/breathing files are never discovered here). `parse_running_activity(fit_path, activities_dir)` decodes one FIT, loads its `.json` Connect sidecar if present, and returns a `RunningActivityData` (session + laps + series). `parse_running_activities(activities_dir)` parses every discovered file, logging and skipping any file that raises rather than aborting the batch.
- `backend/app/domains/garmin_health/infra/fit_parser/activity_extractors.py` — pure field extraction from decoded FIT message dicts (no I/O): session/lap summaries, the per-second record series, HR-source detection, and the unit conversions below.
- Contracts (`backend/app/domains/garmin_health/contracts/activities.py`): `RunningActivitySession`, `RunningActivityLap`, `RunningTimeInZones`, `RunWalkSpan`, `RunningActivitySeries`, `RunningActivityData`.
- Schema/field reference for the FIT message types involved (including unmapped record fields): `.claude/skills/garmin-data/references/activity-messages.json`, owned by the `garmin-data` skill.

### Store (`garmin_sync`)

- `backend/app/domains/garmin_sync/infra/activity_ingest.py::ingest_running_activities(activities_dir, force=False)` — the single entry point. Fingerprint-gated and idempotent:
  1. Computes a SHA-256 fingerprint over every `*.fit` file's path/size/mtime under `activities_dir` (`filesystem.compute_data_fingerprint`) — this covers **all** activity sports (running, strength, breathing, …), not just running, since it walks the whole tree. Stored/compared against `ingest_meta` key **`activities_fingerprint`**.
  2. If the fingerprint is unchanged and `force=False`, returns immediately (`skipped=True`) — no file is decoded.
  3. Otherwise, discovers running files, diffs against `source_file` already present in `running_activity_sessions` (downloads are write-once, so an existing `source_file` is never re-parsed), and parses only the new ones. A per-file parse failure is logged and counted in `files_failed`; it does not abort the rest of the batch.
  4. Writes/replaces rows in `running_activity_sessions` (one per run), `running_activity_laps` (one per lap, delete-then-insert per session), and `running_activity_series` (one JSON-blob row per session), then rewrites the fingerprint. The read cache (`app.infra.cache`) is invalidated only if at least one session was actually ingested.
- Table shapes (`backend/app/domains/garmin_sync/schema.py`): `running_activity_sessions(id PK, activity_id, session_date, start_time_local, sub_sport, source_file UNIQUE, data JSON, created_at, updated_at)`, `running_activity_laps(session_id, lap_index, data JSON, PK(session_id, lap_index))`, `running_activity_series(session_id PK, data JSON)`. `data` columns hold the full contract as JSON; the handful of plain columns exist for indexed lookup (date/start, `activity_id`, `source_file`).
- Called from two places, both after their wellness-side work, per `garmin_sync/CHARTER.md`:
  - `infra/runtime.py::run_startup_ingest_if_needed` — unconditionally on process startup (cheap no-op when the tree is unchanged, since the engine's own fingerprint gate handles that).
  - `workflows.py::sync_garmin` — immediately after the per-sync activity-download sweep, so a run downloaded in a sync call is parsed and queryable within that same call.
- **Adding a parser field requires an activity re-ingest.** Because `source_file` dedup skips any file already in `running_activity_sessions`, a normal sync/startup ingest never re-parses existing downloads — new/changed parser fields only reach already-stored rows via a full rebuild: `cd backend && uv run python ../scripts/reingest_activities.py` (see `data-and-ingest.md` Commands).

### Serve (`garmin_analytics`)

- `backend/app/domains/garmin_analytics/application/runs.py` + `contracts/runs.py` + `SqliteRunsRepository` — read-only over the tables above; no derivation beyond backend-owned pace (`pace_min_per_km` — never recomputed on the frontend).
- Routes (`backend/app/domains/garmin_analytics/routes.py`, prefix `/api/activities/runs`, see `routes.md`):
  - `GET /api/activities/runs?from=&to=` — `RunsListResponse`, newest first, optional inclusive date-range filter.
  - `GET /api/activities/runs/{run_id}` — `RunDetailResponse` (full session fields + laps).
  - `GET /api/activities/runs/{run_id}/series` — `RunSeriesResponse` (per-second column arrays + backend-derived pace array).

### Display (frontend)

- `frontend/src/routes/runs/+page.svelte` — list table (Date, Name, Distance, Time, Pace, Avg HR with a CHEST/WRIST badge, Load, TE), date-range filter, whole-row navigation to the detail page. Reached via Training → Runs in the nav.
- `frontend/src/routes/runs/[id]/+page.svelte` — stat-card header, a run/walk/stand span band, a 10-channel chart stack (elevation, pace, heart rate, cadence, stride length, power, vertical oscillation, vertical ratio, ground contact time, temperature — each rendered only when its series has data), session-stat definition lists (no card chrome), a laps table, and HR/power time-in-zone bars.
- Shared formatting: `frontend/src/lib/format-run.ts`. Frontend computes no statistics — every displayed number (including pace) comes from the API as-is.

## `hr_source` semantics

Set by `activity_extractors._detect_hr_source`, values `"strap" | "wrist" | None`:

- **`"strap"`** — a non-local `device_info` entry whose `ble_device_type` or `antplus_device_type` is `heart_rate` (an external chest strap paired over BLE/ANT+). `hr_strap_serial` and `hr_strap_battery` are captured from that same device-info record.
- **`"wrist"`** — heart rate data is present in the session but no external strap device was seen; attributed to the watch's optical sensor.
- **`None`** — no heart-rate data at all (`has_heart_rate=False`). Most runs before roughly March 2026 fall here; HR coverage is date-patterned, not uniformly present across the whole history.

## Strap channels

Three running-dynamics fields are **strap-only** — present only when a chest-strap HR sensor (not the watch's optical/wrist sensor) was worn, gated by `has_strap_dynamics` (distinct from `has_running_dynamics`, which covers plain GCT/vertical-oscillation/vertical-ratio and is available from watch-only running dynamics too):

- **GCT balance** — `avg_ground_contact_balance_pct` (session/lap), `stance_time_balance_pct` (series). Stored value is the left foot's share of total ground contact time; the display layer (`garmin_analytics/application/runs.py::_ground_contact_balance_label`) renders it as `"49.8% L / 50.2% R"` (right share = 100 − left, both rounded to 1dp independently, matching Connect) — computed backend-side since it's arithmetic on one stored field, per the frontend display-only rule.
- **Respiration rate** — `avg_respiration_rate_brpm` / `max_respiration_rate_brpm` / `min_respiration_rate_brpm` (session/lap), `respiration_rate_brpm` (series), unit breaths/min (brpm). Sourced from the FIT `enhanced_*_respiration_rate` fields.
- **Stance time %** — `avg_stance_time_pct` (session/lap), `stance_time_pct` (series). FIT's `stance_time_percent` field, already a percent — pass-through, no conversion.

All three are None on wrist-only runs, same as `hr_source="wrist"`/`None` above. Parser: `activity_extractors.py` (session/lap extraction ~L167-172/246-250, series ~L282-285). Displayed on `/runs/[id]`: the GCT Balance and Respiration Rate channel charts, a "GCT Balance"/"Stance Time" stat pair, and per-lap in the laps table (`avg_ground_contact_balance_label`, `avg_respiration_rate_brpm`).

## Stamina / performance-condition

Firstbeat's Stamina, Stamina Potential, and Performance Condition — the same metrics Connect's Stats-panel "Stamina" group and Performance Condition chart show. Sourced from **undocumented numeric FIT record field IDs**, not named fields: `137` = stamina potential (the ceiling; monotonically ≥ 138 throughout a run), `138` = stamina (dips first, recovers toward potential), `90` = performance condition. The SDK exposes these as positional int dict keys (`msg.get(137)`/`msg.get(138)`/`msg.get(90)`), not named — see `activity_extractors.py` ~L287-294; tracked as unknowns in `.claude/skills/garmin-data/references/activity-messages.json`.

- **Series** (`RunningActivitySeries`): `stamina_pct`, `stamina_potential_pct`, `performance_condition` — per-record, positional nulls (field 90 in particular has a leading gap while Garmin's model baselines).
- **Session scalars** (`RunningActivitySession`, derived at parse time from the series — `activities.py::_stamina_scalars`): `stamina_beginning_potential_pct`/`stamina_ending_potential_pct` (first/last non-null `stamina_potential_pct` sample), `stamina_min_pct` (minimum non-null `stamina_pct` sample — the dip, matching Connect's Stats-panel semantics). None-safe: old watch firmware without stamina channels yields `(None, None, None)`, not a `KeyError`/`min()`-on-empty.
- **Provenance/validation:** field-ID mapping validated 2026-07-11 against 3 real Garmin Connect activities — 9/9 anchor values (begin/end/min stamina) matched exactly (commit `49898ab`). Frontend chart values additionally cross-checked visually against Connect's own Stamina and Performance Condition charts and Stats panel — exact match.
- **Display:** dimensionless ints/percents, no unit conversion, pass-through on `RunDisplayStats`/`RunSeriesResponse`. No top-level array duplicates on the series response — the arrays live only inside the embedded `series` object (see commit `59abb86`: duplicating embedded series data at the top level was tried and reverted). `/runs/[id]` renders a two-dataset Stamina chart (stamina + potential ceiling, fixed 0-100 y-axis), a Performance Condition chart with a zero-line annotation, and a Stamina stats group.

## Route map

`/runs/[id]` renders a GPS route map (`frontend/src/lib/components/RunRouteMap.svelte`) built on Leaflet + OpenStreetMap tiles, dark-filtered to match the app's muted surfaces:

- **Pace-quantile coloring.** The route line is drawn as per-segment polylines colored by binning each segment's pace into 5 quantile bins (quintiles) of *that run's own* pace distribution — equal-population edges, not equal-width min/max bins, because urban runs carry extreme stop/light outliers (observed range 6.6-27.1 min/mi on one route) that would otherwise pack ~99% of segments into a single bin. Segments with no pace on either endpoint draw neutral gray rather than being dropped, so GPS-but-no-pace stretches (paused/stopped) still read as part of the route.
- **Gap-safe segmentation.** GPS gaps (consecutive null lat/lon indices) are never bridged — polylines terminate at the gap and resume after it, rather than drawing a straight line across a lost-signal stretch.
- **Client-side quantile binning is presentation-only**, not a statistical computation: see the presentation-calibration exception in `code-conventions.md`.
- Leaflet touches `window`/`document` at import time, so it's loaded via a dynamic `import()` inside `onMount` (never at module scope) to stay SSR-safe.
- Inputs are `lat`/`lon`/`pace` arrays already on `RunSeriesResponse` (`series.lat`/`series.lon`, `pace_min_per_mi`) — no new API surface.

## Association

A tracked run can be linked to the `running.v3` prescription card it satisfies, surfaced on the Today board only. This is a `training`-domain read policy over `garmin_analytics` run data, not a `garmin_analytics`/`run-activities` feature — full ownership, contracts, and route detail live in `backend/app/domains/training/CHARTER.md`; this section covers only what a run-activities reader needs to know about how tracked runs feed it.

**Port boundary.** `training` must never import `garmin_analytics`/`garmin_health` (see its charter's "Must not import"). It defines a `RunActivityReadPort` protocol and a `TrainingRunActivitySummary` contract (`backend/app/domains/training/dependencies.py`/`contracts.py`); the concrete adapter, `GarminRunActivityPort`, lives outside the slice in `backend/app/bootstrap/run_activity_port.py` and wraps `garmin_analytics`'s `RunsReadRepository`. It converts to the same imperial display units (`distance_mi`, `pace_min_per_mi`) using the identical constants/rounding as `garmin_analytics/application/runs.py`, so a run's association fields always match what `/api/activities/runs` shows for the same run. Wired into the app container in `backend/app/bootstrap/container.py`.

**`running.v3` discriminator.** Association only ever evaluates for cards from the `running.v3` bundle (`training/application/read_models.py::_is_run_card`, mirroring `validation.py`'s own `entry.bundle_id == "running.v3"` check) — every other card, including `support.v3`'s `sup.daily` (which also prescribes `SegmentPrescription`), gets `run_candidates=[]`/`associated_activity=None` unconditionally.

**Matching policy** (`match_run_to_card`, `training/application/read_models.py`), verbatim precedence:

1. A manual `linked_run_id` always wins, even over a `run_link_detached` flag stored on the same log — detaching only takes effect once the manual link itself is cleared. A `linked_run_id` absent from that day's tracked runs (e.g. the run was re-ingested and changed id) silently resolves to no association rather than raising; the caller still offers the day's runs as re-pick candidates regardless.
2. `run_link_detached` with no manual link explicitly suppresses auto-matching for that occurrence.
3. Otherwise, auto-match: only when exactly one `running.v3` card is scheduled that day (two or more have no unambiguous per-card signal — cards carry no time-of-day, so only a manual link can resolve them) and at least one tracked run exists for the date. The pick is the run whose `distance_mi` is closest to the card's prescribed distance (sum of its segments' `distance_mi`, or the longest run when the card prescribes no distance at all). A run with no `distance_mi` sorts as 0 mi in both comparisons.

The resolved summary's `link_source` is `"manual"` for branch 1 or `"auto"` for branch 3; branch 1's stale-link case and branch 2 both return no association.

**Today-only.** `GET /api/training/today` is the only read model that threads a `run_activity_port` — `run_candidates`/`associated_activity` are always empty/`None` on `GET /api/training/schedule-window` (planning view). `PUT /api/training/today/{date}/cards/{occurrence_key}` also receives the port, but only to validate a manually-set `linked_run_id` against that date's tracked runs (rejects with 400 if the id isn't one of them) — it does not itself resolve `match_run_to_card`.

**PATCH fields** on `TrainingLogUpdateRequest`: `linked_run_id: str | None` and `run_link_detached: bool | None`. Both follow PATCH (only-if-present) semantics — an explicit `null` on `linked_run_id` clears the stored link; omitting the field leaves the existing value untouched. Frontend: the Today card's "Executed" block shows `associated_activity` when resolved, and a `run_candidates` picker (radio list, "Not this run?" to reopen) when a `running.v3` card has candidates but no resolved match — `frontend/src/lib/training/TrainingCardBody.svelte`.

## Units policy

All fields are canonical backend units; the frontend receives display-ready values and derives nothing (project-wide rule). Per `contracts/activities.py`:

| Concept | Unit | Notes |
|---|---|---|
| Distance, elevation | meters | |
| Duration | seconds | |
| Speed | m/s | `avg_speed_mps`, `max_speed_mps`, `grade_adjusted_avg_speed_mps` |
| Pace | min/km | backend-derived from timer time ÷ distance; never recomputed on the frontend |
| Heart rate | bpm | |
| Power | watts | |
| Cadence | steps/min | FIT running-cadence fields are half-cadence; parser applies `(value + fractional) × 2` |
| Ground contact time | ms | |
| Step length, vertical oscillation | mm | |
| Vertical ratio, GCT balance, stance time | percent | GCT balance/stance-time are strap-only (see above) |
| Respiration rate | brpm (breaths/min) | strap-only |
| Stamina, stamina potential, performance condition | dimensionless int/percent | pass-through, no conversion |
| Temperature | °C | |
| Lat/lon | degrees | FIT stores semicircles; parser converts via `raw × 180 / 2³¹` |

This table is **storage/canonical units** (`RunningActivitySession`/`Lap`/`Series` — what the parser and tables hold). The read layer (`garmin_analytics/application/runs.py`) additionally projects a subset into US imperial fields for display — miles, min/mi, feet, °F — per the project-wide imperial display rule (`CLAUDE.md`; distance/pace/elevation/temperature only, the Garmin-style exceptions above stay metric/native). `RunDisplayStats`/`RunSeriesResponse`'s `*_mi`/`*_ft`/`*_f`/`pace_min_per_mi` fields are that projection; the embedded `session`/`laps`/`series` stay metric regardless.

## Known gaps

- **No time↔distance axis toggle.** Chart x-axis is elapsed time only.
- **Strength and breathing FIT files are not parsed.** Only `*_running_*.fit` is discovered; strength-specific schema remains a design doc (`../future/STRENGTH_ACTIVITY_SCHEMA.md`).
- **Zone boundaries display backend sentinels verbatim.** E.g. power zone 6's upper boundary can show as `4000` (an open-ended-top-zone sentinel, not a real reading) — the frontend renders whatever the backend sends without inferring intent.
