# Programs Structural Refactor Design

Date: 2026-05-10

## Goal

Align the `domains/programs` package layout with the already-refactored
`routines` and `experiments` slices without changing program behavior.

Programs remain a secondary backend domain that owns imported program specs,
program lifecycle status, and program version history. This refactor is
structural only: endpoint paths, response contracts, import validation,
activation/retirement behavior, and version-history semantics stay unchanged.

## Scope

In scope:

- Flatten `domains/programs/api/programs.py` into `domains/programs/routes.py`.
- Rename `domains/programs/application/ports.py` to
  `domains/programs/dependencies.py`.
- Flatten `domains/programs/infra/sqlite_repository.py` into
  `domains/programs/adapters.py`.
- Move program-specific persistence helpers from `app.infra.database` into
  `domains/programs/adapters.py`.
- Keep `Program`, `ProgramVersion`, and response models in
  `domains/programs/contracts.py`.
- Update bootstrap imports, architecture tests, domain tests, and architecture
  documentation to reflect the new layout.

Out of scope:

- No routine activation, experiment creation, artifact staging, protocol
  activation, or child-record writes.
- No API behavior or schema changes.
- No frontend changes.
- No redesign of shared SQLite schema initialization.

## Target Layout

```text
backend/app/domains/programs/
  __init__.py
  adapters.py
  contracts.py
  dependencies.py
  routes.py
  application/
    __init__.py
    programs.py
```

The `api/` and `infra/` packages are removed because each contains only one
stable concept. This matches the small-capability layout used by routines and
experiments.

## Boundaries

`routes.py` owns FastAPI routing for `/api/programs`. It may import
`build_container()` and pass the container-owned `programs_repo` into
application use cases. It must not import shared database helpers directly.

`application/programs.py` owns import, list, read, activate, retire, and version
use cases. It depends on the `ProgramRepository` protocol from
`dependencies.py` and remains FastAPI-free and database-free.

`dependencies.py` owns the `ProgramRepository` protocol. The name aligns with
the routines and experiments convention and makes the file a domain dependency
contract rather than an implementation port package under `application`.

`adapters.py` owns SQLite-backed persistence for programs. It contains
`SqliteProgramRepository` and the program-specific load/save/version helpers
currently living in `app.infra.database`. It may depend on shared SQLite
primitives such as `JsonStore`, `connect`, and `now_iso`.

`contracts.py` remains the home for `Program`, `ProgramVersion`,
`ProgramsResponse`, and `ProgramVersionsResponse`. These models are part of the
program domain and API surface, not adapter-only details.

## Persistence

Program table creation remains in shared SQLite schema initialization for this
structural pass. Only program-specific CRUD and version-history persistence move
into `domains/programs/adapters.py`.

The adapter preserves existing behavior:

- `save_program` stores the current program record in `programs`.
- `load_program` and `load_programs` read current program records.
- `save_program_import` atomically stores the new current program and, when
  provided, the previous current version in `program_versions`.
- `load_program_versions` returns versions ordered by version number.
- The unused `delete_program` helper is removed unless a real current consumer
  is found during implementation. No deletion repository method, route, or use
  case is added.

## Architecture Tests

Update the programs architecture guard rails to require the flattened layout:

- `domains/programs/routes.py` exists and `api/` does not.
- `domains/programs/adapters.py` exists and `infra/` does not.
- `domains/programs/dependencies.py` exists and
  `application/ports.py` does not.
- Program application modules and dependencies remain strict: no FastAPI,
  `build_container`, `app.infra.database`, `app.services`, or `app.routers`.
- `app.infra.database` no longer imports `domains.programs.contracts` and no
  longer owns program CRUD helpers.
- Bootstrap mounts `domains.programs.routes` directly.

## Verification

Because the change touches Python backend files, validation must include:

```bash
cd backend && uv run ruff check
cd backend && uv run pyright app/ tests/
cd backend && uv run pytest tests/ -v
```

No API schema change is intended. If verification shows generated OpenAPI types
changed unexpectedly, investigate before regenerating frontend API types.
