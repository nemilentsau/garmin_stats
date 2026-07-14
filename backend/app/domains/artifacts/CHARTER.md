# artifacts — Charter

**Status:** shipped
**Boundary source of truth for this domain. Update in the same PR that changes the domain.**

Assistant-authored artifact staging and publishing. Artifacts is the staging
and publishing layer for assistant-authored objects; validated artifacts and
bundles are activated into live routine/card data. It uses a flat
small-capability layout and delegates live routine activation writes to
`domains/routines`.

## Owns

- Assistant-authored artifact staging.
- Card template persistence before activation.
- Bundle preview/import.
- Bundle revision tracking.
- Capability request records.

## Does not own

- Live routine schedule semantics after activation.
- Experiment protocol semantics.
- Assistant chat runtime.
- Garmin data.

## May import

- Artifact repository dependencies.
- Artifact-owned contracts.
- Allowlisted routine activation contracts/dependencies for publishing live
  cards/routines.

## Must not import

- Garmin sync.
- Garmin analytics.
- Journal.
- Experiments application internals.
- Assistant runtime internals.
- FastAPI from application modules.
- SQLite helpers from application modules.

## Public entrypoints

- `/api/cards`
- `/api/assistant/artifacts`
- `/api/assistant/artifact-bundles`
- Bundle preview.
- Bundle import.

## Key files

- `routes.py` — artifact, bundle, and card-template routes
  (`assistant_artifacts_router`, `assistant_artifact_bundles_router`,
  `cards_router`).
- `application/` — staging, bundle planning/import, activation, validation, and
  card catalog use cases
  (`staging`, `bundles`, `bundle_ids`, `activation`, `validation`,
  `placeholder_validation`).
- `dependencies.py` — artifact repository port (`ArtifactRepository`).
- `adapters.py` — SQLite artifact repository adapter.
- `contracts.py` — staged artifact and bundle API shapes.

Normal artifact flow:

`assistant/generated JSON -> staged artifact or bundle import -> validated
artifact -> activation -> live domain record`

Activated cards/routines become live runtime data owned by `domains/routines`.
Future experiment artifacts should enter through this domain, then delegate
final writes to `domains/experiments`.

## Verified against code (2026-07-10)

Matches. Route prefixes (`/api/cards`, `/api/assistant/artifacts`,
`/api/assistant/artifact-bundles`), Owns, and the "May/Must not import"
boundaries all hold:

- The only cross-domain imports in `application/` are to `routines`
  (`routines.dependencies.RoutineRepository`,
  `routines.application.activation.compile_routine_activation`,
  `routines.contracts`), matching the allowlisted routine activation exception.
- No imports of Garmin sync/analytics, journal, experiments, or
  assistant runtime were found. `adapters.py` imports `app.infra` SQLite/JSON
  store helpers (adapter layer, allowed); application modules import no FastAPI
  or SQLite helpers.
- The `/api/cards` catalog read is served directly in `routes.py` via
  `routines_repo.list_card_templates` rather than a dedicated `application/`
  module; the other four routes delegate to application use cases.
