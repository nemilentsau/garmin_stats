# artifacts — Charter

**Status:** shipped
**Boundary source of truth for this domain. Update in the same PR that changes the domain.**

Authored v2 artifact staging and publishing. Validated artifacts and bundles
are activated into live routine/card data. It uses a flat
small-capability layout and delegates live routine activation writes to
`domains/routines`.

## Owns

- Authored artifact staging.
- Card template persistence before activation.
- Bundle preview/import.
- Bundle revision tracking.
- Capability request records.

## Does not own

- Live routine schedule semantics after activation.
- Experiment protocol semantics.
- Coach runtime.
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
- Coach runtime internals.
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

`authored JSON -> staged artifact or bundle import -> validation -> activation -> live routine record`

Activated cards/routines become live runtime data owned by `domains/routines`.
