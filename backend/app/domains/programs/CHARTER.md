# programs — Charter

**Status:** secondary (partial)

Program import and management is a secondary backend domain. It currently
persists the program spec and version history only. Child activation —
protocol, routine, and experiment activation from an imported program — is
**intentionally not implemented yet**. The `activate`/`retire` endpoints flip
the program's own lifecycle status (active/retired); they do not activate any
child records.

**Boundary source of truth for this domain. Update in the same PR that changes the domain.**

Secondary backend domain for program spec import and management. `routes.py`
owns HTTP routes, `application/` owns import, activation/retirement, and version
use cases, `dependencies.py` owns the repository dependency protocol, and
`adapters.py` owns SQLite program spec and version-history persistence.

## Owns

- Imported program specs.
- Program lifecycle status.
- Program version history.

## Does not own

- Protocol activation.
- Routine activation.
- Experiment creation.
- Artifact staging.
- Garmin data.
- Assistant runtime behavior.

## May import

- Program repository ports.
- Program-owned contracts.

## Must not import

- Garmin sync.
- Garmin analytics.
- Assistant.
- Artifacts.
- Journal.
- Routine activation internals.
- Experiment management internals.
- FastAPI from application modules.
- SQLite helpers from application modules.

## Public entrypoints

- `/api/programs`
- Program import/list/read use cases.

## Key files

- `routes.py` — program spec import and lifecycle-state routes (single
  `router`, prefix `/api/programs`).
- `application/programs.py` — import, list, read, retire, activate, and
  version-history use cases.
- `dependencies.py` — program repository dependency protocol
  (`ProgramRepository`).
- `adapters.py` — SQLite program spec and version-history persistence.
- `contracts.py` — program, program-version, and program-status API shapes.

## Verified against code (2026-07-10)

Matches, with the secondary/partial status confirmed:

- Route prefix `/api/programs` confirmed. Endpoints: list, detail, `POST
  /import`, `PUT /{id}/retire`, `PUT /{id}/activate`, `GET /{id}/versions`.
- Partial status confirmed. `import_program` persists the spec snapshot plus a
  previous-version row and does no child activation. `activate_program` /
  `retire_program` only mutate the program's own `status` field
  (active/retired) and `retired_at`. The `application/programs.py` docstring
  states the layer "deliberately does not activate protocols, routines,
  experiments, or artifact records; those future workflows will enter through
  explicit dependencies instead of hidden side effects." So the route named
  `activate` is lifecycle status only, not the unbuilt child-record activation
  the Active-service-areas note refers to.
- Import boundaries hold exactly: `application/programs.py` imports only
  `programs.contracts`, `programs.dependencies`, and `app.utils.timeutil` — no
  cross-domain imports. `adapters.py` imports `app.infra` SQLite/JSON store
  helpers (adapter layer). No FastAPI or SQLite helpers in application modules.
