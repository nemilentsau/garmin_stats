# Run Activities

**Status:** shipped (running only). Strength/breathing activity files still download but are not parsed. Association between a prescribed routine/experiment card and its actual run is not built (see `../routine-pivot/pivot_roadmap.md` next steps).

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
| Vertical ratio | percent | |
| Temperature | °C | |
| Lat/lon | degrees | FIT stores semicircles; parser converts via `raw × 180 / 2³¹` |

## Known gaps

- **Stamina / performance-condition fields not exposed.** The FIT record stream carries undocumented numeric field IDs — `90` (performance-condition candidate), `137`/`138` (stamina / stamina-potential candidates) — observed but not decoded into any contract; tracked as unknowns in `activity-messages.json`, not surfaced anywhere in the app.
- **No GPS map.** `lat`/`lon` are captured in `RunningActivitySeries` but there is no map rendering on the detail page.
- **No time↔distance axis toggle.** Chart x-axis is elapsed time only.
- **No association.** A run has no link back to a prescribed routine/experiment card; this is the pending half of roadmap next-steps item 1 (`../routine-pivot/pivot_roadmap.md`).
- **Strength and breathing FIT files are not parsed.** Only `*_running_*.fit` is discovered; strength-specific schema remains a design doc (`../future/STRENGTH_ACTIVITY_SCHEMA.md`).
- **Zone boundaries display backend sentinels verbatim.** E.g. power zone 6's upper boundary can show as `4000` (an open-ended-top-zone sentinel, not a real reading) — the frontend renders whatever the backend sends without inferring intent.
