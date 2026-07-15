# Route Inventory

**Status:** generated — do NOT hand-edit. Regenerate after route changes:
`cd backend && uv run python ../scripts/generate_routes_doc.py`

Backend from the FastAPI OpenAPI schema (69 operations); frontend from `frontend/src/routes`.

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

### `body-battery`

| Method | Path | Summary |
|---|---|---|
| GET | `/api/body-battery/analysis` | Get Body Battery Analysis |
| GET | `/api/body-battery/daily` | Get Body Battery Daily |
| GET | `/api/body-battery/raw` | Get Body Battery Raw |

### `checkins`

| Method | Path | Summary |
|---|---|---|
| GET | `/api/checkins` | Get Checkins |
| POST | `/api/checkins` | Post Checkin |

### `coach`

| Method | Path | Summary |
|---|---|---|
| GET | `/api/coach/brief` | Get Brief |
| GET | `/api/coach/reviews` | Get Reviews |
| POST | `/api/coach/reviews/run` | Post Run Review |
| POST | `/api/coach/reviews/{review_id}/regenerate` | Post Review Regenerate |
| POST | `/api/coach/reviews/{review_id}/retry` | Post Review Retry |
| GET | `/api/coach/run-reviews/{run_id}` | Get Run Review |
| GET | `/api/coach/status` | Get Status |
| GET | `/api/coach/threads` | Get Threads |
| POST | `/api/coach/threads` | Post Thread |
| POST | `/api/coach/threads/{thread_id}/close` | Post Close |
| GET | `/api/coach/threads/{thread_id}/messages` | Get Messages |
| POST | `/api/coach/threads/{thread_id}/messages` | Post Message |
| POST | `/api/coach/threads/{thread_id}/retry-close` | Post Retry Close |

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
| `/body-battery` | page |
| `/coach` | page |
| `/experiments` | page |
| `/heart-rate` | page |
| `/hrv` | page |
| `/pulse-ox` | page |
| `/respiration` | page |
| `/runs` | page |
| `/runs/[id]` | page |
| `/skin-temp` | page |
| `/sleep` | page |
| `/stress` | page |
| `/today` | page |
| `/training/import` | page |
| `/training/schedule` | page |

