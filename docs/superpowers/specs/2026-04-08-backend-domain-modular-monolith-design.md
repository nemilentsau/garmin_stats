# Backend Domain-Modular Monolith Refactor Design

Date: 2026-04-08
Status: In progress - routines slice completed on 2026-04-10

## Summary

Refactor the backend from a flat collection of routers and services into a domain-modular monolith with enforced internal boundaries. The external HTTP API stays stable during phase 1. Storage internals may change when that improves domain ownership, testability, or migration safety.

The refactor optimizes for these priorities in order:

1. Change safety and testability
2. Domain ownership and navigability
3. Strict dependency enforcement

This is a whole-backend target architecture with phased implementation. It is not a big-bang rewrite.

## Implementation Status

### Completed on `refactor`

The first implementation milestone is now merged into `refactor`.

What landed:

- app assembly was split out of `backend/app/main.py` into `backend/app/bootstrap/{app,lifespan,routing,container}.py`
- initial shared-core extraction started with `backend/app/core/config.py`
- the first domain package was introduced under `backend/app/domains/routines/`
- routines catalog, schedule window, today, and activation logic now live in domain-local `api`, `application`, `domain`, and `infra` modules
- old flat `routers/routines.py`, `routers/today.py`, `services/schedule_projection.py`, and `services/today.py` now act as compatibility seams
- routines activation now persists the live schedule and assignments atomically
- startup ingest coverage now includes the second-run no-op case
- architecture guard tests now defend the routines slice from falling back into router-to-database shortcuts
- backend packaging was normalized around `pyproject.toml` and `uv.lock`, and the backend now targets Python 3.14

Verification on the merged branch:

- `cd backend && uv run ruff check`
- `cd backend && uv run pyright app/ tests/`
- `cd backend && uv run pytest tests/ -v`

All three passed on the merged `refactor` branch, with `pytest` at `308 passed`.

### Current state of the target architecture

The codebase is now in the expected transitional state:

- `bootstrap/` is real and owns app assembly
- `domains/routines/` is real and owns one vertical slice
- `main.py` and several flat routes/services remain as explicit compatibility entrypoints
- the rest of the backend still needs migration into domain-local packages

This is the intended halfway shape for a phased modular-monolith migration.

## Current Problems

The current backend shape has accumulated structural debt:

- `backend/app/main.py` centrally imports and registers nearly all routers and startup concerns.
- Flat `routers/` and `services/` directories make ownership unclear.
- Some routers bypass services and call `infra.database` or `stats` directly.
- Shared modules like `backend/app/models.py` and `backend/app/stats.py` have become cross-domain dumping grounds.
- Large mixed-responsibility modules are already hard to reason about, especially in routines, experiments, and Garmin analytics.

This creates three practical failures:

1. Structural edits are high-risk because behavior and dependency boundaries are unclear.
2. It is too hard to find the real owner of a workflow or data shape.
3. Layer violations are already normal, so the codebase has no way to defend itself against more sprawl.

## Goals

- Reorganize the backend around business domains rather than flat technical folders.
- Enforce a stable request flow from HTTP boundary to application use case to infrastructure.
- Reduce the blast radius of changes by making domain ownership explicit.
- Preserve the current HTTP API surface during phase 1 unless a route is objectively broken.
- Allow storage and repository reshaping when needed to support clearer boundaries.
- Support incremental migration with compatibility seams and stable tests.

## Non-Goals

- No frontend architecture refactor in phase 1.
- No intentional public API redesign in phase 1.
- No big-bang rewrite of the whole backend.
- No maximalist clean-architecture ceremony that adds abstraction without reducing maintenance cost.

## Constraints And Decisions

- Phase 1 treats the existing HTTP API surface as fixed.
- Storage internals may change as needed.
- Compatibility wrappers and re-export modules are allowed during migration.
- The design targets the whole backend end state, but implementation will move domain by domain.
- The refactor will rely on characterization tests and seam tests before aggressive structural moves.

## Target Architecture

The backend becomes a domain-modular monolith:

```text
backend/app/
  bootstrap/
    app.py
    lifespan.py
    routing.py
    container.py

  core/
    config/
    contracts/
    db/
    errors/
    events/
    logging/
    time/

  domains/
    garmin_analytics/
      api/
      application/
      domain/
      infra/
    assistant/
      api/
      application/
      domain/
      infra/
    routines/
      api/
      application/
      domain/
      infra/
    experiments/
      api/
      application/
      domain/
      infra/
    programs/
      api/
      application/
      domain/
      infra/
    profile/
      api/
      application/
      domain/
      infra/

  legacy/
    compatibility shims and migration wrappers
```

### Layer meanings

- `api/`: FastAPI routers, request parsing, response mapping, HTTP concerns only.
- `application/`: use cases and orchestration. This layer coordinates work.
- `domain/`: business rules, domain types, invariants, pure logic.
- `infra/`: repositories, persistence adapters, event publishing, external integrations.

### Dependency rules

- `api -> application -> domain`
- `application -> domain`
- `application -> infra` only through narrow, explicit dependencies
- `infra -> domain`
- `domain` must not depend on FastAPI, SQLite, or sibling domains

Forbidden patterns in new code:

- router directly importing low-level database helpers
- router directly importing `stats.py`
- domain logic reaching into FastAPI request or response types
- casual sibling-domain imports without an explicit boundary

## Domain Ownership

### `garmin_analytics`

Owns the dashboard-facing Garmin read models and analytical use cases:

- dashboard overview
- day summaries and period summaries
- Garmin metric detail endpoints and analysis endpoints
- Garmin-specific dashboard logic currently spread across service and stats modules

Initial domain scope:

- `dashboard`
- `days`
- `wellness`
- `sleep`
- `daily_aggregates`
- `skin_temp`
- `heart_rate`
- `hrv`
- `stress`
- `body_battery`

This domain is read-oriented. It does not own ingest startup logic, file watching, or archive extraction.

### `assistant`

Owns:

- assistant threads, messages, and runs
- assistant context snapshots
- assistant runtime integration
- assistant event publishing related to assistant workflows
- assistant HTTP streaming behavior

Phase 1 ownership decision:

- assistant artifact and bundle APIs remain externally owned by `assistant` for compatibility
- routine execution concerns that consume activated artifacts belong in `routines`

This keeps the public seam stable while the internal ownership becomes clearer.

### `routines`

Owns:

- schedule projection
- live compiled routine runtime
- card and occurrence read models for schedule and today
- today execution flows
- card logging
- routine-side activation and projection logic required to power schedule/today behavior

This domain is currently one of the most structurally important and entangled areas, so it should be migrated early.

### `experiments`, `programs`, `profile`

These are real domains in the end-state architecture, but they are lower-priority for strict enforcement in the first implementation slices.

- `experiments`: experiment CRUD, preview, analysis orchestration, exposures
- `programs`: program imports and versioned program data
- `profile`: user profile, checkins, notes, and adjacent personal-state APIs

For this refactor, `checkins` and `notes` stay inside `profile`. Splitting them later would require a separate follow-up design.

### Shared runtime and infrastructure

Ingest and watcher concerns do not belong to `garmin_analytics`. They feed the system rather than implement dashboard-domain use cases. They should live in shared runtime or infrastructure modules under `bootstrap/` and `core/` until ingestion itself is intentionally modularized.

## Bootstrap And Shared Core

`backend/app/main.py` should stop being the single place where app assembly, lifespan behavior, middleware, exception handling, and router registration all accumulate.

Split it into:

- `bootstrap/app.py`: app factory and high-level FastAPI construction
- `bootstrap/lifespan.py`: startup and shutdown orchestration
- `bootstrap/routing.py`: domain router registration
- `bootstrap/container.py`: domain wiring and shared dependency assembly

Shared `core/` owns low-level concerns:

- config and environment loading
- DB connection primitives and transaction helpers
- event bus primitives
- shared error types
- shared time and logging utilities
- narrow contracts used across domains

The point of `core/` is to host shared infrastructure primitives, not to become a new global dumping ground for business logic.

## Data And Model Strategy

The current global `models.py` approach should be reduced over time.

Target model split:

- API contracts live near `api/`
- domain models and invariants live near `domain/`
- persistence row mappers and storage DTOs live near `infra/`

This migration should be incremental. The immediate rule is not "move every model now." The rule is "stop adding unrelated models to one global file and move them as domains are migrated."

## Stats And Parser Strategy

### `parser.py`

`parser.py` remains part of the ingest pipeline until ingest is explicitly modularized. It should not be folded into `garmin_analytics`, because ingest is a data pipeline concern, not a dashboard use-case concern.

### `stats.py`

`stats.py` should be split by ownership:

- Garmin analytics logic moves toward `domains/garmin_analytics`
- truly shared math and utility logic can move to `core`

The current all-purpose statistics bucket should shrink and eventually disappear as a business-logic catchall.

## Database Strategy

The current low-level database surface is too global. The target structure is:

- `core/db`: connections, transactions, low-level primitives
- `domains/*/infra`: repositories and query intent owned by each domain

Domain repositories should describe business intent rather than expose generic tables everywhere. This allows storage to evolve without pushing low-level persistence details into routers and use cases.

Phase 1 does not require immediate schema decomposition or physical table isolation if that would add risk. It does require moving query ownership toward the right domain packages.

## Migration Strategy

This refactor is implemented as phased vertical slices.

### Step A: establish structure without changing behavior

- create `bootstrap/`, `core/`, and `domains/` packages
- move app assembly out of `main.py`
- add domain-local packages and initial wiring points
- keep old import paths working where needed

### Step B: add characterization and seam tests

Before moving heavy internals, strengthen tests around:

- HTTP contract behavior for active routes
- assistant runtime flows
- routine schedule and today flows
- Garmin analytics read endpoints
- startup and ingest idempotence when touched

The goal is not test bulk. The goal is regression tripwires around public behavior and critical orchestration seams.

### Step C: migrate domains in recommended order

Recommended order:

1. `routines` - completed on 2026-04-10
2. `assistant`
3. `garmin_analytics`
4. secondary domains such as `experiments`, `programs`, and `profile`

Rationale:

- `routines` is highly user-visible and structurally entangled
- `assistant` has a strong domain boundary but cross-cuts runtime, events, and context
- `garmin_analytics` is broad but mostly read-oriented and becomes easier to stabilize after shared seams improve

### Step D: keep compatibility seams during transition

Allowed transitional tactics:

- wrapper modules at old import paths
- re-export modules
- old routers delegating to new application use cases
- temporary adapter layers between old database helpers and new repositories

These are not permanent architecture. They are migration tools used to keep the refactor safe.

### Step E: cleanup after a domain is stable

When a domain is fully migrated and covered by tests:

- remove dead flat entrypoints
- remove obsolete compatibility wrappers
- tighten enforcement rules further

## Request Flow Rules

The standard request path is:

1. HTTP enters through `domains/*/api`
2. router calls an application use case
3. application layer coordinates domain rules and infrastructure adapters
4. infra reads or writes storage and integrations
5. response mapping happens at the API boundary

This is the core behavioral seam for the refactor. New code must conform to it.

## Testing Strategy

The testing strategy follows the chosen priority order:

1. change safety and testability
2. ownership and navigability
3. strict enforcement

### Required test emphasis

- characterization tests before structural moves
- use-case seam tests for migrated application logic
- route contract tests for stable public behavior
- idempotence and no-op tests for startup, watcher, or ingest changes
- cross-flow tests where the value is in orchestration rather than pure computation

### Avoid

- brittle tests that assert internal call sequences instead of behavior
- over-mocking that hides real regression risk
- broad rewrites without seam coverage

### Domain migration definition of done

A migrated domain is not "done" when files move. It is done when:

- routes are served from the new domain package
- use cases live in `application`
- direct router-to-database shortcuts are removed
- characterization and regression tests pass
- compatibility shims are either explicitly retained or removed

## Enforcement Strategy

Strict enforcement is important, but it should come after seams and tests exist.

Recommended enforcement progression:

1. document allowed dependency directions
2. move code into clear package ownership
3. add architecture checks or lint rules for forbidden imports
4. remove transitional escape hatches once domains are stable

Examples of useful enforcement once migration starts:

- routers cannot import `core/db` directly
- routers cannot import global legacy database helpers directly
- domain packages cannot import sibling domain internals casually
- new code cannot be added to deprecated flat service buckets once a domain has a new home

## Risks And Mitigations

### Risk: migration stalls in a half-old, half-new state

Mitigation:

- migrate vertically by domain
- define completion criteria per domain
- keep compatibility layers explicit and temporary

### Risk: structural edits break frontend behavior indirectly

Mitigation:

- keep HTTP contracts stable in phase 1
- preserve response semantics
- regenerate frontend API types only if backend contract changes intentionally

### Risk: shared modules continue to grow during migration

Mitigation:

- freeze further growth of flat global buckets
- require new behavior to land in domain packages when a domain home exists

### Risk: enforcement arrives too early and slows the migration

Mitigation:

- prioritize characterization tests and seam ownership first
- add strict import enforcement only after the new structure is in use

## Recommended First Implementation Milestone

The first implementation milestone should deliver:

- bootstrap split from `main.py`
- domain package skeletons
- initial `core/` extraction for low-level shared concerns
- strengthened seam tests around `routines`
- first vertical migration of the `routines` domain behind unchanged HTTP routes

This is the smallest milestone that proves the architecture is real rather than aspirational.

This milestone is complete and has been merged into `refactor`.

## Next Recommended Milestones

### Milestone 2: `assistant`

Move assistant thread, message, run, context, and runtime orchestration into `domains/assistant/` while keeping the current `/api/assistant` HTTP contract stable. Keep assistant artifact and bundle routes externally stable during this slice; they can remain on the existing `training_specs.py` seam until artifact ownership is intentionally revisited.

### Milestone 3: `garmin_analytics`

Move dashboard and Garmin metric read paths into `domains/garmin_analytics/`, starting with read-oriented endpoints that already have strong test coverage. Split `stats.py` by ownership as this migration progresses, but do not fold ingest or watcher logic into the analytics domain.

### Milestone 4: secondary domains and cleanup

Migrate `experiments`, `programs`, and `profile` out of the flat buckets, then remove obsolete compatibility wrappers, continue shrinking `models.py` and `stats.py`, and tighten import enforcement once each migrated domain is stable.

## Final Recommendation

Adopt a domain-modular monolith with phased vertical migration, stable HTTP contracts, storage flexibility, compatibility seams, and test-first structural moves. Do not attempt a whole-backend big-bang rewrite. Use the whole-backend design as the target, then reach it through domain-specific implementation slices.
