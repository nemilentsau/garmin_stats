# Route Inventory

**Status:** generated — do NOT hand-edit. Regenerate after route changes:
`cd backend && uv run python ../scripts/generate_routes_doc.py`

Backend from the FastAPI OpenAPI schema (81 operations); frontend from `frontend/src/routes`.

## Backend API


### `(root)`

| Method | Path | Summary |
|---|---|---|
| GET | `/` | Root |

### `activities`

| Method | Path | Summary |
|---|---|---|
| GET | `/api/activities/runs` | List Runs Route |
| GET | `/api/activities/runs/{run_id}` | Get Run Route |
| GET | `/api/activities/runs/{run_id}/series` | Get Run Series Route |

### `assistant`

| Method | Path | Summary |
|---|---|---|
| POST | `/api/assistant/artifact-bundles/import` | Post Import Bundle |
| POST | `/api/assistant/artifact-bundles/preview` | Post Preview Bundle |
| GET | `/api/assistant/artifacts` | Get Artifacts |
| POST | `/api/assistant/artifacts` | Post Artifact |
| GET | `/api/assistant/artifacts/{artifact_id}` | Get Artifact Detail |
| POST | `/api/assistant/artifacts/{artifact_id}/activate` | Post Activate Artifact |
| GET | `/api/assistant/threads` | Get Threads |
| POST | `/api/assistant/threads` | Post Thread |
| GET | `/api/assistant/threads/{thread_id}` | Get Thread Detail |
| GET | `/api/assistant/threads/{thread_id}/messages` | Get Thread Messages |
| POST | `/api/assistant/threads/{thread_id}/messages` | Post Thread Message |

### `body-battery`

| Method | Path | Summary |
|---|---|---|
| GET | `/api/body-battery/analysis` | Get Body Battery Analysis |
| GET | `/api/body-battery/daily` | Get Body Battery Daily |
| GET | `/api/body-battery/raw` | Get Body Battery Raw |

### `cards`

| Method | Path | Summary |
|---|---|---|
| GET | `/api/cards` | Get Cards |

### `checkins`

| Method | Path | Summary |
|---|---|---|
| GET | `/api/checkins` | Get Checkins |
| POST | `/api/checkins` | Post Checkin |

### `daily-aggregates`

| Method | Path | Summary |
|---|---|---|
| GET | `/api/daily-aggregates` | Get Daily Agg |

### `dashboard`

| Method | Path | Summary |
|---|---|---|
| GET | `/api/dashboard` | Get Dashboard Overview |

### `events`

| Method | Path | Summary |
|---|---|---|
| GET | `/api/events` | Sse Events |

### `experiments`

| Method | Path | Summary |
|---|---|---|
| GET | `/api/experiments` | Get Experiments |
| POST | `/api/experiments` | Post Experiment |
| POST | `/api/experiments/import` | Post Import |
| POST | `/api/experiments/preview` | Post Preview |
| POST | `/api/experiments/refresh-analyses` | Post Refresh |
| GET | `/api/experiments/{experiment_id}` | Get Experiment Detail |
| PUT | `/api/experiments/{experiment_id}` | Put Experiment |
| GET | `/api/experiments/{experiment_id}/analysis` | Get Analysis |
| GET | `/api/experiments/{experiment_id}/exposures` | Get Exposures |
| POST | `/api/experiments/{experiment_id}/exposures` | Post Exposure |

### `heart-rate`

| Method | Path | Summary |
|---|---|---|
| GET | `/api/heart-rate/analysis` | Get Heart Rate Analysis |
| GET | `/api/heart-rate/daily` | Get Heart Rate Daily |
| GET | `/api/heart-rate/distribution` | Get Hr Distribution |
| GET | `/api/heart-rate/insights` | Get Heart Rate Insights |
| GET | `/api/heart-rate/raw` | Get Heart Rate Raw |

### `hrv`

| Method | Path | Summary |
|---|---|---|
| GET | `/api/hrv/analysis` | Get Hrv Analysis |
| GET | `/api/hrv/daily` | Get Hrv Daily |
| GET | `/api/hrv/insights` | Get Hrv Insights |
| GET | `/api/hrv/raw` | Get Hrv Raw |

### `ingest`

| Method | Path | Summary |
|---|---|---|
| POST | `/api/ingest` | Trigger Ingest |
| GET | `/api/ingest/status` | Get Ingest Status |
| POST | `/api/ingest/sync` | Trigger Sync |

### `notes`

| Method | Path | Summary |
|---|---|---|
| GET | `/api/notes` | Get Notes |
| POST | `/api/notes` | Post Note |

### `profile`

| Method | Path | Summary |
|---|---|---|
| GET | `/api/profile` | Get Profile |
| PUT | `/api/profile` | Put Profile |

### `programs`

| Method | Path | Summary |
|---|---|---|
| GET | `/api/programs` | Get Programs |
| POST | `/api/programs/import` | Post Import Program |
| GET | `/api/programs/{program_id}` | Get Program Detail |
| PUT | `/api/programs/{program_id}/activate` | Put Activate Program |
| PUT | `/api/programs/{program_id}/retire` | Put Retire Program |
| GET | `/api/programs/{program_id}/versions` | Get Versions |

### `pulse-ox`

| Method | Path | Summary |
|---|---|---|
| GET | `/api/pulse-ox/daily` | Get Pulse Ox Daily |
| GET | `/api/pulse-ox/raw` | Get Pulse Ox Raw |

### `respiration`

| Method | Path | Summary |
|---|---|---|
| GET | `/api/respiration/daily` | Get Respiration Daily |
| GET | `/api/respiration/raw` | Get Respiration Raw |

### `routines`

| Method | Path | Summary |
|---|---|---|
| GET | `/api/routines` | Get Routines |
| GET | `/api/routines/schedule-window` | Get Routine Schedule Window |
| GET | `/api/routines/{routine_id}` | Get Routine Detail |
| GET | `/api/routines/{routine_id}/assignments` | Get Assignments |

### `skin-temp`

| Method | Path | Summary |
|---|---|---|
| GET | `/api/skin-temp/daily` | Get Skin Temp Daily |
| GET | `/api/skin-temp/raw` | Get Skin Temp Raw |

### `sleep`

| Method | Path | Summary |
|---|---|---|
| GET | `/api/sleep/analysis` | Get Sleep Analysis |
| GET | `/api/sleep/daily` | Get Sleep Daily |
| GET | `/api/sleep/raw` | Get Sleep Raw |

### `stress`

| Method | Path | Summary |
|---|---|---|
| GET | `/api/stress/analysis` | Get Stress Analysis |
| GET | `/api/stress/daily` | Get Stress Daily |
| GET | `/api/stress/raw` | Get Stress Raw |

### `target-metrics`

| Method | Path | Summary |
|---|---|---|
| GET | `/api/target-metrics` | List Target Metrics Route |

### `today`

| Method | Path | Summary |
|---|---|---|
| GET | `/api/today` | Get Today View |
| GET | `/api/today/card-logs` | Get Card Logs Range |
| PUT | `/api/today/{date}/cards/{occurrence_key}` | Put Today Card Log |

### `training`

| Method | Path | Summary |
|---|---|---|
| GET | `/api/training/block` | Get Block |
| POST | `/api/training/import` | Post Import |
| GET | `/api/training/schedule-window` | Get Schedule Window |
| GET | `/api/training/today` | Get Today |
| PUT | `/api/training/today/{date}/cards/{occurrence_key}` | Put Today Card Log |

## Frontend routes (SvelteKit)

| Route | Kind |
|---|---|
| `/` | page |
| `/assistant` | page |
| `/body-battery` | page |
| `/experiments` | page |
| `/heart-rate` | page |
| `/hrv` | page |
| `/programs` | page |
| `/pulse-ox` | page |
| `/respiration` | page |
| `/routines/schedule` | page |
| `/skin-temp` | page |
| `/sleep` | page |
| `/stress` | page |
| `/today` | page |
| `/training/import` | page |

