# Architecture

Current-state code map. Not a roadmap, not a historical diary. This file is the high-level map; per-domain boundary contracts live colocated at `backend/app/domains/<domain>/CHARTER.md`, and volatile facts live in the reference docs linked below.

## Product Shape

The shipped app has five active product centers:

1. Recovery dashboard and metric drill-downs
2. Runs: tracked running sessions, detail/series views, and prescription evidence
3. Coach: queued run reviews, evidence-grounded chat, and bounded semantic memory
4. Training block runtime (v3): artifact import, lint-gated activation, and the Today/schedule training feed
5. Experiment runtime: explicit-date designs, manual day-grain exposures, and N=1 analysis

Experiment and training content enters the app only through import/upload of authored artifacts. There are no generators, translators, seeders, or derived content artifacts; runtime projections never rewrite imported content.

## Project Layout

- `backend/app/` — FastAPI application code.
- `backend/tests/` — backend tests by ownership: architecture guards, bootstrap, infra, core, and domain slices.
- `frontend/src/` — SvelteKit application.
- Local SQLite and Garmin data roots are runtime state, not repository source. Their exact defaults, environment overrides, and lifecycles live in `reference/data-and-ingest.md`.

Full data topology, ingest/sync flow, and config paths: **`reference/data-and-ingest.md`**.

## Backend

Boundary tests guard module intent, not a mandatory folder template. Larger slices may use `api/`, `application/`, and `infra/` packages when those layers contain multiple stable concepts; small capability slices stay flatter.

### Main flow

Three paths:

- **Ingest (wellness):** FIT files → Garmin health FIT parser → daily metric composer → SQLite.
- **Activity:** tracked-session FIT/JSON downloaded from Garmin Connect every sync; running activities parsed into `running_activity_{sessions,laps,series}` on sync/startup and associated with prescribed run cards (see `reference/run-activities.md`); strength/breathing parse pending (`future/strength-activities.md`).
- **Read:** SQLite → repository adapters → domain/core application slices → JSON API → frontend.

Dependency direction (the layering enforced by architecture tests):

- `garmin_sync` ingest adapters → `garmin_health`, `app.utils`
- `garmin_analytics` → `garmin_health`, `app.utils`
- `experiments` → Garmin health and journal contracts plus injected analytics/journal read sources
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
| `training` | v3 training import, lint-gated activation, Today/schedule execution and measurement projection, authored backup runtime, capture logs | `/api/training/*` | [charter](../backend/app/domains/training/CHARTER.md) |
| `garmin_sync` | Garmin archive + tracked-activity acquisition, ingest/sync (running activities parsed; strength/breathing download-only) | `/api/ingest`, `/api/ingest/status`, `/api/ingest/sync` | [charter](../backend/app/domains/garmin_sync/CHARTER.md) |
| `garmin_health` | Canonical FIT parsing, timestamp normalization, daily-metric composition | *(no routes)* | [charter](../backend/app/domains/garmin_health/CHARTER.md) |
| `garmin_analytics` | Read models: dashboard, biometrics, period summaries, analysis, insights, recovery score, tracked runs | `/api/dashboard`, `/api/daily-aggregates`, `/api/{metric}/*`, `/api/activities/runs*` | [charter](../backend/app/domains/garmin_analytics/CHARTER.md) |
| `experiments` | Imported experiment definitions, day-grain exposures, cached N=1 analysis | `/api/experiments`, `/api/target-metrics` | [charter](../backend/app/domains/experiments/CHARTER.md) |
| `journal` | Daily check-ins + freeform notes (subjective context) | `/api/checkins`, `/api/notes` | [charter](../backend/app/domains/journal/CHARTER.md) |
| `core/profile` | App-level profile configuration | `/api/profile` | [charter](../backend/app/core/profile/CHARTER.md) |

Notes: `garmin_sync` is a data-acquisition capability, not a business domain. `coach` reuses application read models and owns descriptive packaging, structured measurement-assessment validation/persistence, memory, and runtime lifecycle ([reference/coach.md](reference/coach.md)). `garmin_analytics` owns the session-grain run mart (`/api/activities/runs*`). `training` projects run association on Today and schedule-window plus measurement evaluation from its injected, training-local `RunActivityReadPort`; it reads exact Coach judgments through a separate `MeasurementAssessmentReadPort`. Bootstrap adapts Garmin and Coach storage into those contracts, so Training imports neither source domain (see the [training charter](../backend/app/domains/training/CHARTER.md) and [run reference](reference/run-activities.md)).

## Conventions

Slice boundary convention, `app/utils/` promotion rule, frontend conventions, and code-doc style: **`reference/code-conventions.md`**.

Architecture tests guard route/service boundaries and prevent new imports of removed flat `app.routers.*` / `app.services.*` paths. Current strict-boundary slices: all domains above plus `core/profile`; transitional slices: none.

## Experiment Semantics

Full day-grain exposure semantics live in `backend/app/domains/experiments/CHARTER.md`. In short: one manually recorded `ExperimentExposure` per `experiment_id + date`, representing whether the planned daily intervention dose was met.

## Route Inventory

Generated from the FastAPI OpenAPI schema + SvelteKit routes: **`reference/routes.md`** — regenerate via `scripts/generate_routes_doc.py` (do not hand-maintain a route list here).

## Frontend

Route list is in `reference/routes.md`. `/today` and `/training/schedule` render the v3 training read models from `/api/training/*`. Frontend conventions (runes, typed API client, generated types, display-only): `reference/code-conventions.md`.

## Storage and Runtime Config

Data roots, ingest lifecycles, Garmin credentials, and path overrides live only in **`reference/data-and-ingest.md`**. Other application settings are defined by `backend/app/core/config.py` and their owning feature references.

## Source Of Truth Docs

- [docs/README.md](README.md) — documentation index and question router.
- [reference/data-and-ingest.md](reference/data-and-ingest.md) — data topology, ingest/sync, config paths.
- [reference/routes.md](reference/routes.md) — generated route inventory.
- [reference/code-conventions.md](reference/code-conventions.md) — cross-cutting code conventions.
- [reference/coach.md](reference/coach.md) — coach evidence, memory, queue, runtime, and API behavior.
- `backend/app/domains/<domain>/CHARTER.md` — per-domain boundary contracts.
- [README.md](../README.md) — product overview, setup, high-level data-flow narrative.
- [future/strength-activities.md](future/strength-activities.md) — the retained unbuilt strength-session ingest contract.
- [routine-pivot/](routine-pivot/) — training-system canon (principles, v3 schema, roadmap, frozen block0 exemplar, active block1).
- [FINDINGS.md](../FINDINGS.md) — current dataset observations.
