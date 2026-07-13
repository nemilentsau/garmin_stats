# Architecture

Current-state code map. Not a roadmap, not a historical diary. This file is the high-level map; per-domain boundary contracts live colocated at `backend/app/domains/<domain>/CHARTER.md`, and volatile facts live in the reference docs linked below.

## Product Shape

The shipped app has four active product centers:

1. Recovery dashboard and metric drill-downs
2. Coach: queued run reviews, evidence-grounded chat, and bounded semantic memory
3. Training block runtime (v3): artifact import, lint-gated activation, and the Today/schedule training feed
4. Routine runtime shared by Creation, Schedule, and Today — the import path for non-training bundles (meditation, breathwork)

Experiments remain backend-supported and domain-owned, but the frontend experiment screens are intentionally parked. Programs remain a secondary backend area. Standing rule from the pivot (`routine-pivot/pivot_roadmap.md`): routine/experiment/training content enters the app **only** by importing an authored bundle — no generators, translators, seeders, or derived artifacts.

## Project Layout

- `backend/app/` — FastAPI application code.
- `backend/tests/` — backend tests by ownership: architecture guards, bootstrap, infra, core, and domain slices.
- `frontend/src/` — SvelteKit application.
- `storage/` — local SQLite database, created at runtime.
- `data/garmin_health_stats/` — Garmin wellness day archives + extracted FIT (ingested → `daily_metrics`).
- `data/garmin_activities/` — per-activity FIT + JSON pulled from Garmin Connect every sync (running parsed into session/lap/series tables and associated with prescribed run cards; strength/breathing parse pending).

Full data topology, ingest/sync flow, and config paths: **`reference/data-and-ingest.md`**.

## Backend

Boundary tests guard module intent, not a mandatory folder template. Larger slices may use `api/`, `application/`, and `infra/` packages when those layers contain multiple stable concepts; small capability slices stay flatter.

### Main flow

Three paths:

- **Ingest (wellness):** FIT files → Garmin health FIT parser → daily metric composer → SQLite.
- **Activity:** tracked-session FIT/JSON downloaded from Garmin Connect into `data/garmin_activities/` every sync; running activities parsed into `running_activity_{sessions,laps,series}` on sync/startup and associated with prescribed run cards (see `reference/run-activities.md`); strength/breathing parse pending (`reference/data-and-ingest.md`, `future/ACTIVITY_ANALYTICS_DESIGN.md`).
- **Read:** SQLite → repository adapters → domain/core application slices → JSON API → frontend.

Dependency direction (the layering enforced by architecture tests):

- `garmin_sync` ingest adapters → `garmin_health`, `app.utils`
- `garmin_analytics` → `garmin_health`, `app.utils`
- `experiments` → `garmin_health` contracts and its injected read sources
- `coach` → existing `garmin_analytics`, `training`, `journal`, and `garmin_health` read contracts through one gateway; it does not own estimator computation
- `garmin_health` → `app.contracts.base`, `app.utils`
- `app.utils` → stdlib and numpy only

### Core modules

- `backend/app/contracts/base.py` — shared Pydantic response bases. User-facing contracts live with their owning slices.
- `backend/app/bootstrap/` — app factory, router registration, lifespan, storage schema composition, composition root. Cross-domain reactions (e.g. "refresh experiment analyses after Garmin ingest") live here, not in the individual slices.
- `backend/app/core/` — shared cross-cutting modules extracted out of the flat app root.
- `backend/app/parser.py` — compatibility facade for the FIT parser; implementation under `domains/garmin_health/infra/fit_parser/`.
- `backend/app/utils/` — shared, domain-agnostic helpers (promotion rule in `reference/code-conventions.md`).
- `backend/app/main.py` — compatibility entrypoint exposing the assembled FastAPI app.

### Infrastructure

- `backend/app/infra/sqlite.py` — shared SQLite path + connection primitive (no table/persistence policy).
- `backend/app/infra/jsonstore.py` — generic JSON-record persistence helper for storage adapters that own their tables.
- `backend/app/bootstrap/schema.py` — storage composition entrypoint (creates the DB, enables WAL, calls each slice's `schema.py`).
- `backend/app/infra/cache.py` — in-memory cache with generation-based invalidation.
- `backend/app/realtime/events.py` + `routes.py` — SSE event bus/heartbeat and the `/api/events` transport.

### Domains (index)

Each domain's full boundary contract — **Owns / Does not own / May import / Must not import / Public entrypoints** — lives in its own `CHARTER.md`, updated in the same PR that changes the domain. This table is the map; the charter is the authority.

| Domain / slice | Purpose | Routes | Charter |
|---|---|---|---|
| `coach` | Durable run reviews/chat, structured measurement assessments, hierarchical context, semantic journal/brief, isolated Codex runtime | `/api/coach/*` | [charter](../backend/app/domains/coach/CHARTER.md) |
| `routines` | v2 routine catalog, schedule projection, Today execution (meditation/breath import path) | `/api/routines`, `/api/today` | [charter](../backend/app/domains/routines/CHARTER.md) |
| `training` | v3 training import, lint-gated activation, Today/schedule execution and measurement projection, authored backup runtime, capture logs | `/api/training/*` | [charter](../backend/app/domains/training/CHARTER.md) |
| `garmin_sync` | Garmin archive + tracked-activity acquisition, ingest/sync (running activities parsed; strength/breathing download-only) | `/api/ingest`, `/api/ingest/status`, `/api/ingest/sync` | [charter](../backend/app/domains/garmin_sync/CHARTER.md) |
| `garmin_health` | Canonical FIT parsing, timestamp normalization, daily-metric composition | *(no routes)* | [charter](../backend/app/domains/garmin_health/CHARTER.md) |
| `garmin_analytics` | Read models: dashboard, biometrics, period summaries, analysis, insights, recovery score | `/api/dashboard`, `/api/daily-aggregates`, `/api/{metric}/*` | [charter](../backend/app/domains/garmin_analytics/CHARTER.md) |
| `experiments` | Experiment CRUD, day-grain exposures, cached N=1 analysis | `/api/experiments`, `/api/target-metrics` | [charter](../backend/app/domains/experiments/CHARTER.md) |
| `artifacts` | Authored staging + bundle publish; delegates activation to `routines` | `/api/cards`, `/api/assistant/artifacts`, `/api/assistant/artifact-bundles` | [charter](../backend/app/domains/artifacts/CHARTER.md) |
| `journal` | Daily check-ins + freeform notes (subjective context) | `/api/checkins`, `/api/notes` | [charter](../backend/app/domains/journal/CHARTER.md) |
| `programs` | Program spec import + version history (secondary; child activation unbuilt) | `/api/programs` | [charter](../backend/app/domains/programs/CHARTER.md) |
| `core/profile` | App-level profile configuration | `/api/profile` | [charter](../backend/app/core/profile/CHARTER.md) |

Notes: `garmin_sync` is a data-acquisition capability, not a business domain. The `/api/cards` and compatibility-prefixed `/api/assistant/artifact*` routes are owned by `artifacts`; there is no assistant chat slice. `coach` reuses application read models and owns descriptive packaging, structured measurement-assessment validation/persistence, memory, and runtime lifecycle ([reference/coach.md](reference/coach.md)). `garmin_analytics` owns the session-grain run mart (`/api/activities/runs*`) and reserves equivalents for future strength/meditation. `training` projects run association on Today and schedule-window plus measurement evaluation from its injected, training-local `RunActivityReadPort` (range summaries and full run evidence). It reads the newest exact Coach judgment through its separate training-local `MeasurementAssessmentReadPort`. Bootstrap adapts Garmin and Coach storage into those contracts; training directly imports neither source domain (see the [training charter](../backend/app/domains/training/CHARTER.md) and [run reference](reference/run-activities.md)).

## Conventions

Slice boundary convention, `app/utils/` promotion rule, frontend conventions, and code-doc style: **`reference/code-conventions.md`**.

Architecture tests guard route/service boundaries and prevent new imports of removed flat `app.routers.*` / `app.services.*` paths. Current strict-boundary slices: all domains above plus `core/profile`; transitional slices: none.

## Experiment Semantics

Full day-grain exposure semantics live in `backend/app/domains/experiments/CHARTER.md`. In short: one `ExperimentExposure` per `experiment_id + date`, derived from whether the planned daily intervention dose was met — never collapsed to a "best card status", and multiple same-day cards are expected, not ambiguity.

## Route Inventory

Generated from the FastAPI OpenAPI schema + SvelteKit routes: **`reference/routes.md`** — regenerate via `scripts/generate_routes_doc.py` (do not hand-maintain a route list here).

## Frontend

Route list is in `reference/routes.md`. Notable composition: `/today` and `/routines/schedule` render two feeds side by side — the training block's cards (`/api/training/*`) and v2 routine cards (`/api/today`) — and neither domain imports the other. Frontend conventions (runes, typed API client, generated types, display-only): `reference/code-conventions.md`.

## Storage and Runtime Config

Data roots, ingest, and Garmin config paths are documented in full in **`reference/data-and-ingest.md`** (single source of truth). Quick reference:

- DB path: `storage/garmin_stats.db` (`GARMIN_DB_PATH`)
- Wellness tree: `data/garmin_health_stats/` (`GARMIN_DATA_DIR`)
- Activities tree: `data/garmin_activities/` (`GARMIN_ACTIVITY_DATA_DIR`)
- Garmin tokens: `~/.garminconnect` (`GARMINTOKENS`)
- Other: `BACKEND_CORS_ORIGINS`, `PUBLIC_API_BASE_URL`, `GARMIN_COACH_WORKER_ENABLED`

## Source Of Truth Docs

- [docs/README.md](README.md) — documentation index and question router.
- [reference/data-and-ingest.md](reference/data-and-ingest.md) — data topology, ingest/sync, config paths.
- [reference/routes.md](reference/routes.md) — generated route inventory.
- [reference/code-conventions.md](reference/code-conventions.md) — cross-cutting code conventions.
- [reference/coach.md](reference/coach.md) — coach evidence, memory, queue, runtime, and API behavior.
- `backend/app/domains/<domain>/CHARTER.md` — per-domain boundary contracts.
- [README.md](../README.md) — product overview, setup, high-level data-flow narrative.
- [future/ACTIVITY_ANALYTICS_DESIGN.md](future/ACTIVITY_ANALYTICS_DESIGN.md) — planned activity/session analytics.
- [routine-pivot/](routine-pivot/) — training-system canon (principles, v3 schema, roadmap, block0).
- [FINDINGS.md](../FINDINGS.md) — current dataset observations.
